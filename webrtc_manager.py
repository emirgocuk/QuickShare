"""
QuickShare WebRTC Manager
P2P dosya transferi için WebRTC DataChannel yönetimi
"""

import asyncio
import json
import os
import hashlib
import time
import threading
import math
from typing import Optional, Callable, List, Dict
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import socketio
from config import WEBRTC_CHUNK_SIZE, ICE_SERVERS, WEBRTC_TIMEOUT, SIGNALING_SERVER_URL


def is_safe_path(basedir, path, follow_symlinks=True):
    # resolves symbolic links
    if follow_symlinks:
        return os.path.realpath(path).startswith(os.path.realpath(basedir))
    return os.path.abspath(path).startswith(os.path.abspath(basedir))


def _get_rtc_config() -> RTCConfiguration:
    """Create RTCConfiguration from ICE_SERVERS config"""
    ice_servers = []
    for s in ICE_SERVERS:
        ice_servers.append(RTCIceServer(
            urls=s["urls"],
            username=s.get("username"),
            credential=s.get("credential")
        ))
    return RTCConfiguration(iceServers=ice_servers)


class WebRTCSender:
    """
    Gönderen tarafı — dosyaları DataChannel üzerinden P2P gönderir.
    Flask signal server'ın arkasında çalışır.
    """

    def __init__(self):
        self.peers = {} # {sid: {"pc": RTCPeerConnection, "channel": RTCDataChannel, "ready": asyncio.Event(), "start": asyncio.Event(), "files_to_send": [], "offsets": {}}}
        self.files: List[Dict] = []  # [{name, path, size}]
        self.status = "idle"  # idle, waiting, connected, transferring, done
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.log_callback: Optional[Callable] = None
        self.progress_callback: Optional[Callable] = None
        self.password: Optional[str] = None # Added for Phase 9 Security
        # Track connection state for UI (true if AT LEAST ONE peer is connected)
        self._connected_event = threading.Event()
        # Global Speed tracking across all peers
        self._speed_last_time = 0.0
        self._speed_last_bytes = 0
        self._current_speed = 0.0
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set() # Not paused by default
        self.signaling = None

    def setup_signaling(self, signaling_client):
        """Attach signaling client"""
        self.signaling = signaling_client
        self.signaling.on_offer = self.handle_signaling_offer
        self.signaling.on_ice = self.handle_signaling_ice

    async def handle_signaling_offer(self, sdp, sender_sid):
        """Handle offer from signaling server"""
        self._log(f"Offer received from {sender_sid}")
        answer = await self.handle_offer(sdp, sender_sid=sender_sid)
        await self.signaling.send_answer(answer["sdp"], target_sid=sender_sid)

    async def handle_signaling_ice(self, candidate, sender_sid):
        """Handle ICE candidate"""
        if sender_sid in self.peers and self.peers[sender_sid]["pc"]:
            try: pass 
            except: pass

    def _log(self, msg):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass  # Never let a log failure crash the transfer

    def set_files(self, file_list: List[Dict]):
        """Set the file list to send — [{name, path, size}]"""
        self.files = file_list

    def start(self):
        """Start the async event loop in a background thread"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def wait_until_ready(self, timeout=5.0):
        """Wait until the async loop is initialized"""
        start = time.time()
        while self._loop is None:
            if time.time() - start > timeout:
                raise RuntimeError("WebRTC loop failed to start")
            time.sleep(0.01)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Clean shutdown"""
        if self._stopped:
            return
            
        # Send STOPPED signal to all peers
        for peer_id, peer_data in self.peers.items():
            channel = peer_data.get("channel")
            if channel and channel.readyState == "open" and self._loop and self._loop.is_running():
                try:
                    self._loop.call_soon_threadsafe(channel.send, json.dumps({"type": "STOPPED"}))
                except: pass

        self._stopped = True
        self._pause_event.set()  # Unpause to let loops exit
        
        async def _shutdown():
            for peer_id, peer_data in list(self.peers.items()):
                pc = peer_data.get("pc")
                if pc:
                    try: await pc.close()
                    except: pass
            self.peers.clear()
            
            # Cancel all running tasks except this shutdown task
            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks(self._loop) if t is not current_task]
            for task in tasks:
                task.cancel()
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
            self._loop.stop()

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            
        self.status = "idle"
        self._current_speed = 0.0

    def pause(self):
        """Pause transfer"""
        if not self._stopped:
            self._pause_event.clear()
            self._current_speed = 0.0 # Reset speed
            self._log("⏸️ Transfer duraklatıldı")
            # Send pause signal to all receivers
            for peer_data in self.peers.values():
                channel = peer_data.get("channel")
                if channel and channel.readyState == "open" and self._loop and self._loop.is_running():
                    try: self._loop.call_soon_threadsafe(channel.send, json.dumps({"type": "PAUSE"}))
                    except: pass

    def resume(self):
        """Resume transfer"""
        if not self._stopped:
            self._pause_event.set()
            self._log("▶️ Transfer devam ediyor")
            # Send resume signal to all receivers
            for peer_data in self.peers.values():
                channel = peer_data.get("channel")
                if channel and channel.readyState == "open" and self._loop and self._loop.is_running():
                    try: self._loop.call_soon_threadsafe(channel.send, json.dumps({"type": "RESUME"}))
                    except: pass

    async def handle_offer(self, offer_sdp: str, offer_type: str = "offer", sender_sid: str = "default_peer") -> dict:
        """
        Alıcıdan gelen SDP offer'ı işle ve answer döndür.
        """
        pc = RTCPeerConnection(configuration=_get_rtc_config())
        
        # Initialize peer context
        peer_data = {
            "pc": pc,
            "channel": None,
            "ready": asyncio.Event(),
            "start": asyncio.Event(),
            "files_to_send": [],
            "offsets": {},
            "status": "waiting",
            "last_time": 0.0,
            "last_bytes": 0,
            "current_speed": 0.0
        }
        self.peers[sender_sid] = peer_data
        self.status = "waiting" # Global status

        @pc.on("datachannel")
        def on_datachannel(channel):
            peer_data["channel"] = channel
            self._log(f"[{sender_sid}] DataChannel bağlandı!")
            peer_data["status"] = "connected"
            self.status = "connected"
            self._connected_event.set()

            @channel.on("message")
            def on_message(message):
                try:
                    data = json.loads(message)
                    if data.get("type") == "PAUSE":
                        self._log(f"[{sender_sid}] ⏸️ Alıcı tarafından duraklatıldı")
                        self._pause_event.clear()
                    elif data.get("type") == "RESUME":
                        self._log(f"[{sender_sid}] ▶️ Alıcı tarafından devam ettirildi")
                        self._pause_event.set()
                    elif data.get("type") == "DOWNLOAD_REQUEST":
                        requested = data.get("files", [])
                        peer_data["offsets"] = data.get("offsets", {})  # Store requested offsets
                        if not requested: pass
                        
                        peer_data["files_to_send"] = requested
                        self._log(f"[{sender_sid}] İndirme isteği alındı: {len(requested)} dosya")
                        peer_data["start"].set()

                    elif data.get("type") == "auth":
                        if self.password and data.get("password") != self.password:
                            channel.send(json.dumps({"type": "auth_failed"}))
                            self._log(f"[{sender_sid}] 🔒 Alıcı yanlış parola girdi!")
                            # Optional: Wait a bit then close pc?
                        else:
                            channel.send(json.dumps({"type": "auth_success"}))
                            peer_data["ready"].set()
                            self._log(f"[{sender_sid}] Hazır (kimlik doğrulandı), veriler yollanıyor...")
                            asyncio.ensure_future(self._send_files_async(sender_sid))

                    elif data.get("type") == "ready":
                        if self.password:
                            channel.send(json.dumps({"type": "auth_required"}))
                            self._log(f"[{sender_sid}] 🔒 Alıcıdan parola bekleniyor...")
                        else:
                            peer_data["ready"].set()
                            self._log(f"[{sender_sid}] Alıcı hazır, dosya listesi gönderiliyor...")
                            asyncio.ensure_future(self._send_files_async(sender_sid))
                except json.JSONDecodeError:
                    self._log(f"[{sender_sid}] Alıcıdan bilinmeyen mesaj: {message}")
                except Exception as e:
                    self._log(f"[{sender_sid}] Alıcı mesajı işlenirken hata: {e}")


        @pc.on("connectionstatechange")
        async def on_state_change():
            self._log(f"[{sender_sid}] Bağlantı durumu: {pc.connectionState}")
            if pc.connectionState == "failed":
                peer_data["status"] = "failed"
                # Remove from peers implicitly or explicitly later
            elif pc.connectionState == "closed":
                peer_data["status"] = "closed"

        # Set remote description (the offer)
        offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
        await pc.setRemoteDescription(offer)

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        self._log(f"[{sender_sid}] SDP answer oluşturuldu")
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

    def handle_offer_sync(self, offer_sdp: str, sender_sid: str = "default_peer") -> dict:
        """Synchronous wrapper for handle_offer"""
        if not self._loop:
            self.start()
            time.sleep(0.5)  # Wait for loop to start
        
        future = asyncio.run_coroutine_threadsafe(
            self.handle_offer(offer_sdp, sender_sid=sender_sid), self._loop
        )
        return future.result(timeout=WEBRTC_TIMEOUT)

    async def _send_files_async(self, peer_sid: str):
        """Send all files over the peer's DataChannel"""
        if peer_sid not in self.peers: return
        peer_data = self.peers[peer_sid]
        channel = peer_data.get("channel")
        
        if not channel:
            self._log(f"[{peer_sid}] DataChannel bağlı değil!")
            return

        peer_data["status"] = "transferring"
        self.status = "transferring"

        # 1. Send file list
        file_list_msg = {
            "type": "file_list",
            "files": [{"name": f["name"], "size": f["size"]} for f in self.files],
            "total_size": sum(f["size"] for f in self.files)
        }
        channel.send(json.dumps(file_list_msg))
        self._log(f"[{peer_sid}] Dosya listesi gönderildi, seçim bekleniyor...")
        
        # Wait for download request
        await peer_data["start"].wait()
        
        # Filter files to send
        files_to_send = []
        if peer_data["files_to_send"]:
            # Filter self.files keeping order
            files_to_send = [f for f in self.files if f['name'] in peer_data["files_to_send"]]
            if not files_to_send:
                self._log("⚠️ İstenen dosyalar bulunamadı veya liste boş.")
                # We should probably send an "end" or error
                # For now, just log and proceed with empty list, which will skip transfer.
                pass
        else:
            # If _files_to_send is empty, it means the receiver requested all or didn't specify.
            # For now, we'll assume if _files_to_send is empty after _transfer_start_event,
            # it implies "send all". This might need refinement based on receiver behavior.
            files_to_send = self.files
        
        total_files_count = len(files_to_send)
        self._log(f"Transfer başlıyor: {total_files_count} dosya gönderilecek.")

        total_sent = 0
        total_size = sum(f["size"] for f in files_to_send)

        for i, file_info in enumerate(files_to_send):
            if self._stopped:
                break
            name = file_info["name"]
            path = file_info["path"]
            size = file_info["size"]
            
            # Check for resume offset
            offset = peer_data.get("offsets", {}).get(name, 0)
            if offset > size:
                offset = 0 # Invalid offset, start from 0
            
            if offset > 0:
                self._log(f"[{peer_sid}] Resume aktifleştirildi: {name} ({offset} bytes atlanıyor)")

            # 2. FILE_START
            start_msg = {
                "type": "file_start",
                "name": name,
                "size": size,
                "index": i,
                "total": total_files_count,
                "offset": offset
            }
            channel.send(json.dumps(start_msg))

            # 3. Send chunks adaptively
            file_hash = hashlib.sha256()
            file_sent = offset
            total_sent += offset # Pre-add offset to total so progress starts correctly
            
            # ADAPTIVE CHUNKING LOGIC
            # Start with a chunk size based on file size, but cap it at 256KB for WebRTC safety
            MIN_CHUNK_SIZE = 16 * 1024       # 16 KB
            MAX_CHUNK_SIZE = 256 * 1024      # 256 KB
            
            # Base chunk size on file size (larger file = larger optimal chunk)
            optimal_chunk = max(MIN_CHUNK_SIZE, min(MAX_CHUNK_SIZE, size // 1000))
            current_chunk_size = optimal_chunk
            
            BUFFER_THRESHOLD = current_chunk_size * 8 # Target max buffer

            with open(path, "rb") as f:
                if offset > 0:
                    f.seek(offset)
                    
                while True:
                    # Check pause
                    await self._pause_event.wait()
                    
                    if self._stopped:
                        break
                        
                    chunk = f.read(current_chunk_size)
                    if not chunk:
                        break

                    # Wait for buffer to drain if needed (backpressure)
                    buffered = channel.bufferedAmount
                    if buffered > BUFFER_THRESHOLD:
                        # Network is congested! Throttle down the chunk size temporarily to prevent bloat
                        current_chunk_size = max(MIN_CHUNK_SIZE, current_chunk_size // 2)
                        
                        backoff = 0.001
                        while channel.bufferedAmount > BUFFER_THRESHOLD:
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 1.5, 0.05)  # Max 50ms wait per loop
                    else:
                        # Network is clear, slowly increase back to optimal chunk size
                        if current_chunk_size < optimal_chunk:
                            current_chunk_size = min(optimal_chunk, int(current_chunk_size * 1.2))

                    channel.send(chunk)
                    file_hash.update(chunk)
                    file_sent += len(chunk)
                    total_sent += len(chunk)

                    # Progress callback (throttled to avoid GUI overhead)
                    if self.progress_callback:
                        now = time.time()
                        elapsed = now - peer_data["last_time"]
                        if elapsed >= 0.5 or peer_data["last_time"] == 0:
                            if peer_data["last_time"] > 0:
                                byte_diff = total_sent - peer_data["last_bytes"]
                                peer_data["current_speed"] = byte_diff / elapsed
                            peer_data["last_time"] = now
                            peer_data["last_bytes"] = total_sent
                            
                            # Aggregate totals across all peers for UI
                            aggregate_speed = sum(p.get("current_speed", 0) for p in self.peers.values())
                            
                            self.progress_callback(total_sent, total_size, aggregate_speed, i + 1, len(self.files))

            # 4. FILE_END
            end_msg = {
                "type": "file_end",
                "name": name,
                "hash": file_hash.hexdigest()
            }
            channel.send(json.dumps(end_msg))
            self._log(f"[{peer_sid}] ✅ {name} gönderildi ({file_sent} bytes)")

        # 5. TRANSFER_END
        channel.send(json.dumps({"type": "transfer_end"}))
        self._log(f"[{peer_sid}] Transfer tamamlandı!")
        peer_data["status"] = "done"

    def send_files(self):
        """Deprecated: files are now sent per-peer inside handle_offer -> _send_files_async(peer_sid)"""
        self._log("send_files() called — transfers are now initiated per-peer automatically.")

    def wait_for_connection(self, timeout=30) -> bool:
        """Block until DataChannel connects or timeout"""
        return self._connected_event.wait(timeout=timeout)


class WebRTCReceiver:
    """
    Alıcı tarafı — SDP offer oluşturur, dosyaları DataChannel üzerinden alır.
    """

    def __init__(self):
        self.pc: Optional[RTCPeerConnection] = None
        self.channel = None
        self.status = "idle"
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stopped = False # Added for clean shutdown
        self._pause_event = asyncio.Event() 
        self._pause_event.set()  # Not paused by default
        
        self.log_callback: Optional[Callable] = None
        self.progress_callback: Optional[Callable] = None
        self.on_auth_failed: Optional[Callable] = None
        self.password: Optional[str] = None
        self.save_path: Optional[str] = None

        # Transfer state
        self._file_list: List[Dict] = []
        self._current_file = None
        self._current_file_handle = None
        self._current_hash = None
        self._bytes_received = 0
        self._total_size = 0
        self._files_received = 0
        self._total_files = 0
        
        # Events
        self._connected_event = threading.Event()
        self._transfer_done_event = threading.Event()
        self._file_list_event = threading.Event()
        self._offer_ready = threading.Event()
        self._offer_sdp: Optional[str] = None
        self.on_file_list: Optional[Callable] = None
        # Speed tracking
        self._speed_last_time = 0.0
        self._speed_last_bytes = 0
        self._current_speed = 0.0

    def _log(self, msg):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def setup_signaling(self, signaling_client):
        """Attach signaling client"""
        self.signaling = signaling_client
        self.signaling.on_answer = self.handle_signaling_answer
        self.signaling.on_ice = self.handle_signaling_ice

    async def connect_via_signaling(self):
        """Initiate connection via signaling server"""
        # Create Offer
        self.status = "connecting"
        self.pc = RTCPeerConnection(configuration=_get_rtc_config())
        
        # Create DataChannel
        self.channel = self.pc.createDataChannel("fileTransfer", ordered=True)
        self._setup_datachannel(self.channel)
        
        # Create Offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        # Send Offer via Signaling
        await self.signaling.send_offer(self.pc.localDescription.sdp)
        self._log("Offer sent to signaling server")

    async def handle_signaling_answer(self, sdp, sender_sid):
        """Handle answer from signaling server"""
        self._log(f"Answer received from {sender_sid}")
        answer = RTCSessionDescription(sdp=sdp, type="answer")
        await self.pc.setRemoteDescription(answer)
        self._log("Remote description set (Answer)")

    async def handle_signaling_ice(self, candidate, sender_sid):
        pass

    def _setup_datachannel(self, channel):
        @channel.on("open")
        def on_open():
            self._log("DataChannel AÇIK! (Signaling)")
            self.status = "connected"
            self._connected_event.set()
            channel.send(json.dumps({"type": "ready"}))

        @channel.on("message")
        def on_message(message):
            self._handle_message(message)

    def start(self):
        """Start the async event loop in a background thread"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def wait_until_ready(self, timeout=5.0):
        """Wait until the async loop is initialized"""
        start = time.time()
        while self._loop is None:
            if time.time() - start > timeout:
                raise RuntimeError("WebRTC loop failed to start")
            time.sleep(0.01)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Clean shutdown"""
        if self._stopped:
            return
            
        self._stopped = True
        self._pause_event.set() # Unpause any waiting loops
        if self._current_file_handle:
            try:
                self._current_file_handle.close()
            except:
                pass
                
        async def _shutdown():
            if self.pc:
                try:
                    await self.pc.close()
                except: pass
                
            # Cancel all running tasks except this shutdown task
            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks(self._loop) if t is not current_task]
            for task in tasks:
                task.cancel()
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
            self._loop.stop()

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            
        self.status = "idle"
        self._current_speed = 0.0

    def pause(self):
        """Send pause signal to sender"""
        if self.channel and self.channel.readyState == "open" and self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self.channel.send, json.dumps({"type": "PAUSE"}))
                self._pause_event.clear()
                self._log("⏸️ Duraklatma isteği gönderildi")
            except: pass

    def resume(self):
        """Send resume signal to sender"""
        if self.channel and self.channel.readyState == "open" and self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self.channel.send, json.dumps({"type": "RESUME"}))
                self._pause_event.set()
                self._log("▶️ Devam etme isteği gönderildi")
            except: pass

    def request_download(self, filenames: list):
        """Send download request with specific filenames and their existing sizes for resume"""
        if self.channel and self.channel.readyState == "open" and self._loop and self._loop.is_running():
            try:
                offsets = {}
                save_dir = self.save_path or "."
                for name in filenames:
                    target_path = os.path.join(save_dir, name)
                    if os.path.exists(target_path):
                        offsets[name] = os.path.getsize(target_path)
                
                msg = {
                    "type": "DOWNLOAD_REQUEST",
                    "files": filenames,
                    "offsets": offsets
                }
                self._loop.call_soon_threadsafe(self.channel.send, json.dumps(msg))
                self._log(f"İndirme isteği gönderildi: {len(filenames)} dosya (Resume: {len(offsets)} dosya)")
            except Exception as e:
                self._log(f"İstek gönderilemedi: {e}")

    async def create_offer(self) -> dict:
        """
        SDP offer oluştur ve döndür.
        
        Returns:
            {"sdp": offer_sdp, "type": "offer"}
        """
        self.pc = RTCPeerConnection(configuration=_get_rtc_config())

        # Create DataChannel
        self.channel = self.pc.createDataChannel("fileTransfer", ordered=True)

        @self.channel.on("open")
        def on_open():
            self._log("DataChannel açıldı!")
            self.status = "connected"
            self._connected_event.set()
            # Send auth if password is set, else ready
            if self.password:
                self.channel.send(json.dumps({"type": "auth", "password": self.password}))
            else:
                self.channel.send(json.dumps({"type": "ready"}))

        @self.channel.on("message")
        def on_message(message):
            self._handle_message(message)

        @self.pc.on("connectionstatechange")
        async def on_state_change():
            self._log(f"Bağlantı durumu: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                self.status = "failed"
                self._connected_event.set()
                self._transfer_done_event.set()
            elif self.pc.connectionState == "closed":
                self.status = "idle"

        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        self._log("SDP offer oluşturuldu")
        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        }

    def create_offer_sync(self) -> dict:
        """Synchronous wrapper for create_offer"""
        if not self._loop:
            self.start()
            time.sleep(0.5)
        
        future = asyncio.run_coroutine_threadsafe(
            self.create_offer(), self._loop
        )
        return future.result(timeout=WEBRTC_TIMEOUT)

    async def set_answer(self, answer_sdp: str, answer_type: str = "answer"):
        """Set the remote SDP answer from the sender"""
        answer = RTCSessionDescription(sdp=answer_sdp, type=answer_type)
        await self.pc.setRemoteDescription(answer)
        self._log("SDP answer alındı, P2P bağlantısı kuruluyor...")

    def set_answer_sync(self, answer_sdp: str):
        """Synchronous wrapper for set_answer"""
        future = asyncio.run_coroutine_threadsafe(
            self.set_answer(answer_sdp), self._loop
        )
        future.result(timeout=WEBRTC_TIMEOUT)

    def _handle_message(self, message):
        """Handle incoming DataChannel messages"""
        # Text message (Control)
        if isinstance(message, str):
            try:
                data = json.loads(message)
                if data.get("type") == "PAUSE":
                    self._log("⏸️ Gönderici tarafından duraklatıldı")
                    self._pause_event.clear()
                    return
                elif data.get("type") == "RESUME":
                    self._log("▶️ Gönderici tarafından devam ettirildi")
                    self._pause_event.set()
                    return
                elif data.get("type") == "STOPPED":
                    self._log("🛑 Gönderici transferi durdurdu.")
                    self.status = "stopped"
                    self._transfer_done_event.set() # Release waiters
                    return
                
                msg_type = data.get("type")

                if msg_type == "auth_failed":
                    self._log("🔒 Parola hatalı!")
                    self.status = "auth_failed"
                    if self.on_auth_failed:
                        self.on_auth_failed()
                    self.stop()
                    return
                elif msg_type == "auth_success":
                    self._log("🔓 Kimlik doğrulama başarılı!")
                    return
                elif msg_type == "auth_required":
                    self._log("❓ Gönderici parola istiyor ama biz göndermedik!")
                    self.status = "auth_failed"
                    if self.on_auth_failed:
                        self.on_auth_failed()
                    self.stop()
                    return

                if msg_type == "file_list":
                    self._file_list = data["files"]
                    self._total_size = data["total_size"]
                    self._total_files = len(self._file_list)
                    self._log(f"Dosya listesi alındı: {self._total_files} dosya, toplam {self._total_size} bytes")
                    self._file_list_event.set()
                    if self.on_file_list:
                        self.on_file_list(self._file_list)

                elif msg_type == "file_start":
                    name = data["name"]
                    size = data["size"]
                    index = data["index"]
                    total = data["total"]
                    offset = data.get("offset", 0)
                    
                    # Security Check
                    target_path = os.path.join(self.save_path or ".", name)
                    if not is_safe_path(self.save_path or ".", target_path):
                        self._log(f"⚠️ GÜVENLİK UYARISI: Geçersiz dosya yolu '{name}'. Atlanıyor.")
                        self._current_file = None # Reset current file state
                        self._current_file_handle = None
                        self._current_hash = None
                        return

                    os.makedirs(os.path.dirname(target_path) if os.path.dirname(target_path) else ".", exist_ok=True)
                    
                    if offset > 0 and os.path.exists(target_path):
                        self._current_file_handle = open(target_path, "ab")
                        self._bytes_received += offset # Ensure overall progress includes what we already have
                        self._log(f"Devam ediliyor: {name} ({offset} bytes atlandı)")
                    else:
                        self._current_file_handle = open(target_path, "wb")
                        self._log(f"Alınıyor: {name} ({index+1}/{total})")
                        
                    self._current_file = {"name": name, "size": size} # Keep this for progress tracking
                    self._current_hash = hashlib.sha256()

                elif msg_type == "file_end":
                    if self._current_file_handle:
                        self._current_file_handle.close()
                        self._current_file_handle = None
                    
                    # Verify hash
                    expected_hash = data.get("hash", "")
                    actual_hash = self._current_hash.hexdigest() if self._current_hash else ""
                    
                    if expected_hash and expected_hash == actual_hash:
                        self._log(f"✅ {data['name']} alındı (hash OK)")
                    elif expected_hash:
                        self._log(f"⚠️ {data['name']} alındı (hash UYUMSUZ!)")
                    else:
                        self._log(f"✅ {data['name']} alındı")
                    
                    self._files_received += 1
                    self._current_file = None
                    self._current_hash = None

                elif msg_type == "transfer_end":
                    self._log(f"Transfer tamamlandı! {self._files_received} dosya alındı.")
                    self.status = "done"
                    self._transfer_done_event.set()

            except json.JSONDecodeError:
                pass

        elif isinstance(message, bytes):
            # Binary chunk data
            if self._current_file_handle:
                self._current_file_handle.write(message)
                if self._current_hash:
                    self._current_hash.update(message)
                
                self._bytes_received += len(message)

                # Progress callback with speed
                if self.progress_callback:
                    now = time.time()
                    elapsed = now - self._speed_last_time
                    if elapsed >= 0.3:
                        byte_diff = self._bytes_received - self._speed_last_bytes
                        self._current_speed = byte_diff / elapsed
                        self._speed_last_time = now
                        self._speed_last_bytes = self._bytes_received
                    elif self._speed_last_time == 0:
                        self._speed_last_time = now
                        self._speed_last_bytes = self._bytes_received
                    self.progress_callback(
                        self._bytes_received,
                        self._total_size,
                        self._current_speed,
                        self._files_received + 1,
                        self._total_files
                    )

    def wait_for_connection(self, timeout=30) -> bool:
        """Block until P2P connection is established"""
        return self._connected_event.wait(timeout=timeout)

    def wait_for_transfer(self, timeout=None) -> bool:
        """Block until file transfer completes"""
        return self._transfer_done_event.wait(timeout=timeout)


