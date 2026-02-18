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
from typing import Optional, Callable, List, Dict
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from config import WEBRTC_CHUNK_SIZE, ICE_SERVERS, WEBRTC_TIMEOUT


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
        self.pc: Optional[RTCPeerConnection] = None
        self.channel = None
        self.files: List[Dict] = []  # [{name, path, size}]
        self.status = "idle"  # idle, waiting, connected, transferring, done
        self._transfer_event = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.log_callback: Optional[Callable] = None
        self.progress_callback: Optional[Callable] = None
        # Track connection state
        self._connected_event = threading.Event()
        self._receiver_ready = threading.Event()
        # Speed tracking
        self._speed_last_time = 0.0
        self._speed_last_bytes = 0
        self._current_speed = 0.0
        self._stopped = False

    def _log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def set_files(self, file_list: List[Dict]):
        """Set the file list to send — [{name, path, size}]"""
        self.files = file_list

    def start(self):
        """Start the async event loop in a background thread"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Clean shutdown"""
        self._stopped = True
        self._pause_event.set()  # Unpause to let loops exit
        if self.pc and self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self.pc.close(), self._loop)
                future.result(timeout=5)
            except:
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.status = "idle"

    def pause(self):
        """Pause transfer"""
        if not self._stopped:
            self._pause_event.clear()
            self._log("⏸️ Transfer duraklatıldı")
            # Send pause signal to receiver
            if self.channel and self.channel.readyState == "open":
                try:
                    self.channel.send(json.dumps({"type": "PAUSE"}))
                except: pass

    def resume(self):
        """Resume transfer"""
        if not self._stopped:
            self._pause_event.set()
            self._log("▶️ Transfer devam ediyor")
            # Send resume signal to receiver
            if self.channel and self.channel.readyState == "open":
                try:
                    self.channel.send(json.dumps({"type": "RESUME"}))
                except: pass

    async def handle_offer(self, offer_sdp: str, offer_type: str = "offer") -> dict:
        """
        Alıcıdan gelen SDP offer'ı işle ve answer döndür.
        
        Args:
            offer_sdp: SDP offer string
            offer_type: SDP type (always "offer")
            
        Returns:
            {"sdp": answer_sdp, "type": "answer"}
        """
        self.pc = RTCPeerConnection(configuration=_get_rtc_config())
        self.status = "waiting"

        @self.pc.on("datachannel")
        def on_datachannel(channel):
            self.channel = channel
            self._log("DataChannel bağlandı!")
            self.status = "connected"
            self._connected_event.set()

            @channel.on("message")
            def on_message(message):
                # Receiver'dan gelen kontrol mesajları
                try:
                    data = json.loads(message)
                    if data.get("type") == "PAUSE":
                        self._log("⏸️ Alıcı tarafından duraklatıldı")
                        self._pause_event.clear()
                    elif data.get("type") == "RESUME":
                        self._log("▶️ Alıcı tarafından devam ettirildi")
                        self._pause_event.set()
                    elif data.get("type") == "ready":
                        self._receiver_ready.set()
                        self._log("Alıcı hazır, transfer başlıyor...")
                except json.JSONDecodeError:
                    self._log(f"Alıcıdan bilinmeyen mesaj: {message}")
                except Exception as e:
                    self._log(f"Alıcı mesajı işlenirken hata: {e}")


        @self.pc.on("connectionstatechange")
        async def on_state_change():
            self._log(f"Bağlantı durumu: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                self.status = "failed"
                self._connected_event.set()  # Unblock waiters
            elif self.pc.connectionState == "closed":
                self.status = "idle"

        # Set remote description (the offer)
        offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
        await self.pc.setRemoteDescription(offer)

        # Create answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        self._log("SDP answer oluşturuldu")
        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        }

    def handle_offer_sync(self, offer_sdp: str) -> dict:
        """Synchronous wrapper for handle_offer"""
        if not self._loop:
            self.start()
            time.sleep(0.5)  # Wait for loop to start
        
        future = asyncio.run_coroutine_threadsafe(
            self.handle_offer(offer_sdp), self._loop
        )
        return future.result(timeout=WEBRTC_TIMEOUT)

    async def _send_files_async(self):
        """Send all files over the DataChannel"""
        if not self.channel:
            self._log("DataChannel bağlı değil!")
            return

        self.status = "transferring"

        # 1. Send file list
        file_list_msg = {
            "type": "file_list",
            "files": [{"name": f["name"], "size": f["size"]} for f in self.files],
            "total_size": sum(f["size"] for f in self.files)
        }
        self.channel.send(json.dumps(file_list_msg))
        self._log(f"Dosya listesi gönderildi: {len(self.files)} dosya")

        # Wait for receiver to be ready
        total_sent = 0
        total_size = sum(f["size"] for f in self.files)

        for i, file_info in enumerate(self.files):
            name = file_info["name"]
            path = file_info["path"]
            size = file_info["size"]

            # 2. FILE_START
            start_msg = {
                "type": "file_start",
                "name": name,
                "size": size,
                "index": i,
                "total": len(self.files)
            }
            self.channel.send(json.dumps(start_msg))

            # 3. Send chunks
            file_hash = hashlib.sha256()
            file_sent = 0

            with open(path, "rb") as f:
                while True:
                    # Check pause
                    await self._pause_event.wait()
                    
                    if self._stopped:
                        break
                        
                    chunk = f.read(WEBRTC_CHUNK_SIZE)
                    if not chunk:
                        break

                    # Wait for buffer to drain if needed
                    while self.channel.bufferedAmount > WEBRTC_CHUNK_SIZE * 16:
                        await asyncio.sleep(0.01)

                    self.channel.send(chunk)
                    file_hash.update(chunk)
                    file_sent += len(chunk)
                    total_sent += len(chunk)

                    # Progress callback with speed
                    if self.progress_callback:
                        now = time.time()
                        elapsed = now - self._speed_last_time
                        if elapsed >= 0.3:
                            byte_diff = total_sent - self._speed_last_bytes
                            self._current_speed = byte_diff / elapsed
                            self._speed_last_time = now
                            self._speed_last_bytes = total_sent
                        elif self._speed_last_time == 0:
                            self._speed_last_time = now
                            self._speed_last_bytes = total_sent
                        self.progress_callback(total_sent, total_size, self._current_speed, i + 1, len(self.files))

            # 4. FILE_END
            end_msg = {
                "type": "file_end",
                "name": name,
                "hash": file_hash.hexdigest()
            }
            self.channel.send(json.dumps(end_msg))
            self._log(f"✅ {name} gönderildi ({file_sent} bytes)")

        # 5. TRANSFER_END
        self.channel.send(json.dumps({"type": "transfer_end"}))
        self._log("Transfer tamamlandı!")
        self.status = "done"

    def send_files(self):
        """Start sending files (call after connection is established)"""
        if not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._send_files_async(), self._loop)

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
        self._offer_ready = threading.Event()
        self._offer_sdp: Optional[str] = None
        # Speed tracking
        self._speed_last_time = 0.0
        self._speed_last_bytes = 0
        self._current_speed = 0.0

    def _log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def start(self):
        """Start the async event loop in a background thread"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Clean shutdown"""
        self._stopped = True
        self._pause_event.set() # Unpause any waiting loops
        if self._current_file_handle:
            try:
                self._current_file_handle.close()
            except:
                pass
        if self.pc and self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self.pc.close(), self._loop)
                future.result(timeout=5)
            except:
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.status = "idle"

    def pause(self):
        """Send pause signal to sender"""
        if self.channel and self.channel.readyState == "open":
            try:
                self.channel.send(json.dumps({"type": "PAUSE"}))
                self._pause_event.clear()
                self._log("⏸️ Duraklatma isteği gönderildi")
            except: pass

    def resume(self):
        """Send resume signal to sender"""
        if self.channel and self.channel.readyState == "open":
            try:
                self.channel.send(json.dumps({"type": "RESUME"}))
                self._pause_event.set()
                self._log("▶️ Devam etme isteği gönderildi")
            except: pass

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
            # Tell sender we're ready
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
                
                msg_type = data.get("type")

                if msg_type == "file_list":
                    self._file_list = data["files"]
                    self._total_size = data["total_size"]
                    self._total_files = len(self._file_list)
                    self._log(f"Dosya listesi alındı: {self._total_files} dosya, toplam {self._total_size} bytes")

                elif msg_type == "file_start":
                    name = data["name"]
                    size = data["size"]
                    self._current_file = {"name": name, "size": size}
                    self._current_hash = hashlib.sha256()
                    
                    # Create save path
                    save_file = os.path.join(self.save_path or ".", name)
                    os.makedirs(os.path.dirname(save_file) if os.path.dirname(save_file) else ".", exist_ok=True)
                    self._current_file_handle = open(save_file, "wb")
                    self._log(f"Alınıyor: {name} ({size} bytes)")

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
