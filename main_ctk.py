"""
QuickShare Main Application - Modern UI with Sidebar & Drag-Drop
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import sys
import time
import os
import webbrowser
from typing import List, Optional

from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE
from utils import format_size, format_speed, format_time, validate_url, calculate_total_size
from server import set_shared_files, run_server, transfer_monitor
from tunnel_manager import TunnelManager
from downloader import Downloader
from webrtc_manager import WebRTCSender, WebRTCReceiver

# CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")



class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    """CustomTkinter + TkinterDnD Wrapper"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class QuickShareApp(Tk):
    """QuickShare Modern UI Application"""
    
    def __init__(self):
        super().__init__()
        
        # Window Setup
        self.title(WINDOW_TITLE)
        self.geometry(f"{800}x{600}")  # Slightly larger for sidebar
        self.minsize(700, 500)
        
        # State
        self.selected_files: List[str] = []
        self.tunnel_manager: Optional[TunnelManager] = None
        self.webrtc_sender: Optional[WebRTCSender] = None
        self.use_p2p = False
        self.server_thread: Optional[threading.Thread] = None
        self.downloader: Optional[Downloader] = None
        self.download_url: Optional[str] = None
        self.remote_files: List[dict] = []
        self.is_sharing = False
        
        # Grid Layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_pages()
        
        # Start at Home
        self.select_frame("home")
        
    def setup_sidebar(self):
        """Create the sidebar navigation"""
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text=" QuickShare", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Navigation Buttons
        self.sidebar_button_home = ctk.CTkButton(
            self.sidebar_frame, text="🏠 Ana Sayfa", command=lambda: self.select_frame("home")
        )
        self.sidebar_button_home.grid(row=1, column=0, padx=20, pady=10)
        
        self.sidebar_button_send = ctk.CTkButton(
            self.sidebar_frame, text="📤 Gönder", command=lambda: self.select_frame("send")
        )
        self.sidebar_button_send.grid(row=2, column=0, padx=20, pady=10)
        
        self.sidebar_button_receive = ctk.CTkButton(
            self.sidebar_frame, text="📥 Al", command=lambda: self.select_frame("receive")
        )
        self.sidebar_button_receive.grid(row=3, column=0, padx=20, pady=10)
        
        # High Speed Toggle
        self.speed_switch = ctk.CTkSwitch(self.sidebar_frame, text="⚡ Doğrudan P2P", command=self.toggle_p2p_mode)
        self.speed_switch.grid(row=4, column=0, padx=20, pady=10, sticky="s")
        
        # Settings / Info at bottom
        self.sidebar_button_settings = ctk.CTkButton(
            self.sidebar_frame, text="⚙️ Ayarlar", command=lambda: self.select_frame("settings"),
            fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE")
        )
        self.sidebar_button_settings.grid(row=5, column=0, padx=20, pady=10)
        
        # Connection Status
        self.status_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="🔴 Çevrimdışı", 
            font=ctk.CTkFont(size=12),
            text_color="#ff5555"
        )
        self.status_label.grid(row=6, column=0, padx=20, pady=(0, 20))

    def setup_pages(self):
        """Initialize all page frames"""
        # Home Frame
        self.home_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_home_ui()
        
        # Send Frame
        self.send_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_send_ui()
        
        # Receive Frame
        self.receive_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_receive_ui()
        
        # Settings Frame
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_settings_ui()

    def select_frame(self, name):
        """Switch active frame"""
        # Reset button colors
        self.sidebar_button_home.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.sidebar_button_send.configure(fg_color=("gray75", "gray25") if name == "send" else "transparent")
        self.sidebar_button_receive.configure(fg_color=("gray75", "gray25") if name == "receive" else "transparent")
        
        # Hide all
        self.home_frame.grid_forget()
        self.send_frame.grid_forget()
        self.receive_frame.grid_forget()
        self.settings_frame.grid_forget()
        
        # Show selected
        if name == "home":
            self.home_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "send":
            self.send_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "receive":
            self.receive_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew")

    # --- UI SETUP METHODS ---
    
    def setup_home_ui(self):
        """Home Dashboard UI"""
        self.home_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.home_frame, text="QuickShare'e Hoşgeldiniz", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=40)
        
        # Status Cards
        status_frame = ctk.CTkFrame(self.home_frame)
        status_frame.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(status_frame, text="Son Durum", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkLabel(status_frame, text="Sistem Hazır ve Beklemede").pack(pady=(0, 20))
        
        # Quick Actions
        ctk.CTkButton(self.home_frame, text="Yeni Dosya Gönder", command=lambda: self.select_frame("send"), height=40).pack(pady=10)
        ctk.CTkButton(self.home_frame, text="Dosya Al", command=lambda: self.select_frame("receive"), height=40, fg_color="#06A77D", hover_color="#058c68").pack(pady=10)

    def setup_send_ui(self):
        """Send UI with Drag & Drop"""
        self.send_frame.grid_columnconfigure(0, weight=1)
        self.send_frame.grid_rowconfigure(1, weight=1)  # File list expands
        
        # Header
        header = ctk.CTkFrame(self.send_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        ctk.CTkLabel(header, text="Dosya Gönder", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        # Drag & Drop Area / File List
        self.file_list_frame = ctk.CTkScrollableFrame(self.send_frame, label_text="⬆️ Dosyaları Buraya Sürükleyin")
        self.file_list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        # Enable Drop
        self.file_list_frame.drop_target_register(DND_FILES)
        self.file_list_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        # Help Text inside list
        self.drop_help_label = ctk.CTkLabel(self.file_list_frame, text="Henüz dosya seçilmedi.\nDosyaları sürükleyip bırakın veya aşağıdaki butonları kullanın.", text_color="gray")
        self.drop_help_label.pack(pady=50)
        
        # Controls
        controls = ctk.CTkFrame(self.send_frame)
        controls.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkButton(controls, text="📁 Dosya Ekle", command=self.select_files).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(controls, text="📂 Klasör Ekle", command=self.select_folder).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(controls, text="🗑️ Temizle", command=self.clear_files, fg_color="#D62246", hover_color="#b11d3a", width=80).pack(side="left", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(controls, text="🚀 Paylaş", command=self.start_sharing, font=ctk.CTkFont(weight="bold"))
        self.start_btn.pack(side="right", padx=10, pady=10)
        
        # Active Sharing Info (Hidden initially)
        self.sharing_info_frame = ctk.CTkFrame(self.send_frame, fg_color="transparent")
        self.sharing_info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.sharing_info_frame.grid_remove() # Start hidden
        
        self.url_entry = ctk.CTkEntry(self.sharing_info_frame, placeholder_text="Paylaşım Linki...", state="readonly")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(self.sharing_info_frame, text="Kopyala", command=self.copy_url, width=80).pack(side="left")
        ctk.CTkButton(self.sharing_info_frame, text="Durdur", command=self.stop_sharing, fg_color="#D62246", hover_color="#b11d3a", width=80).pack(side="left", padx=10)

        # Stats
        self.stats_label = ctk.CTkLabel(self.sharing_info_frame, text="")
        self.stats_label.pack(side="bottom", pady=5)

    def setup_receive_ui(self):
        """Receive UI"""
        self.receive_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.receive_frame, text="Dosya Al", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=20, anchor="w", padx=20)
        
        # URL Input
        input_frame = ctk.CTkFrame(self.receive_frame)
        input_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(input_frame, text="Paylaşım Linki:").pack(anchor="w", padx=10, pady=(10, 5))
        
        url_box = ctk.CTkFrame(input_frame, fg_color="transparent")
        url_box.pack(fill="x", padx=10, pady=(0, 10))
        
        self.url_input = ctk.CTkEntry(url_box, placeholder_text="https://...")
        self.url_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_input.bind('<Return>', lambda e: self.connect_to_url())
        
        self.connect_btn = ctk.CTkButton(url_box, text="Bağlan", command=self.connect_to_url)
        self.connect_btn.pack(side="right")
        
        # Remote Files List
        self.remote_files_frame = ctk.CTkFrame(self.receive_frame)
        # Pack later when connected
        
        self.remote_files_tb = ctk.CTkTextbox(self.remote_files_frame, height=150, state="disabled")
        self.remote_files_tb.pack(fill="both", padx=10, pady=10)
        
        self.download_btn = ctk.CTkButton(self.remote_files_frame, text="📥 İndir", command=self.start_download, fg_color="#06A77D", hover_color="#058c68")
        self.download_btn.pack(fill="x", padx=10, pady=(0, 10))
        
        # Progress (Persistent)
        self.progress_frame = ctk.CTkFrame(self.receive_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Hazır - İndirme Bekleniyor")
        self.progress_label.pack()
        
        # Log Console
        self.log_label = ctk.CTkLabel(self.receive_frame, text="İşlem Logları:", anchor="w")
        self.log_label.pack(fill="x", padx=20, pady=(10, 0))
        
        self.log_box = ctk.CTkTextbox(self.receive_frame, height=100, state="disabled", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.pack(fill="x", padx=20, pady=5)

    def log_message(self, msg):
        """Log mesajını UI'a yaz"""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def setup_settings_ui(self):
        """Settings UI"""
        ctk.CTkLabel(self.settings_frame, text="Ayarlar", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=20)
        ctk.CTkLabel(self.settings_frame, text="(Gelecek sürümde eklenecek)").pack()
        
    # --- LOGIC ---

    def _download_thread(self, save_path):
        try:
            # Update Status to Receiving
            self.after(0, lambda: self.status_label.configure(text="🟢 Dosya İndiriliyor", text_color="#06A77D"))
            self.after(0, lambda: self.log_message(f"İndirme başlatıldı: {save_path}"))

            def cb(dl, total, speed, current_file_index, total_files):
                pct = (dl / total * 100) if total else 0
                self.after(0, self.update_progress, pct, speed, current_file_index, total_files)
            
            # Log callback for main thread
            def log_cb(msg):
                self.after(0, lambda: self.log_message(msg))
                
            self.downloader.download_all(self.download_url, save_path, cb, log_cb)
            self.after(0, self._on_download_complete, save_path)
        except Exception as e:
            # Bind e explicitly to lambda to avoid NameError
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Hata", err_msg))
            self.after(0, lambda: self.log_message(f"HATA: {err_msg}"))
            self.after(0, self._reset_download_ui)

    # --- WebRTC P2P Logic ---

    def toggle_p2p_mode(self):
        """Handle P2P Switch"""
        if self.speed_switch.get() == 1:
            self.use_p2p = True
            self.status_label.configure(text="🟢 P2P Aktif", text_color="#06A77D")
        else:
            self.use_p2p = False
            self.status_label.configure(text="🔴 P2P Kapalı", text_color="#ff5555")
            if self.webrtc_sender:
                self.webrtc_sender.stop()
                self.webrtc_sender = None

    def on_drop(self, event):
        """Handle Drag & Drop files"""
        # Event data returns strings like "{C:/path 1} C:/path2"
        # Need to parse this. tkinterdnd2 returns a list of paths
        files = self.TkdndVersion.splitlist(event.data)
        self.selected_files.extend(files)
        self.update_file_list()

    def select_files(self):
        files = filedialog.askopenfilenames()
        if files:
            self.selected_files.extend(files)
            self.update_file_list()
            
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_files.append(folder)
            self.update_file_list()
            
    def clear_files(self):
        self.selected_files = []
        self.update_file_list()
        
    def update_file_list(self):
        # Clear current list widgets
        for widget in self.file_list_frame.winfo_children():
            if widget != self.drop_help_label:
                widget.destroy()
        
        self.file_progress_labels = {}  # {filename: {'pct': label, 'bar': progressbar}}
        
        if not self.selected_files:
            self.drop_help_label.pack(pady=50)
            return
            
        self.drop_help_label.pack_forget()
        
        for f in self.selected_files:
            # Simple item row
            row = ctk.CTkFrame(self.file_list_frame, fg_color=("gray80", "gray20"))
            row.pack(fill="x", padx=5, pady=2)
            
            name = os.path.basename(f)
            if os.path.isdir(f):
                name = "📂 " + name
            else:
                name = "📄 " + name
                
            ctk.CTkLabel(row, text=name).pack(side="left", padx=10)
            
            # Percent Label
            pct_label = ctk.CTkLabel(row, text="0%", width=40)
            pct_label.pack(side="right", padx=10)
            
            self.file_progress_labels[os.path.basename(f)] = pct_label
            
    def start_sharing(self):
        if not self.selected_files:
            messagebox.showwarning("Uyarı", "Dosya seçiniz.")
            return

        self.start_btn.configure(state="disabled", text="Başlatılıyor...")
        threading.Thread(target=self._sharing_thread, daemon=True).start()

    def _sharing_thread(self):
        try:
            set_shared_files(self.selected_files)
            
            # Setup WebRTC sender if P2P is enabled
            if self.use_p2p:
                from server import webrtc_sender as _ws
                import server as srv
                from utils import create_file_info, get_files_from_directory
                
                self.webrtc_sender = WebRTCSender()
                self.webrtc_sender.start()
                self.webrtc_sender.log_callback = lambda msg: print(f"[P2P] {msg}")
                
                # Feed P2P progress into transfer_monitor for sender stats bar
                def sender_progress(sent, total, speed, current_file_idx, total_files):
                    transfer_monitor.total_sent = sent
                    transfer_monitor.total_size = total
                    if transfer_monitor.active_transfers == 0:
                        transfer_monitor.active_transfers = 1
                    # Update per-file progress
                    if self.webrtc_sender and self.webrtc_sender.files:
                        # Calculate how much of the current file has been sent
                        files = self.webrtc_sender.files
                        cumulative = 0
                        for idx, f_info in enumerate(files):
                            if cumulative + f_info['size'] >= sent:
                                # This is the file currently being sent
                                file_sent = sent - cumulative
                                fname = os.path.basename(f_info['name'])
                                transfer_monitor.update_file_progress(fname, file_sent, f_info['size'])
                                break
                            else:
                                # This file is complete
                                fname = os.path.basename(f_info['name'])
                                transfer_monitor.update_file_progress(fname, f_info['size'], f_info['size'])
                                cumulative += f_info['size']
                self.webrtc_sender.progress_callback = sender_progress
                
                # Build file list for WebRTC sender
                file_list = []
                for path in self.selected_files:
                    if os.path.isfile(path):
                        file_list.append({"name": os.path.basename(path), "path": path, "size": os.path.getsize(path)})
                    elif os.path.isdir(path):
                        for f in get_files_from_directory(path):
                            rel = os.path.relpath(f, path)
                            file_list.append({"name": rel, "path": f, "size": os.path.getsize(f)})
                
                self.webrtc_sender.set_files(file_list)
                srv.webrtc_sender = self.webrtc_sender
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            time.sleep(1)
            
            self.tunnel_manager = TunnelManager()
            url = self.tunnel_manager.start()
            
            self.after(0, self._on_sharing_started, url)
        except Exception as e:
            self.after(0, self._on_sharing_error, str(e))

    def _on_sharing_started(self, url):
        self.start_btn.configure(state="disabled", text="✅ Paylaşılıyor")
        self.sharing_info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        self.url_entry.configure(state="normal")
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.url_entry.configure(state="readonly")
        
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("Başarılı", f"Link kopyalandı!\n{url}")
        
        self.is_sharing = True
        self.update_stats()

    def _on_sharing_error(self, err):
        self.start_btn.configure(state="normal", text="🚀 Paylaş")
        messagebox.showerror("Hata", str(err))

    def update_stats(self):
        if not self.is_sharing:
            return
            
        stats = transfer_monitor.get_stats()
        text = f"Hız: {format_speed(stats['speed'])} | Gönderilen: {format_size(stats['total_sent'])} | Aktif: {stats['active']}"
        self.stats_label.configure(text=text)
        
        # Update Connection Status
        if stats['active'] > 0:
            self.status_label.configure(text="🟢 Aktif Transfer", text_color="#06A77D")
        else:
            self.status_label.configure(text="🟡 Beklemede", text_color="#F7D358")
            
        # Update File Progress
        if 'files' in stats:
            for filename, data in stats['files'].items():
                if filename in self.file_progress_labels:
                    pct = (data['sent'] / data['size'] * 100) if data['size'] > 0 else 0
                    self.file_progress_labels[filename].configure(text=f"%{pct:.0f}")
        
        self.after(1000, self.update_stats)

    def stop_sharing(self):
        if self.tunnel_manager:
            self.tunnel_manager.stop()
        self.tunnel_manager = None
        # Stop WebRTC sender
        if self.webrtc_sender:
            self.webrtc_sender.stop()
            self.webrtc_sender = None
            import server as srv
            srv.webrtc_sender = None
        self.is_sharing = False
        self.sharing_info_frame.grid_remove()
        self.start_btn.configure(state="normal", text="🚀 Paylaş")

    def copy_url(self):
        url = self.url_entry.get()
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)

    # --- RECEIVE LOGIC ---
    
    def connect_to_url(self):
        url = self.url_input.get().strip()
        if not url: return
        
        self.download_url = url
        self.connect_btn.configure(state="disabled", text="...")
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        try:
            self.downloader = Downloader()
            files = self.downloader.get_file_list(self.download_url)
            self.remote_files = files
            
            # Check if sender supports P2P
            self._p2p_available = False
            if self.use_p2p:
                try:
                    import requests
                    resp = requests.get(f"{self.download_url}/rtc/status", timeout=5)
                    if resp.ok and resp.json().get("p2p"):
                        self._p2p_available = True
                        print("[P2P] Gönderen P2P destekliyor!")
                except:
                    print("[P2P] P2P durumu kontrol edilemedi, HTTP fallback kullanılacak.")
            
            self.after(0, self._on_connected)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Hata", str(e)))
            self.after(0, lambda: self.connect_btn.configure(state="normal", text="Bağlan"))

    def _on_connected(self):
        self.connect_btn.configure(state="normal", text="Bağlan")
        
        # Status Update
        self.status_label.configure(text="🟢 Bağlandı", text_color="#06A77D")
        
        self.remote_files_frame.pack(fill="both", padx=20, pady=10)
        
        self.remote_files_tb.configure(state="normal")
        self.remote_files_tb.delete("0.0", "end")
        for f in self.remote_files:
            self.remote_files_tb.insert("end", f"{f['name']} ({format_size(f['size'])})\n")
        self.remote_files_tb.configure(state="disabled")

    def start_download(self):
        save_path = filedialog.askdirectory()
        if not save_path: return
        
        self.download_btn.configure(state="disabled", text="İndiriliyor...")
        self.progress_label.configure(text="İndirme Başlıyor...")
        
        # Try P2P first if available
        if getattr(self, '_p2p_available', False):
            threading.Thread(target=self._p2p_download_thread, args=(save_path,), daemon=True).start()
        else:
            threading.Thread(target=self._download_thread, args=(save_path,), daemon=True).start()

    def _p2p_download_thread(self, save_path):
        """Download files via WebRTC P2P DataChannel"""
        try:
            self.after(0, lambda: self.status_label.configure(text="🟢 P2P Bağlanıyor...", text_color="#06A77D"))
            self.after(0, lambda: self.log_message("P2P bağlantısı kuruluyor..."))
            
            receiver = WebRTCReceiver()
            receiver.save_path = save_path
            receiver.log_callback = lambda msg: self.after(0, lambda: self.log_message(f"[P2P] {msg}"))
            
            def p2p_progress(dl, total, speed, current_file, total_files):
                pct = (dl / total * 100) if total else 0
                self.after(0, self.update_progress, pct, speed, current_file, total_files)
            receiver.progress_callback = p2p_progress
            
            # Create offer
            offer = receiver.create_offer_sync()
            
            # Send offer to sender via signal server
            import requests
            resp = requests.post(
                f"{self.download_url}/rtc/offer",
                json={"sdp": offer["sdp"], "type": offer["type"]},
                timeout=15
            )
            
            if not resp.ok:
                raise Exception(f"Signal server hatası: {resp.status_code}")
            
            answer = resp.json()
            if "error" in answer:
                raise Exception(f"SDP hatası: {answer['error']}")
            
            # Set answer
            receiver.set_answer_sync(answer["sdp"])
            
            self.after(0, lambda: self.log_message("P2P bağlantısı bekleniyor..."))
            
            # Wait for connection
            if not receiver.wait_for_connection(timeout=15):
                raise Exception("P2P bağlantısı zaman aşımına uğradı")
            
            if receiver.status == "failed":
                raise Exception("P2P bağlantısı kurulamadı")
            
            self.after(0, lambda: self.status_label.configure(text="🟢 P2P Transfer", text_color="#06A77D"))
            self.after(0, lambda: self.log_message("✅ P2P bağlandı! Dosyalar alınıyor..."))
            
            # Wait for transfer to complete
            receiver.wait_for_transfer(timeout=None)
            
            self.after(0, self._on_download_complete, save_path)
            receiver.stop()
            
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self.log_message(f"P2P hatası: {err_msg}. HTTP fallback'e geçiliyor..."))
            # Fallback to HTTP download
            self._download_thread(save_path)



    def update_progress(self, pct, speed, current, total):
        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=f"Dosya {current}/{total} - %{pct:.1f} ({format_speed(speed)})")

    def _on_download_complete(self, path):
        messagebox.showinfo("Tamamlandı", f"Dosyalar indirildi:\n{path}")
        self._reset_download_ui()
        try: os.startfile(path)
        except: pass

    def _reset_download_ui(self):
        self.download_btn.configure(state="normal", text="📥 İndir")
        # self.progress_frame.pack_forget() # Keep visible
        self.progress_label.configure(text="Hazır - İndirme Bekleniyor")
        self.progress_bar.set(0)

if __name__ == "__main__":
    app = QuickShareApp()
    app.mainloop()
