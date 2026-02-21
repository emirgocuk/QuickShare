# QuickShare - WebRTC Tabanlı P2P Dosya Transfer Uygulaması

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-green.svg" alt="CustomTkinter">
  <img src="https://img.shields.io/badge/Transfer-WebRTC%20P2P-orange.svg" alt="WebRTC">
  <img src="https://img.shields.io/badge/Multi--Peer-1:N-red.svg" alt="Multi-Peer">
</div>

## 🎯 Proje Özeti
QuickShare, bilgisayarlar arasında internet üzerinden veya yerel ağda **sınır olmadan, yüksek hızda ve doğrudan (Peer-to-Peer)** dosya transferi yapmanızı sağlayan modern bir masaüstü uygulamasıdır.

Bulut tünel limitlerini (ör. Cloudflare'in 100 MB sınırı) aşmak ve aracı sunucu maliyetlerini ortadan kaldırmak için **WebRTC DataChannels** kullanılarak baştan aşağı yenilenmiştir.

## ✨ Temel Özellikler

| Özellik | Açıklama |
|---|---|
| ⚡ **Sınırsız P2P Transfer** | Dosyalar buluta yüklenmez, cihazdan cihaza doğrudan akar. Boyut/hız sınırı yok. |
| 👥 **Çoklu Alıcı (1:N)** | Aynı oda kodunu giren birden fazla kişi aynı anda dosyaları indirebilir. |
| 🔄 **Adaptive Chunking** | İnternet hızına göre paket boyutu otomatik ayarlanır (16KB–256KB). |
| 💾 **Kopan Transferi Devam Ettirme** | Bağlantı koparsa kaldığı byte'dan devam eder (Resume). |
| � **P2P Parola Koruması** | İsteğe bağlı PIN/parola ile oda erişimi kilitlenebilir. |
| 🌐 **NAT Traversal** | STUN/TURN sunucuları ile simetrik NAT arkasındaki cihazlara bile ulaşır. |
| 🛡️ **Bütünlük Kontrolü** | SHA-256 hash doğrulaması ile dosyalar bozulmadan iletilir. |
| 🎨 **Modern Arayüz** | CustomTkinter ile karanlık mod destekli şık masaüstü arayüzü. |
| 📦 **Klasör & Çoklu Dosya** | Tek seferde birden fazla dosya veya tüm klasör seçilebilir. |

## 🛠️ Kullanılan Teknolojiler
- **Python 3.10+**
- **aiortc** — WebRTC P2P bağlantı ve DataChannel
- **CustomTkinter** — Modern Desktop GUI
- **Flask** — Lokal HTTP sunucusu (bulut modu)
- **HTTP Long-Polling** — Sinyal sunucusu (Render üzerinde barındırılıyor)
- **aiohttp** — Asenkron HTTP istemci

## 📁 Proje Yapısı
```text
quickshare/
├── main_ctk.py                # Ana uygulama giriş noktası (GUI)
├── webrtc_manager.py          # WebRTC Sender/Receiver + SignalingClient
├── server.py                  # Flask HTTP sunucusu (bulut modu + fallback)
├── config.py                  # STUN/TURN, timeout, sinyal URL ayarları
├── utils.py                   # Ağ ve dosya yardımcı fonksiyonları
├── tunnel_manager.py          # Cloudflared tünel yönetimi (bulut modu)
├── transfer_history.py        # Transfer geçmişi takibi
├── build_ctk.py               # PyInstaller ile .exe oluşturma
├── test_multipeer.py          # Çoklu P2P entegrasyon testi
└── web/                       # Web arayüzü dosyaları
```

## 🚀 Kurulum ve Çalıştırma

### 1. Gereksinimleri Yükleyin
```bash
pip install -r requirements.txt
```

### 2. Uygulamayı Başlatın
```bash
python main_ctk.py
```

### 3. Exe Oluşturma (Opsiyonel)
```bash
python build_ctk.py
```

## ⚡ Kullanım

### Gönderen
1. Uygulamayı açın, **"Dosya Seç"** ile dosyalarınızı belirleyin
2. **"Doğrudan P2P"** butonuna basın — size bir **Oda Kodu** üretilecek
3. Bu kodu alıcı(lar) ile paylaşın

### Alıcı
1. QuickShare'i açın, **"Al"** sekmesine geçin
2. Oda kodunu girin ve **"Bağlan"** butonuna basın
3. Dosya listesi gelince indirmek istediklerinizi seçin — transfer başlar

> **Not:** Birden fazla alıcı aynı oda kodunu girerek eşzamanlı olarak dosyaları indirebilir.

## 🧪 Test
Çoklu P2P transferini otomatik test etmek için:
```bash
python test_multipeer.py
```
Bu test 1 sender + 2 receiver oluşturup canlı sinyal sunucusu üzerinden dosya transferi yapar ve hash doğrulaması ile sonucu kontrol eder.

## 📄 Lisans
MIT License — Özgürce kullanabilir, geliştirebilir ve kendi projelerinizde kaynak belirterek uyarlayabilirsiniz.
