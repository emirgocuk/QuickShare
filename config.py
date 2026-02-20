"""
QuickShare Configuration
Tüm sabit değerler ve ayarlar bu dosyada
"""

# Server Ayarları
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

# Transfer Ayarları
# Transfer Ayarları
CHUNK_SIZE = 64 * 1024           # 64 KB (smoother progress bars)
BUFFER_SIZE = 256 * 1024           # 256 KB (file read buffer)
MAX_FILE_SIZE = 50 * 1024 * 1024 * 1024  # 50 GB limit (opsiyonel)

# Network Ayarları
TIMEOUT = 120                      # saniye (connection timeout - artırıldı)
MAX_RETRIES = 5                    # connection retry sayısı (artırıldı)

# Cloudflared Ayarları
CLOUDFLARED_BINARY = "bin/cloudflared.exe"
CLOUDFLARED_STARTUP_TIMEOUT = 30   # Tunnel URL alınana kadar max bekleme (saniye)

# WebRTC P2P Ayarları
WEBRTC_CHUNK_SIZE = 16 * 1024  # 16KB per DataChannel message (smaller = better SCTP throughput)
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun.cloudflare.com:3478"},
    # TURN Server Örneği (Simetrik NAT için gereklidir)
    # {
    #     "urls": "turn:your-turn-server.com:3478",
    #     "username": "user",
    #     "credential": "password"
    # }
]
WEBRTC_TIMEOUT = 15  # P2P bağlantı kurulma süresi (saniye)

# GUI Ayarları
WINDOW_WIDTH = 650
WINDOW_HEIGHT = 650
WINDOW_TITLE = "QuickShare v1.0"

# Progress Update
PROGRESS_UPDATE_INTERVAL = 100     # millisaniye (GUI update frequency)

# Renkler (opsiyonel - gelecek için)
PRIMARY_COLOR = "#2E86AB"
SUCCESS_COLOR = "#06A77D"
ERROR_COLOR = "#D62246"

# Debug
DEBUG = True                       # False yapılacak production'da
LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR

# Tunnel Configuration
CF_TUNNEL_TOKEN = ""
CF_TUNNEL_URL = ""
DUCKDNS_DOMAIN = ""
DUCKDNS_TOKEN = ""
USE_DUCKDNS = False

SIGNALING_SERVER_URL = "https://quickshare-signal.onrender.com"

# Load config from file if exists
import json
import os

CONFIG_FILE = "config.json"

def load_config():
    global CF_TUNNEL_TOKEN, CF_TUNNEL_URL, DUCKDNS_DOMAIN, DUCKDNS_TOKEN, USE_DUCKDNS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                CF_TUNNEL_TOKEN = data.get("cf_tunnel_token", "")
                CF_TUNNEL_URL = data.get("cf_tunnel_url", "")
                DUCKDNS_DOMAIN = data.get("duckdns_domain", "")
                DUCKDNS_TOKEN = data.get("duckdns_token", "")
                USE_DUCKDNS = data.get("use_duckdns", False)
        except:
            pass

def save_config(cf_token, cf_url, duckdns_domain="", duckdns_token="", use_duckdns=False):
    global CF_TUNNEL_TOKEN, CF_TUNNEL_URL, DUCKDNS_DOMAIN, DUCKDNS_TOKEN, USE_DUCKDNS
    CF_TUNNEL_TOKEN = cf_token
    CF_TUNNEL_URL = cf_url
    DUCKDNS_DOMAIN = duckdns_domain
    DUCKDNS_TOKEN = duckdns_token
    USE_DUCKDNS = use_duckdns
    
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "cf_tunnel_token": cf_token,
                "cf_tunnel_url": cf_url,
                "duckdns_domain": duckdns_domain,
                "duckdns_token": duckdns_token,
                "use_duckdns": use_duckdns
            }, f)
    except:
        pass

load_config()
