# QuickShare - Sanal Kablo Dosya Transfer Tool

## 🎯 Proje Özeti

WhatsApp/Telegram üzerinden paylaşılabilen **~3-4MB'lık tek exe dosyası**. İki bilgisayar arasında internet üzerinden direkt dosya transferi - sanal kablo gibi.

## 🛠️ Kullanılan Teknolojiler

- **Python 3.10+**
- **Tkinter** - GUI (built-in, dependency yok)
- **Flask** - HTTP server + streaming
- **Cloudflare Tunnel (cloudflared)** - Public URL oluşturma
- **PyInstaller** - Exe paketleme

## 📁 Proje Yapısı

```
quickshare/
├── README.md                  # Bu dosya
├── IMPLEMENTATION.md          # Faz faz implementasyon planı
├── requirements.txt           # Python dependencies
├── build_exe.py              # PyInstaller build script
├── config.py                 # Konfigürasyon
├── main.py                   # Ana program + GUI
├── server.py                 # Flask server
├── tunnel_manager.py         # Cloudflared yönetimi
├── downloader.py             # Dosya indirme mantığı
├── utils.py                  # Yardımcı fonksiyonlar
└── bin/
    └── cloudflared.exe       # Cloudflare binary (indirilecek)
```

## 🚀 Hızlı Başlangıç

### 1. Dependencies Kur
```bash
pip install -r requirements.txt
```

### 2. Cloudflared İndir
```bash
# Windows için otomatik indirilecek (FAZ 1'de yapılacak)
```

### 3. Programı Çalıştır

**Gönderen Mod:**
```bash
python main.py --send
```

**Alıcı Mod:**
```bash
python main.py --receive
```

### 4. Exe Oluştur
```bash
python build_exe.py
# Çıktı: dist/QuickShare.exe (~3-4 MB)
```

## ⚡ Kullanım Senaryosu

1. **Gönderen**: `QuickShare.exe` çalıştır → "Dosya Gönder" → Dosya seç → Link al
2. **Link paylaş** (WhatsApp/Telegram)
3. **Alıcı**: `QuickShare.exe` çalıştır → "Dosya Al" → Link yapıştır → İndir

## 📊 Beklenen Performans

- **Exe Boyutu**: 3-4 MB
- **Transfer Hızı (LAN)**: 10-12 MB/s
- **Transfer Hızı (İnternet)**: 5-10 MB/s (bağlantıya bağlı)
- **GUI Açılış**: < 2 saniye

## 🎯 Özellikler

✅ Çoklu dosya/klasör desteği  
✅ Progress bar (hız, boyut, kalan süre)  
✅ Otomatik link kopyalama  
✅ Basit GUI  
✅ Kurulum gerektirmez  

❌ Şifre koruması (basitlik için)  
❌ QR kod (basitlik için)  
❌ Resume/devam etme (basitlik için)  

## 📝 Implementasyon Fazları

Detaylı adımlar için: [IMPLEMENTATION.md](IMPLEMENTATION.md)

**FAZ 1**: Proje kurulumu + Cloudflared entegrasyonu  
**FAZ 2**: Flask server + Dosya streaming  
**FAZ 3**: Tkinter GUI (Gönderen mod)  
**FAZ 4**: Download mantığı (Alıcı mod)  
**FAZ 5**: PyInstaller paketleme  
**FAZ 6**: Test + Optimizasyon  

## 🔧 Geliştirme Notları

- Python 3.10+ gerekli (type hints kullanımı)
- Cloudflared binary ~2-3 MB
- Flask production mode kullanılmayacak (yerel kullanım)
- Threading kullanılacak (GUI freeze önleme)

## 📄 Lisans

MIT License - Özgürce kullanılabilir
