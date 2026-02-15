"""
QuickShare Main Application
GUI ve ana program mantığı
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import time
from typing import List, Optional

from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE
from utils import format_size, format_speed, format_time, validate_url, calculate_total_size
from server import set_shared_files, run_server
from tunnel_manager import TunnelManager
from downloader import Downloader


class QuickShareApp:
    """Ana uygulama sınıfı"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        
        # State
        self.mode: Optional[str] = None  # "send" veya "receive"
        self.selected_files: List[str] = []
        self.public_url: Optional[str] = None
        self.tunnel_manager: Optional[TunnelManager] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Ana menüyü göster
        self.show_main_menu()
        
    def show_main_menu(self):
        """Ana menü ekranı: Gönder/Al seçimi"""
        # Önceki frame'i temizle
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.mode = None
        
        # Ana frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Başlık
        title_label = tk.Label(
            main_frame, 
            text="QuickShare", 
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=20)
        
        subtitle = tk.Label(
            main_frame,
            text="Hızlı Dosya Transferi",
            font=("Arial", 10)
        )
        subtitle.pack(pady=5)
        
        # Butonlar frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(expand=True)
        
        # Gönder butonu
        send_btn = tk.Button(
            button_frame,
            text="📤 Dosya Gönder",
            width=20,
            height=2,
            font=("Arial", 12),
            command=self.show_send_screen
        )
        send_btn.pack(pady=10)
        
        # Al butonu
        receive_btn = tk.Button(
            button_frame,
            text="📥 Dosya Al",
            width=20,
            height=2,
            font=("Arial", 12),
            command=self.show_receive_screen
        )
        receive_btn.pack(pady=10)
        
    def show_send_screen(self):
        """Gönderen mod ekranı"""
        # Önceki frame'i temizle
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.mode = "send"
        self.selected_files = []
        
        # Ana frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Başlık
        title = tk.Label(
            main_frame, 
            text="📤 Dosya Gönder", 
            font=("Arial", 16, "bold"),
            fg="#2E86AB"
        )
        title.pack(pady=15)
        
        # Dosya seçimi bölümü
        file_frame = tk.LabelFrame(main_frame, text="Dosyalar", padx=10, pady=10)
        file_frame.pack(fill='both', expand=True, pady=10)
        
        # Dosya listesi
        self.file_listbox = tk.Listbox(file_frame, height=6)
        self.file_listbox.pack(fill='both', expand=True)
        
        # Dosya seçme butonları
        btn_frame = tk.Frame(file_frame)
        btn_frame.pack(fill='x', pady=5)
        
        select_file_btn = tk.Button(btn_frame, text="Dosya Seç", command=self.select_files)
        select_file_btn.pack(side='left', padx=2)
        
        select_folder_btn = tk.Button(btn_frame, text="Klasör Seç", command=self.select_folder)
        select_folder_btn.pack(side='left', padx=2)
        
        clear_btn = tk.Button(btn_frame, text="Temizle", command=self.clear_files)
        clear_btn.pack(side='left', padx=2)
        
        # Başlat butonu
        self.start_btn = tk.Button(
            main_frame, 
            text="🚀 Paylaşmaya Başla",
            font=("Arial", 12, "bold"),
            bg="#2E86AB",
            fg="white",
            height=2,
            cursor="hand2",
            command=self.start_sharing
        )
        self.start_btn.pack(pady=15)
        
        # URL bölümü - Daha görünür ve büyük
        self.url_frame = tk.LabelFrame(
            main_frame, 
            text="🔗 Paylaşım Linki", 
            padx=15, 
            pady=15,
            font=("Arial", 11, "bold"),
            fg="#06A77D"
        )
        self.url_frame.pack(fill='x', pady=10)
        self.url_frame.pack_forget()  # Başlangıçta gizli
        
        url_entry_frame = tk.Frame(self.url_frame)
        url_entry_frame.pack(fill='x')
        
        self.url_entry = tk.Entry(
            url_entry_frame, 
            font=("Arial", 12, "bold"),
            state='readonly',
            bg="#F0F8FF",
            fg="#0066CC",
            relief="solid",
            borderwidth=2
        )
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        copy_btn = tk.Button(
            url_entry_frame, 
            text="📋 Kopyala",
            font=("Arial", 10, "bold"),
            bg="#06A77D",
            fg="white",
            cursor="hand2",
            command=self.copy_url_to_clipboard
        )
        copy_btn.pack(side='right')
        
        # Progress bölümü
        self.progress_frame = tk.Frame(main_frame)
        self.progress_frame.pack(fill='x', pady=10)
        self.progress_frame.pack_forget()  # Başlangıçta gizli
        
        self.progress_label = tk.Label(
            self.progress_frame, 
            text="Bekleniyor...",
            font=("Arial", 10),
            fg="#555555"
        )
        self.progress_label.pack()
        
        # Geri butonu
        back_btn = tk.Button(main_frame, text="← Geri", command=self.show_main_menu)
        back_btn.pack(pady=5)
        
    def show_receive_screen(self):
        """Alıcı mod ekranı"""
        # Önceki frame'i temizle
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.mode = "receive"
        
        # State
        self.remote_files = []
        self.download_url = None
        
        # Ana frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Başlık
        title = tk.Label(
            main_frame, 
            text="📥 Dosya Al", 
            font=("Arial", 16, "bold"),
            fg="#06A77D"
        )
        title.pack(pady=15)
        
        # URL girişi
        url_frame = tk.LabelFrame(main_frame, text="Bağlantı Linki", padx=10, pady=10)
        url_frame.pack(fill='x', pady=10)
        
        url_input_frame = tk.Frame(url_frame)
        url_input_frame.pack(fill='x')
        
        self.url_input = tk.Entry(url_input_frame, font=("Arial", 10))
        self.url_input.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.url_input.bind('<Return>', lambda e: self.connect_to_url())
        
        self.connect_btn = tk.Button(
            url_input_frame,
            text="🔗 Bağlan",
            font=("Arial", 10, "bold"),
            bg="#06A77D",
            fg="white",
            cursor="hand2",
            command=self.connect_to_url
        )
        self.connect_btn.pack(side='right')
        
        # Dosya listesi
        self.file_list_frame = tk.LabelFrame(main_frame, text="Dosyalar", padx=10, pady=10)
        self.file_list_frame.pack(fill='both', expand=True, pady=10)
        self.file_list_frame.pack_forget()  # Başlangıçta gizli
        
        self.remote_file_listbox = tk.Listbox(self.file_list_frame, height=8)
        self.remote_file_listbox.pack(fill='both', expand=True)
        
        # İndirme butonu
        self.download_btn = tk.Button(
            main_frame,
            text="📦 Tümünü İndir",
            font=("Arial", 12, "bold"),
            bg="#06A77D",
            fg="white",
            height=2,
            cursor="hand2",
            command=self.start_download
        )
        self.download_btn.pack(pady=15)
        self.download_btn.pack_forget()  # Başlangıçta gizli
        
        # Progress bölümü
        self.receive_progress_frame = tk.Frame(main_frame)
        self.receive_progress_frame.pack(fill='x', pady=10)
        self.receive_progress_frame.pack_forget()
        
        self.receive_progress_label = tk.Label(
            self.receive_progress_frame, 
            text="",
            font=("Arial", 10),
            fg="#555555"
        )
        self.receive_progress_label.pack()
        
        # Geri butonu
        back_btn = tk.Button(main_frame, text="← Geri", command=self.show_main_menu)
        back_btn.pack(pady=5)

        
    def select_files(self):
        """Dosya seçim dialog'u aç"""
        files = filedialog.askopenfilenames(title="Dosya Seç")
        if files:
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
                    self.file_listbox.insert(tk.END, file)
    
    def select_folder(self):
        """Klasör seçim dialog'u aç"""
        folder = filedialog.askdirectory(title="Klasör Seç")
        if folder:
            if folder not in self.selected_files:
                self.selected_files.append(folder)
                self.file_listbox.insert(tk.END, f"[KLASÖR] {folder}")
    
    def clear_files(self):
        """Seçili dosyaları temizle"""
        self.selected_files = []
        self.file_listbox.delete(0, tk.END)
    
    def start_sharing(self):
        """Paylaşımı başlat (thread'de)"""
        if not self.selected_files:
            messagebox.showwarning("Uyarı", "Lütfen en az bir dosya veya klasör seçin")
            return
        
        # Butonu devre dışı bırak
        self.start_btn.config(state='disabled', text="Başlatılıyor...")
        
        # Thread'de başlat
        thread = threading.Thread(target=self._start_sharing_thread, daemon=True)
        thread.start()
    
    def _start_sharing_thread(self):
        """Paylaşım thread'i - server ve tunnel başlatır"""
        try:
            # Server'a dosyaları set et
            set_shared_files(self.selected_files)
            
            # Tunnel manager oluştur
            self.tunnel_manager = TunnelManager()
            
            # Server'ı thread'de başlat
            self.server_thread = threading.Thread(
                target=run_server,
                kwargs={'port': 5000, 'debug': False},
                daemon=True
            )
            self.server_thread.start()
            
            # Server'ın başlaması için kısa bir süre bekle
            time.sleep(1)
            
            # Tunnel başlat ve URL al
            self.root.after(0, lambda: self.progress_label.config(text="Tunnel oluşturuluyor..."))
            
            self.public_url = self.tunnel_manager.start()
            
            # UI'yi güncelle (main thread'de)
            self.root.after(0, self._on_sharing_started)
            
        except Exception as e:
            self.root.after(0, lambda: self._on_sharing_error(str(e)))
    
    def _on_sharing_started(self):
        """Paylaşım başladığında UI güncellemesi"""
        # URL'i göster
        self.url_entry.config(state='normal')
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, self.public_url)
        self.url_entry.config(state='readonly')
        
        self.url_frame.pack(fill='x', pady=10)
        
        # Progress güncelle
        total_size = calculate_total_size(self.selected_files)
        self.progress_label.config(
            text=f"Paylaşım aktif - Toplam boyut: {format_size(total_size)}"
        )
        self.progress_frame.pack(fill='x', pady=10)
        
        # Button'u güncelle
        self.start_btn.config(
            state='normal',
            text="Paylaşımı Durdur",
            bg="#D62246",
            command=self.stop_sharing
        )
        
        messagebox.showinfo(
            "Başarılı",
            f"Paylaşım başlatıldı!\n\nLink kopyalandı (Ctrl+C ile de kopyalayabilirsiniz)"
        )
        
        # Otomatik kopyala
        self.copy_url_to_clipboard()
    
    def _on_sharing_error(self, error_msg: str):
        """Paylaşım hatası"""
        messagebox.showerror("Hata", f"Paylaşım başlatılamadı:\n{error_msg}")
        self.start_btn.config(state='normal', text="Paylaşmaya Başla")
    
    def stop_sharing(self):
        """Paylaşımı durdur"""
        if self.tunnel_manager:
            self.tunnel_manager.stop()
            self.tunnel_manager = None
        
        self.url_frame.pack_forget()
        self.progress_frame.pack_forget()
        
        self.start_btn.config(
            state='normal',
            text="Paylaşmaya Başla",
            bg="#2E86AB",
            command=self.start_sharing
        )
        
        messagebox.showinfo("Bilgi", "Paylaşım durduruldu")
    
    def connect_to_url(self):
        """URL'e bağlan ve dosya listesi al"""
        url = self.url_input.get().strip()
        
        if not url:
            messagebox.showwarning("Uyarı", "Lütfen bir URL girin")
            return
        
        if not validate_url(url):
            messagebox.showwarning("Uyarı", "Geçersiz URL formatı")
            return
        
        self.download_url = url
        self.connect_btn.config(state='disabled', text="Bağlanıyor...")
        
        # Thread'de bağlan
        thread = threading.Thread(target=self._connect_thread, daemon=True)
        thread.start()
    
    def _connect_thread(self):
        """Bağlantı thread'i"""
        try:
            downloader = Downloader()
            self.remote_files = downloader.get_file_list(self.download_url)
            
            # UI'yi güncelle
            self.root.after(0, self._on_connected)
            
        except Exception as e:
            self.root.after(0, lambda: self._on_connect_error(str(e)))
    
    def _on_connected(self):
        """Bağlantı başarılı"""
        self.connect_btn.config(state='normal', text="Bağlan")
        
        # Dosya listesini göster
        self.remote_file_listbox.delete(0, tk.END)
        
        total_size = 0
        for file in self.remote_files:
            size_str = format_size(file['size'])
            self.remote_file_listbox.insert(tk.END, f"{file['name']} ({size_str})")
            total_size += file['size']
        
        self.file_list_frame.pack(fill='both', pady=10)  # expand=True KALDIRILDI
        self.download_btn.pack(pady=15)  # Güncellenen spacing
        
        messagebox.showinfo(
            "Başarılı",
            f"{len(self.remote_files)} dosya bulundu\nToplam boyut: {format_size(total_size)}"
        )
    
    def _on_connect_error(self, error_msg: str):
        """Bağlantı hatası"""
        self.connect_btn.config(state='normal', text="Bağlan")
        messagebox.showerror("Hata", f"Bağlantı kurulamadı:\n{error_msg}")
    
    def start_download(self):
        """İndirmeyi başlat"""
        if not self.remote_files:
            return
        
        # Kayıt yeri seç
        save_path = filedialog.askdirectory(title="İndirme Klasörü Seçin")
        if not save_path:
            return
        
        self.download_btn.config(state='disabled', text="İndiriliyor...")
        self.receive_progress_frame.pack(fill='x', pady=10)
        
        # Thread'de indir
        thread = threading.Thread(
            target=self._download_thread,
            args=(save_path,),
            daemon=True
        )
        thread.start()
    
    def _download_thread(self, save_path: str):
        """İndirme thread'i"""
        try:
            downloader = Downloader()
            
            def progress_callback(downloaded, total, speed):
                percent = (downloaded / total * 100) if total > 0 else 0
                eta = calculate_eta(total, downloaded, speed)
                
                status_text = (
                    f"İndiriliyor: {percent:.1f}% | "
                    f"{format_size(downloaded)}/{format_size(total)} | "
                    f"{format_speed(speed)} | "
                    f"Kalan: {format_time(eta)}"
                )
                
                self.root.after(0, lambda: self.receive_progress_label.config(text=status_text))
            
            # Tüm dosyaları ZIP olarak indir
            downloader.download_all(self.download_url, save_path, progress_callback)
            
            # Başarılı
            self.root.after(0, lambda: self._on_download_complete(save_path))
            
        except Exception as e:
            self.root.after(0, lambda: self._on_download_error(str(e)))
    
    def _on_download_complete(self, save_path: str):
        """İndirme tamamlandı"""
        self.download_btn.config(state='normal', text="Tümünü İndir")
        self.receive_progress_label.config(text="İndirme tamamlandı!")
        
        messagebox.showinfo(
            "Başarılı",
            f"Dosyalar indirildi:\n{save_path}\download.zip"
        )
    
    def _on_download_error(self, error_msg: str):
        """İndirme hatası"""
        self.download_btn.config(state='normal', text="Tümünü İndir")
        self.receive_progress_label.config(text="Hata oluştu")
        messagebox.showerror("Hata", f"İndirme başarısız:\n{error_msg}")
    
    def copy_url_to_clipboard(self):
        """Public URL'i clipboard'a kopyala"""
        if self.public_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.public_url)
    
    def run(self):
        """Uygulamayı başlat"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Pencere kapatılırken cleanup"""
        if self.tunnel_manager:
            self.tunnel_manager.stop()
        self.root.destroy()


def main():
    """Ana fonksiyon"""
    app = QuickShareApp()
    app.run()


if __name__ == "__main__":
    main()

