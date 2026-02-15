"""
QuickShare Tunnel Manager
Cloudflared process yönetimi ve public URL oluşturma
"""

import subprocess
import time
import re
import os
import sys
from typing import Optional
from threading import Thread
from config import CLOUDFLARED_BINARY, CLOUDFLARED_STARTUP_TIMEOUT, SERVER_PORT


class TunnelManager:
    """Cloudflared tunnel yönetimi"""
    
    def __init__(self, port: int = SERVER_PORT):
        """
        Args:
            port: Tunnel edilecek local port
        """
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self._url_found = False
        
    def _get_cloudflared_path(self) -> str:
        """Cloudflared binary yolunu al (exe içindeyken de çalışacak)"""
        if getattr(sys, 'frozen', False):
            # PyInstaller ile paketlenmişse
            base_path = sys._MEIPASS
        else:
            # Normal Python çalıştırmada
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        cloudflared_path = os.path.join(base_path, CLOUDFLARED_BINARY)
        
        if not os.path.exists(cloudflared_path):
            raise FileNotFoundError(
                f"cloudflared.exe bulunamadı: {cloudflared_path}\n"
                f"Lütfen {CLOUDFLARED_BINARY} dosyasını indirin."
            )
        
        return cloudflared_path
        
    def start(self) -> str:
        """
        Cloudflared tunnel başlat ve public URL al
        
        Returns:
            Public URL (örn: https://abc123.trycloudflare.com)
            
        Raises:
            RuntimeError: Tunnel başlatılamazsa veya URL alınamazsa
        """
        cloudflared_path = self._get_cloudflared_path()
        
        # Cloudflared komutunu hazırla
        cmd = [
            cloudflared_path,
           "tunnel",
            "--url", f"http://127.0.0.1:{self.port}",
            "--no-autoupdate"
        ]
        
        try:
            # Process'i başlat (stdout ve stderr'ı yakala)
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # URL'i yakalamak için thread başlat
            url_thread = Thread(target=self._read_output)
            url_thread.daemon = True
            url_thread.start()
            
            # URL bulunana kadar bekle (timeout ile)
            start_time = time.time()
            while not self._url_found:
                if time.time() - start_time > CLOUDFLARED_STARTUP_TIMEOUT:
                    self.stop()
                    raise RuntimeError(
                        f"Cloudflared {CLOUDFLARED_STARTUP_TIMEOUT}s içinde URL oluşturamadı"
                    )
                
                # Process çökmüş mü kontrol et
                if self.process.poll() is not None:
                    self.stop()
                    raise RuntimeError("Cloudflared beklenmedik şekilde kapandı")
                
                time.sleep(0.1)
            
            return self.public_url
            
        except FileNotFoundError:
            raise RuntimeError(f"cloudflared.exe çalıştırılamadı: {cloudflared_path}")
        except Exception as e:
            self.stop()
            raise RuntimeError(f"Tunnel başlatılamadı: {e}")
    
    def _read_output(self):
        """Process output'unu okuyup URL'i yakala"""
        # Regex pattern: https://XXXX.trycloudflare.com
        url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
        
        for line in self.process.stdout:
            if self._url_found:
                break
                
            # URL'i ara
            match = url_pattern.search(line)
            if match:
                self.public_url = match.group(0)
                self._url_found = True
                break
    
    def stop(self):
        """Tunnel'ı kapat"""
        if self.process is None:
            return
        
        try:
            # Terminate ile kapat
            self.process.terminate()
            
            # 5 saniye bekle
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Hala çalışıyorsa kill et
                self.process.kill()
                self.process.wait()
        
        except Exception:
            pass  # Zaten kapanmış olabilir
        
        finally:
            self.process = None
            self.public_url = None
            self._url_found = False
    
    def is_running(self) -> bool:
        """
        Tunnel çalışıyor mu kontrol et
        
        Returns:
            True if running, False otherwise
        """
        return self.process is not None and self.process.poll() is None


# Test kodu
if __name__ == "__main__":
    print("Testing TunnelManager...")
    
    manager = TunnelManager(port=5000)
    
    try:
        print("Starting tunnel...")
        url = manager.start()
        print(f"✅ Public URL: {url}")
        
        print(f"\nTunnel is running: {manager.is_running()}")
        print("\nPress Enter to stop tunnel...")
        input()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        print("Stopping tunnel...")
        manager.stop()
        print("✅ Tunnel stopped")
        print(f"Tunnel is running: {manager.is_running()}")

