"""
QuickShare System Tray Manager
Arka planda çalışma ve bildirimler için
"""

import pystray
from PIL import Image, ImageDraw
import threading
import sys
import tkinter as tk

class TrayManager:
    def __init__(self, app, title="QuickShare"):
        self.app = app
        self.title = title
        self.icon = None
        self._create_icon()
        
    def _create_icon(self):
        # Create a simple icon programmatically
        # Blue circle with "QS" text or just a shape
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(30, 30, 30))
        dc = ImageDraw.Draw(image)
        
        # Draw circle
        dc.ellipse((8, 8, 56, 56), fill="#3B8ED0", outline="#3B8ED0")
        
        # Draw "Q" (simplified as rectangle for now)
        dc.rectangle((20, 20, 44, 44), fill="white")
        
        self.image = image
        
        # Menu
        menu = pystray.Menu(
            pystray.MenuItem("Göster", self.show_app),
            pystray.MenuItem("Çıkış", self.quit_app)
        )
        
        self.icon = pystray.Icon(self.title, self.image, self.title, menu)
        
    def run(self):
        """Run tray icon in background thread"""
        threading.Thread(target=self.icon.run, daemon=True).start()
        
    def show_app(self, icon=None, item=None):
        """Restore window from tray"""
        self.app.after(0, self.app.deiconify)
        self.app.after(0, self.app.lift)
        self.app.after(0, self.app.focus_force)
        
    def quit_app(self, icon=None, item=None):
        """Quit application"""
        self.icon.stop()
        self.app.after(0, self.app.exit_app)
        
    def show_notification(self, title, message):
        """Show system notification"""
        if self.icon:
            self.icon.notify(message, title)

    def stop(self):
        if self.icon:
            self.icon.stop()
