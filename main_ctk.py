"""
QuickShare Main Application - CustomTkinter Version
Modern GUI with CustomTkinter
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import sys
import time
from typing import List, Optional

from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE
from utils import format_size, format_speed, format_time, validate_url, calculate_total_size
from server import set_shared_files, run_server, transfer_monitor
from tunnel_manager import TunnelManager
from downloader import Downloader

# CustomTkinter appearance
ctk.set_appearance_mode("dark")  # "dark" | "light" | "system"
ctk.set_default_color_theme("blue")  # "blue" | "green" | "dark-blue"


class QuickShareApp:
    """QuickShare Ana Uygulama"""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(True, True)
        self.root.minsize(600, 500)
        
        self.mode: Optional[str] = None  # "send" veya "receive"
        self.selected_files: List[str] = []
        self.tunnel_manager: Optional[TunnelManager] = None
        self.server_thread: Optional[threading.Thread] = None
        self.downloader: Optional[Downloader] = None
        self.download_url: Optional[str] = None
        self.remote_files: List[dict] = []
        
        self.show_main_menu()
        
    def run(self):
        """Uygulamayı başlat"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.is_sharing = False  # Sharing flag for metrics loop
        self.root.mainloop()
    
    def on_closing(self):
        """Pencere kapatılıyor"""
        self.is_sharing = False
        # Server ve tunnel'ı durdur
        if self.tunnel_manager:
            self.tunnel_manager.stop()
        
        self.root.destroy()
    
    def clear_window(self):
        """Tüm widget'ları temizle"""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def show_main_menu(self):
        """Ana menü ekranı"""
        self.clear_window()
        self.mode = None
        
        # Ana frame
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(expand=True, fill='both', padx=30, pady=30)
        
        # Başlık
        title = ctk.CTkLabel(
            main_frame,
            text="📦 QuickShare",
            font=("Arial", 28, "bold")
        )
        title.pack(pady=(20, 10))
        
        subtitle = ctk.CTkLabel(
            main_frame,
            text="Hızlı ve Kolay Dosya Paylaşımı",
            font=("Arial", 13)
        )
        subtitle.pack(pady=(0, 30))
        
        # Butonlar
        send_btn = ctk.CTkButton(
            main_frame,
            text="📤 Dosya Gönder",
            command=self.show_sender_screen,
            font=("Arial", 16, "bold"),
            height=60,
            corner_radius=10
        )
        send_btn.pack(pady=15, padx=50, fill='x')
        
        receive_btn = ctk.CTkButton(
            main_frame,
            text="📥 Dosya Al",
            command=self.show_receiver_screen,
            font=("Arial", 16, "bold"),
            height=60,
            corner_radius=10,
            fg_color="#06A77D",
            hover_color="#058c68"
        )
        receive_btn.pack(pady=15, padx=50, fill='x')
    
    # SENDER SCREEN
    def show_sender_screen(self):
        """Gönderen ekranı"""
        self.clear_window()
        self.mode = "send"
        
        # Main frame with scrollable area
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Başlık
        title = ctk.CTkLabel(
            main_frame,
            text="📤 Dosya Gönder",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=(10, 15))
        
        # Dosya seçimi frame
        file_frame = ctk.CTkFrame(main_frame)
        file_frame.pack(fill='x', pady=10, padx=10)
        
        ctk.CTkLabel(file_frame, text="Paylaşılacak Dosyalar:", font=("Arial", 12, "bold")).pack(anchor='w', padx=10, pady=5)
        
        # Dosya listesi (CTkTextbox kullanarak - daha iyi görünüm)
        self.file_textbox = ctk.CTkTextbox(file_frame, height=100, state='disabled')
        self.file_textbox.pack(fill='both', padx=10, pady=5)
        
        # Buton frame
        btn_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        ctk.CTkButton(
            btn_frame,
            text="📁 Dosya Seç",
            command=self.select_files,
            width=120,
            height=32
        ).pack(side='left', padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="📂 Klasör Seç",
            command=self.select_folder,
            width=120,
            height=32
        ).pack(side='left', padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Temizle",
            command=self.clear_files,
            width=100,
            height=32,
            fg_color="#D62246",
            hover_color="#b11d3a"
        ).pack(side='left', padx=5)
        
        # Başlat butonu
        self.start_btn = ctk.CTkButton(
            main_frame,
            text="🚀 Paylaşmaya Başla",
            command=self.start_sharing,
            font=("Arial", 14, "bold"),
            height=45
        )
        self.start_btn.pack(pady=15, padx=10, fill='x')
        
        # URL frame
        self.url_frame = ctk.CTkFrame(main_frame, fg_color="#1a4d2e")
        self.url_frame.pack(fill='x', pady=10, padx=10)
        self.url_frame.pack_forget()
        
        ctk.CTkLabel(
            self.url_frame,
            text="🔗 Paylaşım Linki",
            font=("Arial", 13, "bold"),
            text_color="#90EE90"
        ).pack(pady=(10, 5))
        
        url_entry_frame = ctk.CTkFrame(self.url_frame, fg_color="transparent")
        url_entry_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.url_entry = ctk.CTkEntry(
            url_entry_frame,
            font=("Arial", 12, "bold"),
            state='readonly',
            text_color="#90EE90"
        )
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ctk.CTkButton(
            url_entry_frame,
            text="📋 Kopyala",
            command=self.copy_url_to_clipboard,
            width=100,
            fg_color="#06A77D",
            hover_color="#058c68"
        ).pack(side='right')
        
        # Progress
        # Progress / Metrics Panel (Sender)
        self.sender_metrics_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.sender_metrics_frame.pack(fill='x', pady=5, padx=10)
        self.sender_metrics_frame.pack_forget()

        self.sender_speed_label = ctk.CTkLabel(
            self.sender_metrics_frame, 
            text="", 
            font=("Arial", 12, "bold"), 
            text_color="#90EE90"
        )
        self.sender_speed_label.pack()

        self.sender_total_label = ctk.CTkLabel(
            self.sender_metrics_frame, 
            text="", 
            font=("Arial", 11)
        )
        self.sender_total_label.pack()
        
        # Stop button
        self.stop_btn = ctk.CTkButton(
            main_frame,
            text="⏹️ Paylaşımı Durdur",
            command=self.stop_sharing,
            fg_color="#D62246",
            hover_color="#b11d3a",
            height=40
        )
        self.stop_btn.pack(pady=10, padx=10, fill='x')
        self.stop_btn.pack_forget()
        
        # Geri butonu
        ctk.CTkButton(
            main_frame,
            text="← Geri",
            command=self.show_main_menu,
            width=100,
            height=32,
            fg_color="gray40",
            hover_color="gray30"
        ).pack(pady=5)
    
    # RECEIVER SCREEN
    def show_receiver_screen(self):
        """Alıcı ekranı"""
        self.clear_window()
        self.mode = "receive"
        
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=15)
        
        # Başlık
        ctk.CTkLabel(
            main_frame,
            text="📥 Dosya Al",
            font=("Arial", 20, "bold")
        ).pack(pady=(10, 10))
        
        # URL input
        url_frame = ctk.CTkFrame(main_frame)
        url_frame.pack(fill='x', pady=5, padx=10)
        
        ctk.CTkLabel(url_frame, text="Bağlantı Linki:", font=("Arial", 12, "bold")).pack(anchor='w', padx=10, pady=5)
        
        url_input_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_input_frame.pack(fill='x', padx=10, pady=(0, 8))
        
        self.url_input = ctk.CTkEntry(url_input_frame, placeholder_text="https://...")
        self.url_input.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.url_input.bind('<Return>', lambda e: self.connect_to_url())
        
        self.connect_btn = ctk.CTkButton(
            url_input_frame,
            text="🔗 Bağlan",
            command=self.connect_to_url,
            width=120,
            fg_color="#06A77D",
            hover_color="#058c68"
        )
        self.connect_btn.pack(side='right')
        
        # Dosya listesi - başlangıçta gizli
        self.file_list_frame = ctk.CTkFrame(main_frame)
        # pack_forget yerine pack etmiyoruz, _on_connected'da pack edeceğiz
        
        ctk.CTkLabel(self.file_list_frame, text="📋 Dosyalar:", font=("Arial", 12, "bold")).pack(anchor='w', padx=10, pady=5)
        
        # Textbox - NORMAL state ile oluştur, sonra disable et
        self.remote_file_textbox = ctk.CTkTextbox(self.file_list_frame, height=120)
        self.remote_file_textbox.pack(fill='both', padx=10, pady=5)
        self.remote_file_textbox.configure(state='disabled')
        
        # Toplam boyut label
        self.file_info_label = ctk.CTkLabel(
            self.file_list_frame,
            text="",
            font=("Arial", 11),
            text_color="#aaaaaa"
        )
        self.file_info_label.pack(anchor='w', padx=10, pady=(0, 5))
        
        # İndirme butonu - başlangıçta gizli
        self.download_btn = ctk.CTkButton(
            main_frame,
            text="📦 Tümünü İndir",
            command=self.start_download,
            font=("Arial", 14, "bold"),
            height=45,
            fg_color="#06A77D",
            hover_color="#058c68"
        )
        # pack etmiyoruz - _on_connected'da pack edeceğiz
        
        # Progress frame - başlangıçta gizli
        self.receive_progress_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        # pack etmiyoruz - download başlayınca pack edeceğiz
        
        # Progress bar
        self.receive_progress_bar = ctk.CTkProgressBar(self.receive_progress_container)
        self.receive_progress_bar.pack(fill='x', pady=(0, 5))
        self.receive_progress_bar.set(0)
        
        # Ana metrik satırı (hız, yüzde, kalan süre)
        self.receive_progress_label = ctk.CTkLabel(
            self.receive_progress_container, 
            text="", 
            font=("Arial", 13, "bold"),
            text_color="#90EE90"
        )
        self.receive_progress_label.pack()
        
        # Detay satırı (indirilen/toplam boyut)
        self.receive_detail_label = ctk.CTkLabel(
            self.receive_progress_container,
            text="",
            font=("Arial", 11)
        )
        self.receive_detail_label.pack(pady=(3, 0))
        
        # Geri butonu
        self.back_btn_receiver = ctk.CTkButton(
            main_frame,
            text="← Geri",
            command=self.show_main_menu,
            width=100,
            height=32,
            fg_color="gray40",
            hover_color="gray30"
        )
        self.back_btn_receiver.pack(pady=5)
    
    # SENDER METHODS
    def select_files(self):
        """Dosya seçimi"""
        files = filedialog.askopenfilenames(title="Dosya Seçin")
        if files:
            self.selected_files.extend(files)
            self.update_file_list()
    
    def select_folder(self):
        """Klasör seçimi"""
        folder = filedialog.askdirectory(title="Klasör Seçin")
        if folder:
            self.selected_files.append(folder)
            self.update_file_list()
    
    def clear_files(self):
        """Dosya listesini temizle"""
        self.selected_files = []
        self.update_file_list()
    
    def update_file_list(self):
        """Dosya listesini güncelle"""
        self.file_textbox.configure(state='normal')
        self.file_textbox.delete('1.0', 'end')
        
        for file in self.selected_files:
            import os
            is_dir = os.path.isdir(file)
            prefix = "[KLASÖR] " if is_dir else ""
            self.file_textbox.insert('end', f"{prefix}{file}\n")
        
        self.file_textbox.configure(state='disabled')
    
    def start_sharing(self):
        """Paylaşımı başlat"""
        if not self.selected_files:
            messagebox.showwarning("Uyarı", "Lütfen en az bir dosya veya klasör seçin")
            return
        
        self.start_btn.configure(state='disabled', text="Başlatılıyor...")
        
        # Thread'de başlat
        thread = threading.Thread(target=self._sharing_thread, daemon=True)
        thread.start()
    
    def _sharing_thread(self):
        """Paylaşım thread'i"""
        try:
            # Dosyaları set et
            set_shared_files(self.selected_files)
            
            # Server başlat
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            time.sleep(1)  # Server'ın başlaması için bekle
            
            # Tunnel başlat
            self.tunnel_manager = TunnelManager()
            url = self.tunnel_manager.start()
            
            # UI'ı güncelle
            self.root.after(0, self._on_sharing_started, url)
            
        except Exception as e:
            self.root.after(0, self._on_sharing_error, str(e))
    
    def _on_sharing_started(self, url: str):
        """Paylaşım başarıyla başladı"""
        self.start_btn.configure(state='disabled', text="✅ Paylaşım Aktif")
        
        # URL göster
        self.url_entry.configure(state='normal')
        self.url_entry.delete(0, 'end')
        self.url_entry.insert(0, url)
        self.url_entry.configure(state='readonly')
        self.url_frame.pack(fill='x', pady=10, padx=10)
        
        # Clipboard'a kopyala
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        
        # Progress
        total_size = calculate_total_size(self.selected_files)
        # self.progress_label'ı kaldırdık, yerine metrics_frame kullanıyoruz
        
        # Stop button göster
        self.stop_btn.pack(pady=10, padx=10, fill='x')
        
        # Start metrics loop
        self.is_sharing = True
        self.sender_metrics_frame.pack(pady=5, padx=10, fill='x')
        self.update_sender_stats()
        
        messagebox.showinfo("Başarılı", f"Paylaşım başladı!\n\nURL: {url}\n\nURL otomatik olarak panoya kopyalandı.")

    def update_sender_stats(self):
        """Gönderen istatistiklerini güncelle"""
        if not self.is_sharing:
            return
            
        stats = transfer_monitor.get_stats()
        
        # Format stats
        speed_str = format_speed(stats['speed'])
        total_sent_str = format_size(stats['total_sent'])
        eta_str = format_time(stats['eta'])
        active_str = f"{stats['active']} aktif transfer"
        
        # Update labels (Artık ETA da var)
        self.sender_speed_label.configure(text=f"📤 Hız: {speed_str} | Kalan: {eta_str}")
        self.sender_total_label.configure(text=f"Gönderilen: {total_sent_str} | {active_str}")
        
        # Schedule next update (1s)
        self.root.after(1000, self.update_sender_stats)
    
    def _on_sharing_error(self, error: str):
        """Paylaşım hatası"""
        self.start_btn.configure(state='normal', text="🚀 Paylaşmaya Başla")
        messagebox.showerror("Hata", f"Paylaşım başlatılamadı:\n{error}")
    
    def copy_url_to_clipboard(self):
        """URL'i panoya kopyala"""
        url = self.url_entry.get()
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            messagebox.showinfo("Kopyalandı", "URL panoya kopyalandı!")
    
    def stop_sharing(self):
        """Paylaşımı durdur"""
        if self.tunnel_manager:
            self.tunnel_manager.stop()
            self.tunnel_manager = None
        
        self.is_sharing = False  # Stop metrics loop
        self.url_frame.pack_forget()
        self.stop_btn.pack_forget()
        self.sender_metrics_frame.pack_forget()
        self.start_btn.configure(state='normal', text="🚀 Paylaşmaya Başla")
        
        messagebox.showinfo("Durduruldu", "Paylaşım durduruldu")
    
    # RECEIVER METHODS
    def connect_to_url(self):
        """URL'e bağlan"""
        url = self.url_input.get().strip()
        
        if not url:
            messagebox.showwarning("Uyarı", "Lütfen bir URL girin")
            return
        
        if not validate_url(url):
            messagebox.showwarning("Uyarı", "Geçersiz URL formatı")
            return
        
        self.download_url = url
        self.connect_btn.configure(state='disabled', text="Bağlanıyor...")
        
        thread = threading.Thread(target=self._connect_thread, daemon=True)
        thread.start()
    
    def _connect_thread(self):
        """Bağlantı thread'i"""
        try:
            self.downloader = Downloader()
            self.remote_files = self.downloader.get_file_list(self.download_url)
            
            self.root.after(0, self._on_connected)
            
        except Exception as e:
            self.root.after(0, self._on_connect_error, str(e))
    
    def _on_connected(self):
        """Bağlantı başarılı"""
        self.connect_btn.configure(state='normal', text="🔗 Bağlan")
        
        # Dosya listesi textbox'u güncelle
        self.remote_file_textbox.configure(state='normal')
        self.remote_file_textbox.delete('0.0', 'end')
        
        total_size = 0
        file_count = len(self.remote_files)
        
        for i, file in enumerate(self.remote_files):
            size_str = format_size(file['size'])
            line = f"{file['name']} ({size_str})"
            if i < file_count - 1:
                line += "\n"
            self.remote_file_textbox.insert('end', line)
            total_size += file['size']
        
        self.remote_file_textbox.configure(state='disabled')
        
        # Dosya bilgisi
        self.file_info_label.configure(text=f"📊 {file_count} dosya | Toplam: {format_size(total_size)}")
        
        # Frame'leri göster
        self.file_list_frame.pack(fill='both', pady=5, padx=10)
        self.download_btn.pack(pady=10, padx=10, fill='x')
        
        messagebox.showinfo(
            "Bağlantı Başarılı",
            f"{file_count} dosya bulundu\nToplam boyut: {format_size(total_size)}"
        )
    
    def _on_connect_error(self, error: str):
        """Bağlantı hatası"""
        self.connect_btn.configure(state='normal', text="🔗 Bağlan")
        messagebox.showerror("Hata", f"Bağlantı hatası:\n{error}")
    
    def start_download(self):
        """İndirmeyi başlat"""
        if not self.remote_files:
            return
        
        # Kayıt yeri seç
        save_path = filedialog.askdirectory(title="İndirme Klasörü Seçin")
        if not save_path:
            return
        
        self.download_btn.configure(state='disabled', text="İndiriliyor...")
        self.receive_progress_label.configure(text="İndirme başlıyor...")
        
        thread = threading.Thread(
            target=self._download_thread,
            args=(save_path,),
            daemon=True
        )
        thread.start()
    
    def _download_thread(self, save_path: str):
        """İndirme thread'i"""
        try:
            # İlk olarak dosya sayısını göster
            total_files = len(self.remote_files)
            current_file = [0]  # Mutable counter
            
            def progress_callback(downloaded, total, speed, current_file=0, total_files=0):
                percent = (downloaded / total * 100) if total > 0 else 0
                eta = (total - downloaded) / speed if speed > 0 else 0
                
                # Progress bar güncelle
                self.root.after(0, self.receive_progress_bar.set, percent / 100)
                
                # File count info
                file_info = f"Dosya {current_file}/{total_files} | " if total_files > 0 else ""
                
                # Ana metrik (büyük ve belirgin)
                main_text = f"📥 {file_info}%{percent:.1f} | {format_speed(speed)} | Kalan: {format_time(eta)}"
                
                # Detaylı bilgi
                detail_text = f"İndirilen: {format_size(downloaded)} / {format_size(total)}"
                
                self.root.after(0, self.receive_progress_label.configure, {"text": main_text})
                self.root.after(0, self.receive_detail_label.configure, {"text": detail_text})
            
            # Progress container'ı göster
            self.root.after(0, self.receive_progress_container.pack, {"fill": 'x', "pady": 10, "padx": 10})
            
            self.downloader.download_all(self.download_url, save_path, progress_callback)
            
            self.root.after(0, self._on_download_complete, save_path)
            
        except Exception as e:
            self.root.after(0, self._on_download_error, str(e))
    
    def _on_download_complete(self, save_path: str):
        """İndirme tamamlandı"""
        self.download_btn.configure(state='normal', text="📦 Tümünü İndir")
        self.receive_progress_bar.set(1.0)
        self.receive_progress_label.configure(text="✅ İndirme Tamamlandı!", text_color="#90EE90")
        
        # Detaylı özet
        total_files = len(self.remote_files)
        total_size = sum(f['size'] for f in self.remote_files)
        
        summary = f"🎉 İşlem Tamamlandı!\n\n" \
                  f"📂 Dosya Sayısı: {total_files}\n" \
                  f"💾 Toplam Boyut: {format_size(total_size)}\n" \
                  f"📁 Kayıt Yeri:\n{save_path}"
        
        self.receive_detail_label.configure(text=f"Toplam: {format_size(total_size)} - Başarıyla kaydedildi.")
        
        messagebox.showinfo("İndirme Başarılı", summary)
        
        # Klasörü açmayı dene
        try:
            os.startfile(save_path)
        except:
            pass
    
    def _on_download_error(self, error: str):
        """İndirme hatası"""
        self.download_btn.configure(state='normal', text="📦 Tümünü İndir")
        # Container'ı hemen gizleme, hatayı görsünler
        # self.receive_progress_container.pack_forget()
        
        err_msg = str(error)
        friendly_msg = f"❌ Hata Oluştu\n\n{err_msg}"
        
        if "timed out" in err_msg.lower():
            friendly_msg = "⚠️ Zaman Aşımı (Timeout)\n\nİnternet bağlantısı yavaş veya gönderen yanıt vermiyor."
        elif "connection" in err_msg.lower():
            friendly_msg = "⚠️ Bağlantı Hatası\n\nSunucuya ulaşılamıyor. Gönderen programı kapatmış olabilir."
            
        # Kullanıcıya ZIP seçeneği sun
        if messagebox.askyesno("İndirme Hatası", f"{friendly_msg}\n\nDosyaları tek bir ZIP paketi olarak indirmeyi denemek ister misiniz? (Bu yöntem daha garantilidir)"):
            self.start_zip_download()
        else:
            messagebox.showerror("İndirme Hatası", friendly_msg)
            self.receive_progress_label.configure(text="❌ İndirme Başarısız", text_color="#ff5555")

    def start_zip_download(self):
        """ZIP olarak indirmeyi başlat"""
        if not self.remote_files:
            return
        
        # Kayıt yeri seç
        save_path = filedialog.askdirectory(title="ZIP Dosyasını Kaydetmek İçin Klasör Seçin")
        if not save_path:
            return
        
        self.download_btn.configure(state='disabled', text="ZIP İndiriliyor...")
        self.receive_progress_label.configure(text="ZIP paketi hazırlanıyor...", text_color="white")
        # Container'ı göster (eğer gizlendiyse)
        self.receive_progress_container.pack(fill='x', pady=10, padx=10)
        
        thread = threading.Thread(
            target=self._download_zip_thread,
            args=(save_path,),
            daemon=True
        )
        thread.start()

    def _download_zip_thread(self, save_path: str):
        """ZIP indirme thread'i"""
        try:
            total_size = sum(f['size'] for f in self.remote_files)
            
            def progress_callback(downloaded, total, speed):
                # ZIP indirmede total size tam bilinmeyebilir (chunked encoding),
                # ama yaklaşık olarak dosyaların toplam boyutu kadardır.
                est_total = total_size if total <= 0 else total
                percent = (downloaded / est_total * 100) if est_total > 0 else 0
                
                # Progress bar güncelle
                self.root.after(0, self.receive_progress_bar.set, percent / 100)
                
                main_text = f"📦 ZIP İndiriliyor... %{percent:.1f} | {format_speed(speed)}"
                detail_text = f"İndirilen: {format_size(downloaded)}"
                
                self.root.after(0, self.receive_progress_label.configure, {"text": main_text})
                self.root.after(0, self.receive_detail_label.configure, {"text": detail_text})
            
            self.downloader.download_all_as_zip(self.download_url, save_path, progress_callback)
            
            self.root.after(0, self._on_download_complete, save_path)
            
        except Exception as e:
            # Burası da patlarsa artık yapacak bir şey yok, sadece hata göster
            error_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("ZIP Hatası", f"ZIP indirme de başarısız oldu:\n{error_msg}"))
            self.root.after(0, lambda: self.download_btn.configure(state='normal', text="📦 Tümünü İndir"))


if __name__ == "__main__":
    app = QuickShareApp()
    app.run()
