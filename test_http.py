import requests

try:
    print("HTTP isteği gönderiliyor...")
    r = requests.get("https://quickshare-signal.onrender.com/", timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Content: {r.text}")
except Exception as e:
    print(f"Hata: {e}")
