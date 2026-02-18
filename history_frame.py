"""
QuickShare History UI Frame
Transfer geçmişini listeleyen ve filtreleyen UI bileşeni
"""

import customtkinter as ctk
from transfer_history import history
from utils import format_size, format_time, format_speed

class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self._setup_header()
        
        # Table (Scrollable Frame)
        self.table_frame = ctk.CTkScrollableFrame(self, label_text="Transfer Geçmişi")
        self.table_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_frame.grid_columnconfigure(1, weight=1) # Filename column expands
        
        # Initial Load
        self.refresh()
        
    def _setup_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="Geçmiş İşlemler", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        # Refresh Button
        ctk.CTkButton(header, text="🔄 Yenile", command=self.refresh, width=80).pack(side="right", padx=5)
        
        # Clear Button
        ctk.CTkButton(header, text="🗑️ Temizle", command=self.clear_history, fg_color="#D62246", hover_color="#b11d3a", width=80).pack(side="right", padx=5)

    def refresh(self):
        """Tabloyu yenile"""
        # Clear existing
        for widget in self.table_frame.winfo_children():
            widget.destroy()
            
        data = history.get_recent(100)
        
        if not data:
            ctk.CTkLabel(self.table_frame, text="Henüz kayıt yok.", text_color="gray").pack(pady=20)
            return

        # Headers (Optional, simple list for now)
        # Row 0: Headers
        # ...
        
        for i, item in enumerate(data):
            self._create_row(i, item)

    def _create_row(self, index, item):
        row_frame = ctk.CTkFrame(self.table_frame)
        row_frame.pack(fill="x", pady=5)
        
        # Icon / Direction
        icon = "📤" if item['direction'] == "send" else "📥"
        color = "#06A77D" if item['status'] == "success" else "#D62246"
        
        ctk.CTkLabel(row_frame, text=icon, font=ctk.CTkFont(size=20)).pack(side="left", padx=10)
        
        # Info
        info_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        name_lbl = ctk.CTkLabel(info_frame, text=item['filename'], font=ctk.CTkFont(weight="bold"), anchor="w")
        name_lbl.pack(fill="x")
        
        detail_text = f"{format_size(item['size'])} • {item['timestamp'][:16].replace('T', ' ')}"
        if item.get('avg_speed'):
            detail_text += f" • {format_speed(item['avg_speed'])}"
        if item.get('duration_sec'):
            detail_text += f" • {format_time(item['duration_sec'])}"
            
        ctk.CTkLabel(info_frame, text=detail_text, font=ctk.CTkFont(size=12), text_color="gray", anchor="w").pack(fill="x")
        
        # Status / Hash
        status_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        status_frame.pack(side="right", padx=10)
        
        status_text = "Başarılı" if item['status'] == "success" else "Hata"
        ctk.CTkLabel(status_frame, text=status_text, text_color=color).pack(anchor="e")
        
        if item.get('hash'):
            hash_icon = "✅" if item['hash'] == "verified" else "⚠️" if item['hash'] == "skipped" else "❌"
            ctk.CTkLabel(status_frame, text=f"Hash: {hash_icon}", font=ctk.CTkFont(size=12)).pack(anchor="e")
            
    def clear_history(self):
        history.clear()
        self.refresh()