import uuid
import requests

class SignalingClient:
    """
    HTTP Polling based Signaling Client for P2P connection
    """
    def __init__(self, loop, server_url=SIGNALING_SERVER_URL):
        self.server_url = server_url
        self.room_id = None
        self.sid = str(uuid.uuid4())
        self._loop = loop
        self.on_peer_joined = None
        self.on_offer = None
        self.on_answer = None
        self.on_ice = None
        self._polling_task = None
        self._is_closing = False
        import aiohttp # Ensure it's available for the async loop
        self.aiohttp = aiohttp

    async def connect(self, room_id):
        self.room_id = room_id
        self._is_closing = False
        
        def _connect():
            try:
                # Increase timeout to 60 to allow Render free tier servers to wake up
                resp = requests.post(f"{self.server_url}/join", json={'room': self.room_id, 'sid': self.sid}, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                
                if 'peers' in data and data['peers']:
                     # We can trigger peer_joined for existing peers if we want
                     pass
            except Exception as e:
                raise RuntimeError(f"HTTP Signaling Join failed: {e}")
                
        # Run blocking join in executor
        await self._loop.run_in_executor(None, _connect)
        print(f"[Signaling] Joined Room (HTTP): {self.room_id} as {self.sid}")
        
        # Start async polling loop
        self._polling_task = self._loop.create_task(self._poll_loop())

    async def _poll_loop(self):
        # Use ThreadedResolver to avoid aiodns/pycares DNS failures on Windows
        resolver = self.aiohttp.resolver.ThreadedResolver()
        connector = self.aiohttp.TCPConnector(resolver=resolver)
        async with self.aiohttp.ClientSession(connector=connector) as session:
            while not self._is_closing:
                try:
                    async with session.get(f"{self.server_url}/poll", params={'sid': self.sid}, timeout=35) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for msg in data.get('messages', []):
                                await self._handle_message(msg)
                except asyncio.TimeoutError:
                    continue # Expected, just poll again
                except asyncio.CancelledError:
                    break # Task was cancelled for shutdown
                except Exception as e:
                    if not self._is_closing:
                        print(f"[Signaling] Poll error: {e}")
                        await asyncio.sleep(2) # Backoff

    async def _handle_message(self, msg):
        msg_type = msg.get('type')
        if msg_type == 'peer_joined':
             print(f"[Signaling] Peer joined: {msg.get('sid')}")
             if self.on_peer_joined:
                 await self.on_peer_joined(msg.get('sid'))
        elif msg_type == 'offer':
             if self.on_offer:
                 await self.on_offer(msg.get('data'), msg.get('sender'))
        elif msg_type == 'answer':
             if self.on_answer:
                 await self.on_answer(msg.get('data'), msg.get('sender'))
        elif msg_type == 'ice':
             if self.on_ice:
                 await self.on_ice(msg.get('data'), msg.get('sender'))

    async def _post_signal(self, payload):
        def _post():
            try:
                requests.post(f"{self.server_url}/signal", json=payload, timeout=20)
            except Exception as e:
                print(f"[Signaling] Post error: {e}")
        await self._loop.run_in_executor(None, _post)

    async def send_offer(self, sdp, target_sid=None):
        await self._post_signal({
            'sender': self.sid,
            'type': 'offer',
            'data': sdp,
            'target': target_sid,
            'room': self.room_id
        })

    async def send_answer(self, sdp, target_sid=None):
        await self._post_signal({
            'sender': self.sid,
            'type': 'answer',
            'data': sdp,
            'target': target_sid,
            'room': self.room_id
        })

    async def send_ice(self, candidate, target_sid=None):
        await self._post_signal({
            'sender': self.sid,
            'type': 'ice',
            'data': candidate,
            'target': target_sid,
            'room': self.room_id
        })
    
    async def close(self):
        self._is_closing = True
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
