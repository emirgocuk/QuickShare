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
WEBRTC_CHUNK_SIZE = 64 * 1024  # 64KB per DataChannel message
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun.cloudflare.com:3478"},
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
