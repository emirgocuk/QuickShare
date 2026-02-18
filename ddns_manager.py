"""
QuickShare DDNS Manager
DuckDNS kullanarak dinamik DNS güncellemesi ve public URL oluşturma
"""

import requests
import socket
from config import SERVER_PORT

class DDNSManager:
    """DuckDNS güncelleme yöneticisi"""
    
    def __init__(self, domain, token, port=SERVER_PORT):
        self.domain = domain
        self.token = token
        self.port = port
        self.public_ip = None
        
    def update(self):
        """DuckDNS kaydını güncelle"""
        if not self.domain or not self.token:
            raise ValueError("Domain ve token gerekli")
            
        try:
            # 1. Public IP'yi öğren (opsiyonel, DuckDNS otomatik algılayabilir ama bazen explicit iyidir)
            # DuckDNS auto-detects request IP if 'ip' parameter is omitted.
            
            # 2. Update DuckDNS
            url = f"https://www.duckdns.org/update?domains={self.domain}&token={self.token}&verbose=true"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200 and response.text.startswith("OK"):
                print(f"DuckDNS update successful for {self.domain}")
                return True
            else:
                raise Exception(f"DuckDNS update failed: {response.text}")
                
        except Exception as e:
            raise RuntimeError(f"DDNS güncelleme hatası: {e}")

    def get_public_url(self):
        """Public URL oluştur"""
        return f"http://{self.domain}.duckdns.org:{self.port}"
