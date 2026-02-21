"""
QuickShare Main Application - Modern UI with Sidebar & Drag-Drop
"""

import customtkinter as ctk
from tkinter import filedialog
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import sys
import time
import os
import webbrowser
import asyncio
from typing import List, Optional

from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE, CF_TUNNEL_TOKEN, CF_TUNNEL_URL, save_config, DUCKDNS_DOMAIN, DUCKDNS_TOKEN, USE_DUCKDNS, SIGNALING_SERVER_URL
from utils import format_size, format_speed, format_time, validate_url, calculate_total_size, calculate_eta
from server import set_shared_files, run_server, transfer_monitor
from tunnel_manager import TunnelManager
from downloader import Downloader
from webrtc_manager import WebRTCSender, WebRTCReceiver, SignalingClient
import random
import string
from transfer_history import history
from history_frame import HistoryFrame
from tray_manager import TrayManager
from ui_components import FileListTree, ToastNotification

# CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Premium Dark Theme Colors
COLORS = {
    "bg": "#0D1117",
    "surface": "#161B22",
    "surface_hover": "#21262D",
    "border": "#30363d",
    "primary": "#3b82f6",
    "primary_hover": "#2563eb",
    "primary_glow": "#1f6feb",
    "secondary": "#10b981",
    "secondary_hover": "#059669",
    "warning": "#E67E22",
    "warning_hover": "#D35400",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "text": "#c9d1d9",
    "text_muted": "#8b949e",
    "text_bright": "#ffffff",
}



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
        self.geometry("1050x750")
        self.configure(fg_color=COLORS["bg"])
        self.minsize(800, 600)
        
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
        self.is_paused = False
        self.is_paused = False
        self._download_start_time: float = 0
        self.tray_manager: Optional[TrayManager] = None
        
        # Grid Layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_pages()
        
        # Start at Home
        self.select_frame("home")
        
        # Tray Setup
        try:
            self.tray_manager = TrayManager(self)
            self.tray_manager.run()
        except Exception as e:
            print(f"Tray error: {e}")
            
        # Handle Window Close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        """Minimize to tray or quit"""
        # For now, always minimize to tray if passing specific flag, but let's just minimize
        # and Quit option in tray handles actual quit
        self.withdraw()
        if self.tray_manager:
            self.tray_manager.show_notification("QuickShare", "Arka planda çalışıyor...")
            
    def exit_app(self):
        """Actual quit"""
        if self.tray_manager:
            self.tray_manager.stop()
        self.destroy()
        sys.exit(0)
        
    def setup_sidebar(self):
        """Create the sidebar navigation"""
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS["surface"], border_width=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)  # Spacer row
        
        # Separator line on right edge
        separator = ctk.CTkFrame(self.sidebar_frame, width=1, fg_color=COLORS["border"])
        separator.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        
        # Logo / Title
        logo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=24, pady=(32, 28), sticky="w")
        
        ctk.CTkLabel(
            logo_frame, text="⚡",
            font=ctk.CTkFont(size=20),
            text_color=COLORS["warning"]
        ).pack(side="left", padx=(0, 8))
        
        ctk.CTkLabel(
            logo_frame, text="QuickShare",
            font=ctk.CTkFont(family="Inter", size=22, weight="bold"),
            text_color=COLORS["text_bright"]
        ).pack(side="left")
        
        # Navigation Buttons
        nav_kwargs = {
            "fg_color": "transparent",
            "text_color": COLORS["text_muted"],
            "hover_color": COLORS["surface_hover"],
            "corner_radius": 8,
            "anchor": "w",
            "height": 42,
            "font": ctk.CTkFont(family="Inter", size=14, weight="bold")
        }
        
        self.sidebar_button_home = ctk.CTkButton(self.sidebar_frame, text="   🏠  Ana Sayfa", command=lambda: self.select_frame("home"), **nav_kwargs)
        self.sidebar_button_home.grid(row=1, column=0, padx=12, pady=3, sticky="ew")
        
        self.sidebar_button_send = ctk.CTkButton(self.sidebar_frame, text="   📤  Gönder", command=lambda: self.select_frame("send"), **nav_kwargs)
        self.sidebar_button_send.grid(row=2, column=0, padx=12, pady=3, sticky="ew")
        
        self.sidebar_button_receive = ctk.CTkButton(self.sidebar_frame, text="   📥  Al", command=lambda: self.select_frame("receive"), **nav_kwargs)
        self.sidebar_button_receive.grid(row=3, column=0, padx=12, pady=3, sticky="ew")

        self.sidebar_button_history = ctk.CTkButton(self.sidebar_frame, text="   🕐  Geçmiş", command=lambda: self.select_frame("history"), **nav_kwargs)
        self.sidebar_button_history.grid(row=4, column=0, padx=12, pady=3, sticky="ew")
        
        # Bottom section
        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.grid(row=6, column=0, sticky="sew", padx=12, pady=(0, 8))
        
        # Separator
        ctk.CTkFrame(bottom_frame, height=1, fg_color=COLORS["border"]).pack(fill="x", pady=(0, 12))
        
        self.sidebar_button_settings = ctk.CTkButton(
            bottom_frame, text="   ⚙️  Ayarlar", command=lambda: self.select_frame("settings"),
            fg_color="transparent", hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_muted"], anchor="w", height=40,
            font=ctk.CTkFont(family="Inter", size=13, weight="bold")
        )
        self.sidebar_button_settings.pack(fill="x", pady=(0, 8))
        
        # Connection Status
        self.status_label = ctk.CTkLabel(
            bottom_frame, 
            text="● Çevrimdışı", 
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=COLORS["danger"]
        )
        self.status_label.pack(anchor="w", padx=12, pady=(0, 12))

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

        # History Frame
        self.history_frame = HistoryFrame(self, corner_radius=0, fg_color="transparent")
        
        # Settings Frame
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_settings_ui()

    def select_frame(self, name):
        """Switch active frame"""
        # Active: subtle blue glow bg, white text. Inactive: transparent, muted text.
        active_color = "#1f6feb15"  # Very subtle blue tint (CTK may not support alpha, fallback)
        active_color = "#1a2332"   # Solid dark blue tint
        inactive_color = "transparent"
        active_text = COLORS["primary"]
        inactive_text = COLORS["text_muted"]
        
        # Reset button colors
        for btn, btn_name in [(self.sidebar_button_home, "home"), (self.sidebar_button_send, "send"),
                               (self.sidebar_button_receive, "receive"), (self.sidebar_button_history, "history")]:
            is_active = name == btn_name
            btn.configure(
                fg_color=active_color if is_active else inactive_color,
                text_color=active_text if is_active else inactive_text
            )
        
        # Hide all
        self.home_frame.grid_forget()
        self.send_frame.grid_forget()
        self.receive_frame.grid_forget()
        self.history_frame.grid_forget()
        self.settings_frame.grid_forget()
        
        # Show selected
        if name == "home":
            self.refresh_home_ui()
            self.home_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "send":
            self.send_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "receive":
            self.receive_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "history":
            self.history_frame.refresh()
            self.history_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew")

    # --- UI SETUP METHODS ---
    
    def setup_home_ui(self):
        """Home Dashboard UI"""
        self.home_frame.grid_columnconfigure(0, weight=1)
        
        # Main Greeting
        ctk.CTkLabel(self.home_frame, text="Hoşgeldiniz",
                     font=ctk.CTkFont(family="Inter", size=30, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(pady=(50, 8), anchor="w", padx=50)
        ctk.CTkLabel(self.home_frame, text="Dosyalarınızı sınır olmadan özgürce paylaşın.",
                     font=ctk.CTkFont(family="Inter", size=14),
                     text_color=COLORS["text_muted"]).pack(pady=(0, 40), anchor="w", padx=50)
        
        # Status Cards Container
        cards_frame = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=50, pady=10)
        cards_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Card 1: System Status
        status_card = ctk.CTkFrame(cards_frame, corner_radius=16, fg_color=COLORS["surface"],
                                   border_width=1, border_color=COLORS["border"])
        status_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        status_inner.pack(fill="x", padx=20, pady=20)
        
        icon_frame = ctk.CTkFrame(status_inner, width=48, height=48, corner_radius=12,
                                   fg_color=COLORS["surface_hover"], border_width=1, border_color=COLORS["border"])
        icon_frame.pack(side="left", padx=(0, 14))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="🛡️", font=ctk.CTkFont(size=18)).pack(expand=True)
        
        text_frame = ctk.CTkFrame(status_inner, fg_color="transparent")
        text_frame.pack(side="left", fill="x")
        ctk.CTkLabel(text_frame, text="Sistem Durumu",
                     font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(anchor="w")
        self.home_status_text = ctk.CTkLabel(text_frame, text="Hazır ve Beklemede",
                     font=ctk.CTkFont(family="Inter", size=13),
                     text_color=COLORS["text_muted"])
        self.home_status_text.pack(anchor="w")
        
        # Card 2: Recent Activity
        recent_card = ctk.CTkFrame(cards_frame, corner_radius=16, fg_color=COLORS["surface"],
                                   border_width=1, border_color=COLORS["border"])
        recent_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        
        recent_header = ctk.CTkFrame(recent_card, fg_color="transparent")
        recent_header.pack(fill="x", padx=20, pady=(20, 10))
        
        icon_frame2 = ctk.CTkFrame(recent_header, width=48, height=48, corner_radius=12,
                                    fg_color=COLORS["surface_hover"], border_width=1, border_color=COLORS["border"])
        icon_frame2.pack(side="left", padx=(0, 14))
        icon_frame2.pack_propagate(False)
        ctk.CTkLabel(icon_frame2, text="⚡", font=ctk.CTkFont(size=18)).pack(expand=True)
        
        ctk.CTkLabel(recent_header, text="Son İşlemler",
                     font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(side="left")
        
        self.recent_list = ctk.CTkFrame(recent_card, fg_color="transparent")
        self.recent_list.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.refresh_home_ui()
        
        # Quick Actions
        actions_frame = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        actions_frame.pack(pady=40)
        
        ctk.CTkButton(actions_frame, text="  +  Yeni Dosya Gönder",
                      font=ctk.CTkFont(family="Inter", size=15, weight="bold"), 
                      command=lambda: self.select_frame("send"),
                      height=50, corner_radius=12,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="left", padx=10)
        
        ctk.CTkButton(actions_frame, text="  ⬇  Kodu Gir",
                      font=ctk.CTkFont(family="Inter", size=15, weight="bold"), 
                      command=lambda: self.select_frame("receive"),
                      height=50, corner_radius=12,
                      fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                      border_width=1, border_color=COLORS["border"]).pack(side="left", padx=10)

    def refresh_home_ui(self):
        """Refresh home dashboard stats"""
        for widget in self.recent_list.winfo_children():
            widget.destroy()
            
        recent = history.get_recent(5)
        if not recent:
            ctk.CTkLabel(self.recent_list, text="Henüz işlem yok.",
                         text_color=COLORS["text_muted"],
                         font=ctk.CTkFont(family="Inter", size=13)).pack()
        else:
            for item in recent:
                icon = "📤" if item['direction'] == "send" else "📥"
                status = "✅" if item['status'] == "success" else "❌"
                text = f"{icon} {item['filename']} ({format_size(item['size'])}) - {status}"
                ctk.CTkLabel(self.recent_list, text=text, anchor="w",
                             font=ctk.CTkFont(family="Inter", size=12),
                             text_color=COLORS["text"]).pack(fill="x", pady=2)

    def setup_send_ui(self):
        """Send UI with Drag & Drop"""
        self.send_frame.grid_columnconfigure(0, weight=1)
        self.send_frame.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(self.send_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=50, pady=(40, 8))
        ctk.CTkLabel(header, text="Gönderim Merkezi",
                     font=ctk.CTkFont(family="Inter", size=30, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(side="left")
        
        # Instructions
        ctk.CTkLabel(self.send_frame,
                     text="Dosyaları aşağıdaki alana sürükleyip bırakabilir veya butonları kullanabilirsiniz.",
                     font=ctk.CTkFont(family="Inter", size=13),
                     text_color=COLORS["text_muted"], anchor="w"
        ).grid(row=1, column=0, sticky="ew", padx=50, pady=(0, 20))
        
        # Drag & Drop Area / File List Card
        list_container = ctk.CTkFrame(self.send_frame, corner_radius=16,
                                      fg_color=COLORS["surface"],
                                      border_width=1, border_color=COLORS["border"])
        list_container.grid(row=2, column=0, sticky="nsew", padx=50, pady=0)
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(1, weight=1)
        
        # Top tools inside card
        inner_tools = ctk.CTkFrame(list_container, fg_color="transparent")
        inner_tools.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        
        ctk.CTkButton(inner_tools, text="📁  Dosya Seç",
                      font=ctk.CTkFont(family="Inter", weight="bold"),
                      command=self.select_files,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                      corner_radius=8, height=36).pack(side="left", padx=4)
        ctk.CTkButton(inner_tools, text="📂  Klasör Seç",
                      font=ctk.CTkFont(family="Inter", weight="bold"),
                      command=self.select_folder,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      corner_radius=8, height=36).pack(side="left", padx=4)
        ctk.CTkButton(inner_tools, text="🗑️  Temizle",
                      font=ctk.CTkFont(family="Inter", weight="bold"),
                      command=self.clear_files,
                      fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                      corner_radius=8, width=100, height=36).pack(side="right", padx=4)

        self.file_tree = FileListTree(list_container, columns=("size", "status"))
        self.file_tree.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        
        # Enable Drop
        self.file_tree.drop_target_register(DND_FILES)
        self.file_tree.dnd_bind('<<Drop>>', self.on_drop)
        
        # Action Buttons (Cloud vs P2P)
        controls = ctk.CTkFrame(self.send_frame, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew", padx=50, pady=24)
        controls.grid_columnconfigure((0, 1), weight=1)
        
        self.start_btn = ctk.CTkButton(
            controls, text="☁  Bulut Linki Oluştur\nSunucu Üzerinden (URL - Max 100MB)", 
            command=self.start_sharing,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"), 
            height=72, corner_radius=14,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text_bright"]
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.direct_btn = ctk.CTkButton(
            controls, text="⚡  Doğrudan Cihaza Aktar\nP2P Kod ile Sınırsız Hız & Boyut", 
            command=self.start_direct_sharing,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"), 
            height=72, corner_radius=14,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text_bright"]
        )
        self.direct_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        
        # Active Sharing Info Panel
        self.sharing_info_frame = ctk.CTkFrame(self.send_frame, corner_radius=14,
                                               fg_color=COLORS["secondary"],
                                               border_width=0)
        self.sharing_info_frame.grid(row=4, column=0, sticky="ew", padx=50, pady=(0, 24))
        self.sharing_info_frame.grid_remove()
        
        inner_share = ctk.CTkFrame(self.sharing_info_frame, fg_color="transparent")
        inner_share.pack(fill="x", padx=20, pady=15)
        
        self.url_entry = ctk.CTkEntry(inner_share, placeholder_text="Paylaşım Linki/Kodu...",
                                      state="readonly", 
                                      font=ctk.CTkFont(family="Consolas", size=14, weight="bold"), 
                                      fg_color="#064e3b", border_width=0, text_color="#ffffff")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        ctk.CTkButton(inner_share, text="📋 Kopyala", command=self.copy_url,
                      font=ctk.CTkFont(weight="bold"),
                      fg_color="#059669", hover_color="#047857", width=100,
                      corner_radius=8).pack(side="left")
        
        self.pause_btn = ctk.CTkButton(inner_share, text="⏸️", command=self.toggle_pause,
                                       width=40, corner_radius=8,
                                       fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"])
        self.pause_btn.pack(side="left", padx=(8, 0))
        
        ctk.CTkButton(inner_share, text="🛑 Durdur", command=self.stop_sharing,
                      fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                      font=ctk.CTkFont(weight="bold"), width=100,
                      corner_radius=8).pack(side="left", padx=8)

        # Stats
        self.stats_label = ctk.CTkLabel(self.sharing_info_frame, text="",
                                       font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                                       text_color="#ecfdf5")
        self.stats_label.pack(side="bottom", pady=(0, 15))

    def setup_receive_ui(self):
        """Receive UI"""
        self.receive_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        ctk.CTkLabel(self.receive_frame, text="Dosya Al",
                     font=ctk.CTkFont(family="Inter", size=30, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(pady=(40, 8), anchor="w", padx=50)
        ctk.CTkLabel(self.receive_frame, text="Kodu veya Linki girerek indirmeye başlayın.",
                     font=ctk.CTkFont(family="Inter", size=13),
                     text_color=COLORS["text_muted"]).pack(anchor="w", padx=50, pady=(0, 20))
        
        # URL Input Card
        input_card = ctk.CTkFrame(self.receive_frame, fg_color=COLORS["surface"],
                                   corner_radius=16, border_width=1, border_color=COLORS["border"])
        input_card.pack(fill="x", padx=50, pady=(0, 16))
        
        url_box = ctk.CTkFrame(input_card, fg_color="transparent")
        url_box.pack(fill="x", padx=20, pady=20)
        
        self.url_input = ctk.CTkEntry(url_box,
                                      placeholder_text="6 Haneli Kod veya Link...",
                                      font=ctk.CTkFont(family="Consolas", size=16),
                                      fg_color=COLORS["bg"],
                                      border_color=COLORS["border"],
                                      corner_radius=12,
                                      height=48)
        self.url_input.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.url_input.bind('<Return>', lambda e: self.connect_to_url())
        
        self.connect_btn = ctk.CTkButton(url_box, text="🔗 Bağlan",
                                          command=self.connect_to_url,
                                          font=ctk.CTkFont(family="Inter", weight="bold"),
                                          fg_color=COLORS["primary"],
                                          hover_color=COLORS["primary_hover"],
                                          corner_radius=10, height=48, width=120)
        self.connect_btn.pack(side="right", padx=2)

        self.connect_code_btn = ctk.CTkButton(url_box, text="⚡ Kodla",
                                               command=self.connect_via_code,
                                               font=ctk.CTkFont(family="Inter", weight="bold"),
                                               fg_color=COLORS["warning"],
                                               hover_color=COLORS["warning_hover"],
                                               corner_radius=10, height=48, width=100)
        self.connect_code_btn.pack(side="right", padx=2)
        
        # Remote Files List Card
        self.remote_files_frame = ctk.CTkFrame(self.receive_frame, fg_color=COLORS["surface"],
                                               corner_radius=16, border_width=1, border_color=COLORS["border"])
        self.remote_files_frame.pack(fill="both", expand=True, padx=50, pady=(0, 12))
        
        self.remote_files_tree = FileListTree(self.remote_files_frame, columns=("size"), show_checkboxes=True)
        self.remote_files_tree.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        
        self.download_btn = ctk.CTkButton(self.remote_files_frame, text="📥  İndir",
                                           command=self.start_download,
                                           fg_color=COLORS["secondary"],
                                           hover_color=COLORS["secondary_hover"],
                                           font=ctk.CTkFont(family="Inter", weight="bold"),
                                           corner_radius=10, height=40)
        self.download_btn.pack(fill="x", padx=12, pady=12)
        
        # Progress
        self.progress_frame = ctk.CTkFrame(self.receive_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=50, pady=(0, 8))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame,
                                                progress_color=COLORS["primary"],
                                                fg_color=COLORS["surface"],
                                                corner_radius=6, height=8)
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Hazır — İndirme Bekleniyor",
                                           font=ctk.CTkFont(family="Inter", size=12),
                                           text_color=COLORS["text_muted"])
        self.progress_label.pack()
        
        # Log Console
        ctk.CTkLabel(self.receive_frame, text="İşlem Logları", anchor="w",
                     font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                     text_color=COLORS["text_muted"]).pack(fill="x", padx=50, pady=(8, 4))
        
        self.log_box = ctk.CTkTextbox(self.receive_frame, height=90, state="disabled",
                                      font=ctk.CTkFont(family="Consolas", size=11),
                                      fg_color=COLORS["bg"],
                                      border_width=1, border_color=COLORS["border"],
                                      corner_radius=10,
                                      text_color=COLORS["text"])
        self.log_box.pack(fill="x", padx=50, pady=(0, 20))

    def log_message(self, msg):
        """Log mesajını UI'a yaz"""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def setup_settings_ui(self):
        """Settings UI"""
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        ctk.CTkLabel(self.settings_frame, text="Ayarlar",
                     font=ctk.CTkFont(family="Inter", size=30, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(pady=(40, 8), anchor="w", padx=50)
        ctk.CTkLabel(self.settings_frame, text="Uygulama yapılandırmasını buradan düzenleyebilirsiniz.",
                     font=ctk.CTkFont(family="Inter", size=13),
                     text_color=COLORS["text_muted"]).pack(anchor="w", padx=50, pady=(0, 24))
        
        # Scrollable area for settings cards
        settings_scroll = ctk.CTkScrollableFrame(self.settings_frame, fg_color="transparent")
        settings_scroll.pack(fill="both", expand=True, padx=50)
        settings_scroll.grid_columnconfigure(0, weight=1)
        
        # Card 1: Cloudflare Tunnel
        cf_card = ctk.CTkFrame(settings_scroll, corner_radius=16, fg_color=COLORS["surface"],
                                border_width=1, border_color=COLORS["border"])
        cf_card.pack(fill="x", pady=(0, 16))
        
        cf_header = ctk.CTkFrame(cf_card, fg_color="transparent")
        cf_header.pack(fill="x", padx=20, pady=(20, 14))
        ctk.CTkLabel(cf_header, text="☁️",
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(cf_header, text="Cloudflare Tunnel",
                     font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(side="left")
        
        cf_body = ctk.CTkFrame(cf_card, fg_color="transparent")
        cf_body.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkLabel(cf_body, text="Tunnel Token",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.entry_token = ctk.CTkEntry(cf_body, placeholder_text="Token (opsiyonel)",
                                        fg_color=COLORS["bg"], border_color=COLORS["border"],
                                        corner_radius=10, height=40)
        self.entry_token.pack(fill="x", pady=(0, 12))
        self.entry_token.insert(0, CF_TUNNEL_TOKEN)
        
        ctk.CTkLabel(cf_body, text="Public URL",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.entry_url = ctk.CTkEntry(cf_body, placeholder_text="https://...",
                                      fg_color=COLORS["bg"], border_color=COLORS["border"],
                                      corner_radius=10, height=40)
        self.entry_url.pack(fill="x")
        self.entry_url.insert(0, CF_TUNNEL_URL)
        
        # Card 2: DuckDNS
        ddns_card = ctk.CTkFrame(settings_scroll, corner_radius=16, fg_color=COLORS["surface"],
                                  border_width=1, border_color=COLORS["border"])
        ddns_card.pack(fill="x", pady=(0, 16))
        
        ddns_header = ctk.CTkFrame(ddns_card, fg_color="transparent")
        ddns_header.pack(fill="x", padx=20, pady=(20, 14))
        ctk.CTkLabel(ddns_header, text="🌐",
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ddns_header, text="DuckDNS",
                     font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
                     text_color=COLORS["text_bright"]).pack(side="left")
        
        ddns_body = ctk.CTkFrame(ddns_card, fg_color="transparent")
        ddns_body.pack(fill="x", padx=20, pady=(0, 20))
        
        self.use_duckdns_var = ctk.BooleanVar(value=USE_DUCKDNS)
        ctk.CTkSwitch(ddns_body, text="DuckDNS Kullan (Port 5000 açık olmalı)",
                      variable=self.use_duckdns_var,
                      font=ctk.CTkFont(family="Inter", size=13),
                      text_color=COLORS["text"],
                      progress_color=COLORS["secondary"]).pack(anchor="w", pady=(0, 14))
        
        ctk.CTkLabel(ddns_body, text="Domain",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.entry_duck_domain = ctk.CTkEntry(ddns_body, placeholder_text="myapp",
                                               fg_color=COLORS["bg"], border_color=COLORS["border"],
                                               corner_radius=10, height=40)
        self.entry_duck_domain.pack(fill="x", pady=(0, 12))
        self.entry_duck_domain.insert(0, DUCKDNS_DOMAIN)
        
        ctk.CTkLabel(ddns_body, text="Token",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.entry_duck_token = ctk.CTkEntry(ddns_body, placeholder_text="Token",
                                              fg_color=COLORS["bg"], border_color=COLORS["border"],
                                              corner_radius=10, height=40)
        self.entry_duck_token.pack(fill="x")
        self.entry_duck_token.insert(0, DUCKDNS_TOKEN)
        
        # Save Button
        save_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        save_frame.pack(fill="x", padx=50, pady=(8, 24))
        
        ctk.CTkButton(save_frame, text="💾  Kaydet", command=self.save_settings,
                      font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                      corner_radius=12, height=44, width=160).pack(side="right")
        
        ctk.CTkLabel(save_frame, text="Token girilmezse geçici (limitli) tunnel kullanılır.",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=COLORS["text_muted"]).pack(side="left")

    def save_settings(self):
        token = self.entry_token.get().strip()
        url = self.entry_url.get().strip()
        
        duck_domain = self.entry_duck_domain.get().strip()
        duck_token = self.entry_duck_token.get().strip()
        use_duck = self.use_duckdns_var.get()
        
        # Update config in memory
        import config
        config.CF_TUNNEL_TOKEN = token
        config.CF_TUNNEL_URL = url
        config.DUCKDNS_DOMAIN = duck_domain
        config.DUCKDNS_TOKEN = duck_token
        config.USE_DUCKDNS = use_duck
        
        save_config(token, url, duck_domain, duck_token, use_duck)
        messagebox.showinfo("Ayarlar", "Ayarlar kaydedildi! Değişikliklerin geçerli olması için uygulamayı yeniden başlatmanız önerilir.")
        
    # --- LOGIC ---



    # --- WebRTC P2P Logic ---

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
        self.file_tree.clear()
        
        if not self.selected_files:
            # Maybe show a placeholder label inside tree? 
            # FileListTree doesn't support overlay yet. 
            pass
            
        for f in self.selected_files:
            name = os.path.basename(f)
            size = os.path.getsize(f) if os.path.isfile(f) else 0
            is_dir = os.path.isdir(f)
            self.file_tree.add_item(name, is_folder=is_dir, size_str=format_size(size), data=f)
            
    def start_direct_sharing(self):
        """Start sharing via Signaling Server (Direct P2P, No Tunnel)"""
        if not self.selected_files:
            ToastNotification.show_toast(self, "Dosya seçiniz.", type="warning")
            return

        dialog = ctk.CTkInputDialog(text="P2P oturumuna parola eklensin mi?\n(İstemiyorsanız boş bırakın):", title="Parola Koruması (İsteğe Bağlı)")
        password = dialog.get_input()
        if password is None: # User cancelled
            return
            
        self.current_session_password = password.strip() if password else None

        self.start_btn.configure(state="disabled")
        self.direct_btn.configure(state="disabled", text="Başlatılıyor...")
        
        threading.Thread(target=self._direct_sharing_thread, daemon=True).start()

    def _direct_sharing_thread(self):
        try:
            set_shared_files(self.selected_files)
            
            # Generate Room ID
            room_id = ''.join(random.choices(string.digits, k=6))
            
            # Get loop ready then initialize Signaling Client
            self.webrtc_sender = WebRTCSender()
            self.webrtc_sender.password = getattr(self, "current_session_password", None)
            self.webrtc_sender.start() # Starts thread
            self.webrtc_sender.wait_until_ready() # Wait for loop
            
            # Build and set file list for WebRTC sender
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
            
            # Helper to run async in sender's loop
            async def setup_async():
                try:
                    await signaling.connect(room_id)
                    self.webrtc_sender.setup_signaling(signaling)
                except Exception as e:
                    print(f"Sinyal sunucusu bağlantı hatası: {e}")
                    self.after(0, lambda: messagebox.showerror("Bağlantı Hatası", f"Sinyal sunucusuna bağlanılamadı: {e}"))
                    self.after(0, self.stop_sharing)
                
            asyncio.run_coroutine_threadsafe(setup_async(), self.webrtc_sender._loop)
            
            # Setup Callbacks
            self.webrtc_sender.log_callback = lambda msg: print(f"[Sender] {msg}")
            
            def sender_progress(sent, total, speed, current_file_idx, total_files):
                transfer_monitor.total_sent = sent
                transfer_monitor.total_size = total
                transfer_monitor.current_speed = speed
                try:
                    self.after(0, self.update_stats)
                    # Also update file progress in tree
                    current_file_idx_0 = current_file_idx - 1
                    if 0 <= current_file_idx_0 < len(self.selected_files):
                         # This is tricky because we don't know exactly which file is which index in webRTC list vs stats
                         # But transfer_monitor updates stats['files']
                         pass
                except: pass

            self.webrtc_sender.progress_callback = sender_progress
            
            self.is_sharing = True
            
            # Show UI with Code
            self.after(0, self._on_direct_sharing_started, room_id)
            
        except Exception as e:
            print(f"Error starting direct share: {e}")
            self.after(0, lambda: messagebox.showerror("Hata", str(e)))
            self.after(0, self.stop_sharing)

    def stop_sharing(self):
        """Stop sharing (Tunnel or Direct)"""
        self.is_sharing = False
        self.is_paused = False
        self.pause_btn.configure(text="⏸️")
        
        if self.tunnel_manager:
            self.tunnel_manager.stop()
        self.tunnel_manager = None
        
        # Stop WebRTC Sender (handles both Tunnel and Direct modes)
        if self.webrtc_sender:
            if hasattr(self.webrtc_sender, 'signaling') and self.webrtc_sender.signaling:
                asyncio.run_coroutine_threadsafe(self.webrtc_sender.signaling.close(), self.webrtc_sender._loop)
            self.webrtc_sender.stop()
            self.webrtc_sender = None
            import server as srv
            srv.webrtc_sender = None
            
        self.sharing_info_frame.grid_remove()
        self.start_btn.configure(state="normal", text="🌐 Bulut Üzerinden (URL - Max 100MB)")
        self.direct_btn.configure(state="normal", text="⚡ Doğrudan P2P (Kod - Sınırsız)")
        self.status_label.configure(text="Durum: Hazır", text_color="white")

    def _on_direct_sharing_started(self, room_id):
        self.sharing_info_frame.grid()
        self.url_entry.configure(state="normal")
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, f"Kod: {room_id}")
        self.url_entry.configure(state="readonly")
        
        self.status_label.configure(text=f"🟢 Bekleniyor (Kod: {room_id})", text_color="#E67E22")
        self.start_btn.configure(state="disabled")
        
    def connect_via_code(self):
        """Connect to sender using code"""
        code = self.url_input.get().strip().replace("Kod: ", "")
        if not code:
            ToastNotification.show_toast(self, "Lütfen kodu girin.", type="warning")
            return
            
        dialog = ctk.CTkInputDialog(text="Eğer gönderici parola koyduysa giriniz\n(Yoksa boş bırakın):", title="Kimlik Doğrulama")
        password = dialog.get_input()
        if password is None:
            return
            
        self.current_session_password = password.strip() if password else None
            
        self.connect_btn.configure(state="disabled", text="Bağlanıyor...")
        self.connect_code_btn.configure(state="disabled")
        
        threading.Thread(target=self._connect_code_thread, args=(code,), daemon=True).start()

    def _connect_code_thread(self, code):
        try:
             self.log_message(f"Sinyal sunucusuna bağlanılıyor... (Oda: {code})")
             
             receiver = WebRTCReceiver()
             receiver.password = getattr(self, "current_session_password", None)
             
             def on_auth_err():
                 self.after(0, lambda: ToastNotification.show_toast(self, "Parola Hatalı ya da Gerekli!", type="error"))
                 self.after(0, lambda: self.connect_code_btn.configure(state="normal", text="Doğrudan Cihaza Bağlan (Kod)"))
                 self.after(0, lambda: self.connect_btn.configure(state="normal", text="Bağlan"))
                 self.after(0, lambda: self.status_label.configure(text="Bağlantı Bekleniyor", text_color="white"))
             receiver.on_auth_failed = on_auth_err
             
             receiver.start() # Start loop
             receiver.wait_until_ready() # Wait for loop
             
             signaling = SignalingClient(receiver._loop)
             
             async def setup_async():
                 try:
                     await signaling.connect(code)
                     receiver.setup_signaling(signaling)
                     await receiver.connect_via_signaling()
                 except Exception as e:
                     self.after(0, self.log_message, f"Sinyal sunucusu hatası: {e}")
                     receiver.stop()
                 
             asyncio.run_coroutine_threadsafe(setup_async(), receiver._loop)
             
             # Setup callbacks
             receiver.log_callback = lambda msg: self.after(0, self.log_message, msg)
             
             def _p2p_progress(r, t, s, f, tf):
                 pct = (r / t * 100) if t else 0
                 eta = calculate_eta(t, r, s)
                 self.after(0, self.update_progress, pct, s, f, tf, eta)
             receiver.progress_callback = _p2p_progress
             
             # Wait for DataChannel connection
             if not receiver.wait_for_connection(timeout=30):
                 raise Exception("P2P bağlantısı zaman aşımına uğradı")
             
             if receiver.status == "failed":
                 raise Exception("P2P bağlantısı kurulamadı")
             
             self.after(0, self.log_message, "P2P bağlantısı kuruldu! Dosya listesi bekleniyor...")
             
             # Wait for file list from sender
             if not receiver._file_list_event.wait(timeout=30):
                 raise Exception("Dosya listesi alınamadı (zaman aşımı)")
             
             # Populate UI with received file list
             self.remote_files = [{'name': f['name'], 'size': f['size']} for f in receiver._file_list]
             
             def populate_ui():
                 self.remote_files_tree.clear()
                 for f in self.remote_files:
                     self.remote_files_tree.add_path_item(f['name'], size_str=format_size(f['size']), data=f)
                 self.connect_btn.configure(state="normal", text="Bağlan")
                 self.connect_code_btn.configure(state="normal", text="Bağlandı ✅")
                 self.connect_code_btn.configure(state="disabled")
                 self.status_label.configure(text="🟢 P2P Bağlandı", text_color="#06A77D")
             
             self.after(0, populate_ui)
             
             # Store receiver for later use by start_download
             self._p2p_receiver = receiver
             self._p2p_available = True
                 
        except Exception as e:
             self.after(0, self.log_message, f"Hata: {e}")
        finally:
             self.after(0, lambda: self.connect_btn.configure(state="normal", text="Bağlan"))
             self.after(0, lambda: self.connect_code_btn.configure(state="normal"))


    def start_sharing(self):
        if not self.selected_files:
            messagebox.showwarning("Uyarı", "Dosya seçiniz.")
            return

        self.start_btn.configure(state="disabled", text="Başlatılıyor...")
        threading.Thread(target=self._sharing_thread, daemon=True).start()

    def _sharing_thread(self):
        try:
            set_shared_files(self.selected_files)
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            time.sleep(1)
            
            import config
            if config.USE_DUCKDNS and config.DUCKDNS_DOMAIN and config.DUCKDNS_TOKEN:
                from ddns_manager import DDNSManager
                ddns = DDNSManager(config.DUCKDNS_DOMAIN, config.DUCKDNS_TOKEN)
                if ddns.update():
                     url = ddns.get_public_url()
                     self.tunnel_manager = None # No tunnel needed
                else:
                     raise Exception("DuckDNS güncellemesi başarısız oldu.")
            else:
                self.tunnel_manager = TunnelManager()
                # Pass token from config (use module level config to get latest value if changed in runtime without restart, if possible)
                url = self.tunnel_manager.start(token=config.CF_TUNNEL_TOKEN)
            
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
        speed_val = stats['speed']

        text = f"Hız: {format_speed(speed_val)} | Gönderilen: {format_size(stats['total_sent'])} | Aktif: {stats['active']}"
        self.stats_label.configure(text=text)
        
        # Update Connection Status
        if self.webrtc_sender:
            connected_peers = sum(1 for p in self.webrtc_sender.peers.values() if p.get("status") in ["connected", "transferring"])
            if connected_peers > 0:
                self.status_label.configure(text=f"🟢 P2P Aktif ({connected_peers} Kişi Bağlı)", text_color="#06A77D")
            else:
                self.status_label.configure(text="🟡 P2P Beklemede (Kimse Bağlı Değil)", text_color="#F7D358")
        else:
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
        """Stop sharing"""
        self.is_sharing = False
        self.is_paused = False
        self.pause_btn.configure(text="⏸️")
        
        if self.tunnel_manager:
            self.tunnel_manager.stop()
        self.tunnel_manager = None
        
        # Stop background thread
        # Server runs in daemon thread, hard to stop gracefully without complex logic
        # For now we just hide UI and stop WebRTC
        if self.webrtc_sender:
            self.webrtc_sender.stop()
            self.webrtc_sender = None
            import server as srv
            srv.webrtc_sender = None
            
        self.sharing_info_frame.grid_remove()
        self.start_btn.configure(state="normal", text="🌐 Bulut Üzerinden (URL - Max 100MB)")
        self.status_label.configure(text="Durum: Hazır", text_color="white") # Reset status label

    def toggle_pause(self):
        """Toggle pause/resume for P2P transfer"""
        if not self.webrtc_sender:
            return
            
        # Get count
        connected_peers = sum(1 for p in self.webrtc_sender.peers.values() if p.get("status") in ["connected", "transferring"])
            
        if self.is_paused:
            self.webrtc_sender.resume()
            self.is_paused = False
            self.pause_btn.configure(text="⏸️")
            self.status_label.configure(text=f"🟢 P2P Aktif ({connected_peers} Kişi Bağlı)", text_color="#06A77D")
        else:
            self.webrtc_sender.pause()
            self.is_paused = True
            self.pause_btn.configure(text="▶️")
            self.status_label.configure(text=f"⏸️ P2P Duraklatıldı ({connected_peers} Kişi Bağlı)", text_color="#F7D358")

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
            self._p2p_available = False # URL sharing no longer attempts to start P2P
            
            self.after(0, self._on_connected)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Hata", str(e)))
            self.after(0, lambda: self.connect_btn.configure(state="normal", text="Bağlan"))

    def _on_connected(self):
        self.connect_btn.configure(state="normal", text="Bağlan")
        
        # Status Update
        self.status_label.configure(text="🟢 Bağlandı", text_color="#06A77D")
        
        # self.remote_files_frame is already setup in receive_ui
        self.remote_files_tree.clear()
        for f in self.remote_files:
            # f is {'name': 'path/file.txt', 'size': 123}
            # Use add_path_item to build tree
            self.remote_files_tree.add_path_item(f['name'], size_str=format_size(f['size']), data=f)
            
    def start_download(self):
        save_path = filedialog.askdirectory()
        if not save_path: return
        
        # Get selected files
        selected_data = self.remote_files_tree.get_checked_data()
        if not selected_data:
            messagebox.showwarning("Uyarı", "Lütfen indirilecek dosyaları seçiniz.")
            return

        self.download_btn.configure(state="disabled", text="İndiriliyor...")
        self.progress_label.configure(text="İndirme Başlıyor...")
        
        files_to_download = selected_data # List of dicts
        
        # Check if we have an active P2P receiver from code connection
        if hasattr(self, '_p2p_receiver') and self._p2p_receiver and self._p2p_receiver.status == "connected":
            threading.Thread(target=self._p2p_code_download_thread, args=(save_path, files_to_download), daemon=True).start()
        # Try P2P via HTTP signal if available
        elif getattr(self, '_p2p_available', False) and not hasattr(self, '_p2p_receiver'):
            threading.Thread(target=self._p2p_download_thread, args=(save_path, files_to_download), daemon=True).start()
        else:
            threading.Thread(target=self._download_thread, args=(save_path, files_to_download), daemon=True).start()

    def _p2p_code_download_thread(self, save_path, files_to_download):
        """Download files via already-connected P2P receiver (code-based connection)"""
        try:
            receiver = self._p2p_receiver
            receiver.save_path = save_path
            self._download_start_time = time.time()
            
            self.after(0, lambda: self.status_label.configure(text="🟢 P2P İndiriliyor...", text_color="#06A77D"))
            self.after(0, lambda: self.log_message("P2P ile indirme başlıyor..."))
            
            # Send download request with selected filenames
            filenames = [f['name'] for f in files_to_download]
            receiver.request_download(filenames)
            
            # Wait for transfer to complete
            receiver.wait_for_transfer(timeout=None)
            
            if receiver.status == "stopped":
                raise Exception("Gönderici transferi durdurdu.")
            
            self.after(0, self._on_download_complete, save_path)
            receiver.stop()
            self._p2p_receiver = None
            
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self.log_message(f"P2P indirme hatası: {err_msg}"))
        finally:
            self.after(0, self._reset_download_ui)


    def _p2p_download_thread(self, save_path, files_to_download):
        """Download files via WebRTC P2P DataChannel"""
        try:
            self.after(0, lambda: self.status_label.configure(text="🟢 P2P Bağlanıyor...", text_color="#06A77D"))
            self.after(0, lambda: self.log_message("P2P bağlantısı kuruluyor..."))
            
            receiver = WebRTCReceiver()
            receiver.save_path = save_path
            receiver.log_callback = lambda msg: self.after(0, lambda: self.log_message(f"[P2P] {msg}"))
            
            def p2p_progress(dl, total, speed, current_file, total_files):
                pct = (dl / total * 100) if total else 0
                eta = calculate_eta(total, dl, speed)
                self.after(0, self.update_progress, pct, speed, current_file, total_files, eta)
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
            
            if receiver.status == "stopped":
                 raise Exception("Gönderici transferi durdurdu.")

            self.after(0, lambda: self.status_label.configure(text="🟢 P2P Transfer", text_color="#06A77D"))
            self.after(0, lambda: self.log_message("✅ P2P bağlandı! İndirme isteği gönderiliyor..."))

            # REQUEST DOWNLOAD
            filenames = [f['name'] for f in files_to_download]
            receiver.request_download(filenames)
            
            # Wait for transfer to complete
            receiver.wait_for_transfer(timeout=None)
            
            if receiver.status == "stopped":
                 raise Exception("Gönderici transferi durdurdu.")
            
            # Log P2P history (files_to_download contains only selected)
            duration = time.time() - self._download_start_time if self._download_start_time else 0
            total_size = sum(f['size'] for f in files_to_download) if files_to_download else 0
            avg_speed = total_size / duration if duration > 0 else 0
            for f in files_to_download:
                history.log_transfer(
                    filename=f['name'], size=f['size'],
                    direction="receive", status="success",
                    duration_sec=duration / len(files_to_download) if files_to_download else 0,
                    avg_speed=avg_speed, method="p2p"
                )
            
            self.after(0, self._on_download_complete, save_path)
            receiver.stop()
            
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self.log_message(f"P2P hatası: {err_msg}. HTTP fallback'e geçiliyor..."))
            # Fallback to HTTP download
            self._download_thread(save_path, files_to_download) # Pass filtered list
            
    def _download_thread(self, save_path, files_to_download=None):
        try:
            self._download_start_time = time.time()
            # Update Status to Receiving
            self.after(0, lambda: self.status_label.configure(text="🟢 Dosya İndiriliyor", text_color="#06A77D"))
            self.after(0, lambda: self.log_message(f"İndirme başlatıldı: {save_path}"))

            def cb(dl, total, speed, current_file_index, total_files):
                pct = (dl / total * 100) if total else 0
                eta = calculate_eta(total, dl, speed)
                self.after(0, self.update_progress, pct, speed, current_file_index, total_files, eta)
            
            # Log callback for main thread
            def log_cb(msg):
                self.after(0, lambda: self.log_message(msg))
            
            # If files_to_download is filtered, use download_files
            if files_to_download and len(files_to_download) < len(self.remote_files):
                 self.downloader.download_files(files_to_download, self.download_url, save_path, cb, log_cb)
            else:
                 # Otherwise download all (or filtered if list passed)
                 # Wait, downloader.download_files IS the new way.
                 if files_to_download is None: files_to_download = self.remote_files
                 self.downloader.download_files(files_to_download, self.download_url, save_path, cb, log_cb)
                 
            self.after(0, self._on_download_complete, save_path)
        except Exception as e:
            self.after(0, lambda: ToastNotification.show_toast(self, str(e), type="error"))
            self.after(0, self._reset_download_ui)


    def update_progress(self, pct, speed, current, total, eta=-1):
        self.progress_bar.set(pct / 100)
        eta_str = f" — ~{format_time(eta)} kaldı" if eta >= 0 else ""
        self.progress_label.configure(text=f"Dosya {current}/{total} - %{pct:.1f} ({format_speed(speed)}){eta_str}")

    def _on_download_complete(self, path):
        msg = f"Dosyalar indirildi:\n{path}"
        ToastNotification.show_toast(self, msg, type="success")
        
        if self.tray_manager:
            self.tray_manager.show_notification("İndirme Tamamlandı", f"{os.path.basename(path)} indirildi.")
            
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
