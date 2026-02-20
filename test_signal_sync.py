import socketio
import time

sio = socketio.Client()

@sio.event
def connect():
    print("Bağlandı (Sync)! Sunucuya erişim başarılı.")
    sio.disconnect()

@sio.event
def connect_error(data):
    print(f"Bağlantı Hatası: {data}")

try:
    print("Sunucuya bağlanılıyor: https://quickshare-signal.onrender.com")
    sio.connect('https://quickshare-signal.onrender.com')
    sio.wait()
except Exception as e:
    print(f"Bağlantı başarısız: {e}")
