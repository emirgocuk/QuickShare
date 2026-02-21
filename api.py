import os
import threading
import time
import random
import string
import asyncio
import webview

from utils import format_size, format_speed
from server import set_shared_files, run_server, transfer_monitor
import server as srv
from webrtc_manager import WebRTCSender, SignalingClient
from tunnel_manager import TunnelManager
from config import (CF_TUNNEL_TOKEN, SIGNALING_SERVER_URL, 
                    load_config, save_config)
from downloader import Downloader

class QuickShareAPI:
    def __init__(self, window_ref=None):
        self.window = window_ref
        self.selected_files = []
        self.webrtc_sender = None
        self.tunnel_manager = None
        self.server_thread = None
        self.is_sharing = False
        
        # Stats monitoring thread
        self.stats_thread_running = False

    def _get_file_dicts(self):
        """Prepare file list for the frontend"""
        res = []
        for path in self.selected_files:
            is_folder = os.path.isdir(path)
            try:
                size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, _, filenames in os.walk(path) for filename in filenames) if is_folder else os.path.getsize(path)
            except OSError:
                size = 0
            
            res.append({
                "name": os.path.basename(path),
                "path": path,
                "is_folder": is_folder,
                "size": format_size(size),
                "status": "Hazır"
            })
        return res

    # --- UI Callbacks for File Selection (using pywebview native dialogs) ---

    def select_files(self):
        if not self.window:
            return self._get_file_dicts()
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True
        )
        if result:
            for p in result:
                p_clean = str(p).replace("/", "\\")
                if p_clean not in self.selected_files:
                    self.selected_files.append(p_clean)
        return self._get_file_dicts()

    def select_folder(self):
        if not self.window:
            return self._get_file_dicts()
        result = self.window.create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result:
            p_clean = str(result[0]).replace("/", "\\")
            if p_clean not in self.selected_files:
                self.selected_files.append(p_clean)
        return self._get_file_dicts()

    def add_files_from_drop(self, paths):
        if paths:
            for p in paths:
                p_clean = p.replace("/", "\\")
                if p_clean not in self.selected_files:
                     self.selected_files.append(p_clean)
        return self._get_file_dicts()

    def clear_files(self):
        self.selected_files = []
        return []

    # --- Receive / Connect Logic ---

    def connect_to_peer(self, code_or_url):
        """Connect to a sender via P2P code or cloud URL"""
        code_or_url = str(code_or_url).strip()
        if not code_or_url:
            return {"success": False, "error": "Lütfen bir kod veya link girin."}
        
        # Detect if it's a URL or a P2P code
        if code_or_url.startswith("http://") or code_or_url.startswith("https://"):
            # Cloud URL mode - get file list via HTTP
            return self._connect_cloud(code_or_url)
        else:
            # P2P code mode
            return self._connect_p2p(code_or_url)
    
    def _connect_cloud(self, url):
        """Connect to a cloud share URL and retrieve file list"""
        try:
            downloader = Downloader()
            remote_files = downloader.get_file_list(url)
            file_list = []
            for f in remote_files:
                file_list.append({
                    "name": f.get("name", "unknown"),
                    "size": format_size(f.get("size", 0)),
                    "raw_size": f.get("size", 0)
                })
            return {
                "success": True,
                "type": "cloud",
                "url": url,
                "files": file_list
            }
        except Exception as e:
            return {"success": False, "error": f"Bağlantı hatası: {str(e)}"}
    
    def _connect_p2p(self, room_id):
        """Connect to a P2P room via signaling server"""
        try:
            return {
                "success": True,
                "type": "p2p",
                "code": room_id,
                "message": f"P2P bağlantısı kuruluyor... Oda: {room_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"P2P bağlantı hatası: {str(e)}"}

    def select_download_folder(self):
        """Let user pick a download directory via native dialog"""
        if not self.window:
            return {"success": False, "error": "Pencere bulunamadı."}
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            return {"success": True, "path": str(result[0])}
        return {"success": False, "error": "Klasör seçilmedi."}

    # --- Settings ---

    def get_settings(self):
        """Return current settings for the settings page"""
        from config import (CF_TUNNEL_TOKEN, CF_TUNNEL_URL, 
                          DUCKDNS_DOMAIN, DUCKDNS_TOKEN, USE_DUCKDNS,
                          SIGNALING_SERVER_URL, DEBUG)
        return {
            "cf_tunnel_token": CF_TUNNEL_TOKEN,
            "cf_tunnel_url": CF_TUNNEL_URL,
            "duckdns_domain": DUCKDNS_DOMAIN,
            "duckdns_token": DUCKDNS_TOKEN,
            "use_duckdns": USE_DUCKDNS,
            "signaling_url": SIGNALING_SERVER_URL,
            "debug": DEBUG
        }
    
    def save_settings(self, settings):
        """Save settings from the frontend"""
        try:
            save_config(
                cf_token=settings.get("cf_tunnel_token", ""),
                cf_url=settings.get("cf_tunnel_url", ""),
                duckdns_domain=settings.get("duckdns_domain", ""),
                duckdns_token=settings.get("duckdns_token", ""),
                use_duckdns=settings.get("use_duckdns", False)
            )
            return {"success": True, "message": "Ayarlar kaydedildi."}
        except Exception as e:
            return {"success": False, "error": f"Kayıt hatası: {str(e)}"}

    # --- Core Sharing Logic ---
    
    def _start_stats_monitor(self):
        """Thread to constantly evaluate JS to update stats UI"""
        if self.stats_thread_running: return
        self.stats_thread_running = True
        
        def monitor_loop():
            while self.stats_thread_running and self.is_sharing:
                stats = transfer_monitor.get_stats()
                speed_str = format_speed(stats['speed'])
                sent_str = format_size(stats['total_sent'])
                
                # Check bounds / evaluate JS
                if self.window:
                    try:
                        self.window.evaluate_js(f"window.updateStats('{speed_str}', '{sent_str}')")
                    except Exception:
                        pass
                time.sleep(1)
                
        threading.Thread(target=monitor_loop, daemon=True).start()

    def start_direct_share(self):
        """Starts WebRTC P2P sharing logic"""
        if not self.selected_files: return {"success": False, "error": "Lütfen önce dosya seçin."}
        if self.is_sharing: return {"success": False, "error": "Zaten bir paylaşım aktif."}
        
        self.is_sharing = True
        set_shared_files(self.selected_files)
        
        room_id = ''.join(random.choices(string.digits, k=6))
        
        # Start WebRTC thread
        self.webrtc_sender = WebRTCSender()
        self.webrtc_sender.start()
        self.webrtc_sender.wait_until_ready()
        
        # Build file list
        from utils import get_files_from_directory
        file_list = []
        for path in self.selected_files:
            if os.path.isfile(path):
                file_list.append({"name": os.path.basename(path), "path": path, "size": os.path.getsize(path)})
            elif os.path.isdir(path):
                for f in get_files_from_directory(path):
                    rel = os.path.relpath(f, path)
                    file_list.append({"name": rel, "path": f, "size": os.path.getsize(f)})
                    
        self.webrtc_sender.set_files(file_list)
        signaling = SignalingClient(self.webrtc_sender._loop)
        
        # Helper to run async signalling connection
        async def setup_async():
            try:
                await signaling.connect(room_id)
                self.webrtc_sender.setup_signaling(signaling)
            except Exception as e:
                print(f"Sinyal sunucusu hatası: {e}")
                self.stop_share()
                if self.window: self.window.evaluate_js(f"alert('Sinyal sunucusu hatası: {e}')")
                
        asyncio.run_coroutine_threadsafe(setup_async(), self.webrtc_sender._loop)
        
        # Register Progress Callback
        def sender_progress(sent, total, speed, current_file_idx, total_files):
             transfer_monitor.total_sent = sent
             transfer_monitor.total_size = total
             transfer_monitor.current_speed = speed
             pass
             
        self.webrtc_sender.progress_callback = sender_progress
        self._start_stats_monitor()
        
        return {
            "success": True, 
            "type": "p2p", 
            "code": room_id
        }

    def start_cloud_share(self):
         """Starts HTTP Cloudflare Tunnel logic"""
         if not self.selected_files: return {"success": False, "error": "Lütfen önce dosya seçin."}
         if self.is_sharing: return {"success": False, "error": "Zaten bir paylaşım aktif."}
            
         self.is_sharing = True
         set_shared_files(self.selected_files)
         
         # Start Flask Background
         if not self.server_thread or not self.server_thread.is_alive():
             self.server_thread = threading.Thread(target=run_server, daemon=True)
             self.server_thread.start()
             time.sleep(1) # wait for boot
         
         # Start tunnel
         self.tunnel_manager = TunnelManager()
         self.tunnel_manager.start(token=CF_TUNNEL_TOKEN if CF_TUNNEL_TOKEN else None)
         
         # Wait for URL
         timeout = 30
         start_time = time.time()
         public_url = None
         
         while time.time() - start_time < timeout:
             url = self.tunnel_manager.get_url()
             if url:
                 public_url = url
                 break
             time.sleep(1)
             
         if not public_url:
             self.stop_share()
             return {"success": False, "error": "Tünel URL'i alınamadı. (Zaman aşımı)"}
             
         self._start_stats_monitor()
         
         return {
            "success": True, 
            "type": "cloud", 
            "url": public_url
         }

    def stop_share(self):
        print("[API] Stop sharing called")
        self.is_sharing = False
        self.stats_thread_running = False
        
        if self.tunnel_manager:
            self.tunnel_manager.stop()
            self.tunnel_manager = None
            
        if self.webrtc_sender:
            self.webrtc_sender.stop()
            self.webrtc_sender = None
            srv.webrtc_sender = None
            
        return {"success": True}
