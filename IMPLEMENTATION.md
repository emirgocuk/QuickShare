# QuickShare - Faz Faz İmplementasyon Planı

## 📋 Genel Bakış

Bu doküman QuickShare projesinin faz faz nasıl geliştirileceğini detaylı olarak açıklar. Her faz bağımsız test edilebilir şekilde tasarlanmıştır.

---

## FAZ 1: Proje Kurulumu & Cloudflared Entegrasyonu ⏱️ 45 dakika

### Hedef
Temel proje yapısını kurmak ve Cloudflared'i çalıştırıp test etmek.

### Adımlar

#### 1.1. Proje Yapısını Oluştur
```bash
# Klasörler zaten var, sadece dosyaları dolduracağız
```

#### 1.2. requirements.txt Oluştur
- Flask
- requests
- pyinstaller (build için)

#### 1.3. config.py Oluştur
```python
# Port, chunk size, timeout gibi sabitler
SERVER_PORT = 5000
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
BUFFER_SIZE = 256 * 1024      # 256KB
TIMEOUT = 30                   # saniye
```

#### 1.4. Cloudflared Binary İndir
- Windows için cloudflared.exe indir
- `bin/cloudflared.exe` yoluna yerleştir
- Boyutu kontrol et (~2-3 MB olmalı)

#### 1.5. tunnel_manager.py Oluştur
**Görevler:**
- Cloudflared process'ini başlat
- Public URL'i yakalayıp dön
- Process'i düzgün kapat
- Hata yönetimi

**Test:**
```python
# Test kodu:
if __name__ == "__main__":
    manager = TunnelManager(port=5000)
    url = manager.start()
    print(f"Public URL: {url}")
    input("Press Enter to stop...")
    manager.stop()
```

#### 1.6. Test Et
✅ Cloudflared başlatılabiliyor mu?  
✅ Public URL alınıyor mu?  
✅ Process düzgün kapanıyor mu?  

### Teslim Çıktıları
- ✅ `config.py` çalışıyor
- ✅ `tunnel_manager.py` test edildi
- ✅ `cloudflared.exe` indirildi ve çalışıyor

---

## FAZ 2: Flask Server & Dosya Streaming ⏱️ 1.5 saat

### Hedef
Dosyaları HTTP üzerinden stream edebilen Flask server yazmak.

### Adımlar

#### 2.1. server.py Oluştur

**Endpoints:**
```python
GET  /              → Dosya listesi (JSON)
GET  /download      → Tüm dosyalar ZIP olarak (stream)
GET  /file/<name>   → Tek dosya (stream)
GET  /ping          → Health check
POST /status        → Transfer durumu (opsiyonel)
```

#### 2.2. Dosya Listesi Endpoint
```python
@app.route('/')
def list_files():
    # Seçili dosyaların listesini JSON dön
    return {
        "files": [
            {"name": "video.mp4", "size": 1234567, "path": "..."},
            ...
        ]
    }
```

#### 2.3. Tek Dosya Streaming
```python
@app.route('/file/<filename>')
def download_file(filename):
    # Chunk-by-chunk streaming
    # Response.stream_with_context kullan
```

#### 2.4. ZIP Streaming (Çoklu Dosya)
```python
@app.route('/download')
def download_all():
    # zipfile ile on-the-fly zip oluştur
    # Stream olarak gönder
```

#### 2.5. utils.py - Helper Fonksiyonlar
```python
def format_size(bytes: int) -> str:
    """1234567 -> '1.18 MB'"""
    
def format_speed(bytes_per_sec: float) -> str:
    """1234567 -> '1.18 MB/s'"""
    
def format_time(seconds: int) -> str:
    """125 -> '2m 5s'"""
```

#### 2.6. Test Et
```bash
# Terminal 1: Server başlat
python server.py

# Terminal 2: Test dosyası indir
curl http://localhost:5000/file/test.txt -o test_downloaded.txt
```

✅ Dosya listeleniyor mu?  
✅ Tek dosya indiriliyor mu?  
✅ Çoklu dosya ZIP olarak indiriliyor mu?  
✅ Progress gösterilebiliyor mu?  

### Teslim Çıktıları
- ✅ `server.py` çalışıyor
- ✅ `utils.py` helper fonksiyonları hazır
- ✅ Streaming test edildi

---

## FAZ 3: GUI - Gönderen Mod ⏱️ 1.5 saat

### Hedef
Tkinter ile basit GUI oluştur - Gönderen modu.

### Adımlar

#### 3.1. main.py - Ana Pencere
```python
# Tkinter window setup
# Ana menü: [Dosya Gönder] [Dosya Al]
```

#### 3.2. Gönderen Ekranı
**Bileşenler:**
- Dosya seçme butonu (tkinter.filedialog)
- Seçili dosya listesi (Listbox)
- "Başlat" butonu
- URL gösterimi (Entry + Kopyala butonu)
- Progress bar (ttk.Progressbar)
- Transfer bilgileri (Label: hız, boyut, kalan süre)

#### 3.3. İş Akışı Entegrasyonu
1. Kullanıcı dosya seçer
2. "Başlat" → Thread'de server başlatılır
3. Thread'de tunnel başlatılır
4. URL alınıp gösterilir
5. Transfer başladığında progress güncellenir

#### 3.4. Threading Yapısı
```python
# GUI freeze olmaması için:
- Flask server thread'de çalışacak
- Cloudflared ayrı process
- Progress update için periodic callback
```

#### 3.5. Test Et
✅ GUI açılıyor mu?  
✅ Dosya seçimi çalışıyor mu?  
✅ Server + tunnel başlatılıyor mu?  
✅ URL gösteriliyor ve kopyalanıyor mu?  
✅ Progress bar güncelleniyor mu?  

### Teslim Çıktıları
- ✅ `main.py` gönderen modu çalışıyor
- ✅ Threading düzgün
- ✅ GUI responsive

---

## FAZ 4: İndirme Mantığı - Alıcı Mod ⏱️ 1 saat

### Hedef
URL'den dosya indirme mantığını yazıp GUI'ye entegre et.

### Adımlar

#### 4.1. downloader.py Oluştur
```python
class Downloader:
    def download_file(url: str, save_path: str, progress_callback):
        # requests.get(url, stream=True)
        # Chunk-by-chunk indir
        # Her chunk'ta progress_callback çağır
```

#### 4.2. Alıcı GUI Ekranı
**Bileşenler:**
- URL girişi (Entry)
- "Bağlan" butonu
- Dosya listesi (Listbox - uzak sunucudan alınacak)
- Kayıt yeri seçimi (tkinter.filedialog.askdirectory)
- "İndir" butonu
- Progress bar + bilgiler

#### 4.3. İş Akışı
1. Kullanıcı URL girer
2. "Bağlan" → GET / yapılır (dosya listesi alınır)
3. Dosyalar gösterilir
4. Kullanıcı kayıt yeri seçer
5. "İndir" → Thread'de download başlar
6. Progress güncellenir

#### 4.4. Hata Yönetimi
- URL geçersiz ise hata göster
- Bağlantı hatası
- Disk dolu hatası
- Network timeout

#### 4.5. Test Et
✅ URL girişi çalışıyor mu?  
✅ Dosya listesi alınıyor mu?  
✅ İndirme çalışıyor mu?  
✅ Progress doğru gösteriliyor mu?  
✅ Hatalar düzgün yakalanıyor mu?  

### Teslim Çıktıları
- ✅ `downloader.py` çalışıyor
- ✅ Alıcı modu GUI'de entegre
- ✅ İki PC arası test yapıldı

---

## FAZ 5: PyInstaller Paketleme ⏱️ 45 dakika

### Hedef
Tek exe dosyası oluştur.

### Adımlar

#### 5.1. build_exe.py Oluştur
```python
import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',  # Console gizle
    '--name=QuickShare',
    '--icon=icon.ico',  # İsteğe bağlı
    '--add-binary=bin/cloudflared.exe;.',
    '--hidden-import=tkinter',
    '--clean',
])
```

#### 5.2. İkon Hazırla (Opsiyonel)
- Basit bir ikon oluştur veya indir
- `icon.ico` olarak kaydet

#### 5.3. Build Et
```bash
python build_exe.py
# Çıktı: dist/QuickShare.exe
```

#### 5.4. Test Et
✅ Exe çalışıyor mu?  
✅ Boyut 5 MB'ın altında mı?  
✅ Cloudflared embed edilmiş mi?  
✅ GUI açılıyor mu?  
✅ Tüm fonksiyonlar çalışıyor mu?  

#### 5.5. Optimizasyon
- UPX compression (opsiyonel, boyutu küçültür)
- Gereksiz modülleri çıkar

### Teslim Çıktıları
- ✅ `build_exe.py` hazır
- ✅ `QuickShare.exe` oluşturuldu
- ✅ Exe boyutu < 5 MB
- ✅ Tüm özellikler çalışıyor

---

## FAZ 6: Test & Optimizasyon ⏱️ 1-2 saat

### Hedef
Gerçek senaryolarda test et ve optimize et.

### Adımlar

#### 6.1. Yerel Test
- Aynı PC'de gönderen/alıcı mod
- Küçük dosya (1 MB)
- Büyük dosya (100 MB)
- Çoklu dosya (klasör)

#### 6.2. Gerçek Test
- İki farklı Windows PC
- Farklı ağlar (WiFi, mobil hotspot)
- 500 MB - 1 GB dosya
- Hız ölçümü

#### 6.3. Hata Senaryoları
- Network kesilirse ne olur?
- Disk dolu
- URL yanlış
- Server kapanırsa

#### 6.4. Performans Optimizasyonu
- Chunk size ayarla (8MB optimal mi?)
- Buffer size ayarla
- Thread sayısı optimize et

#### 6.5. UX İyileştirmeleri
- Hata mesajları daha açıklayıcı
- Butonlar disable/enable doğru mu?
- Progress bar smooth mu?

#### 6.6. Güvenlik Test
- Antivirüs taraması
- Windows Defender False positive var mı?

### Test Checklist

**Fonksiyonel Testler:**
- [ ] Tek dosya gönderme/alma
- [ ] Çoklu dosya gönderme/alma
- [ ] Klasör gönderme/alma
- [ ] 10 MB dosya - hız testi
- [ ] 100 MB dosya - hız testi
- [ ] 1 GB dosya - hız testi
- [ ] WhatsApp'tan exe paylaşma
- [ ] Link kopyalama
- [ ] Progress bar doğruluğu

**Hata Testleri:**
- [ ] Yanlış URL girişi
- [ ] Network kesintisi
- [ ] Disk dolu
- [ ] Server crash
- [ ] Cloudflared başlatılamama

**Performans Testleri:**
- [ ] Exe boyutu < 5 MB
- [ ] GUI açılış < 2 saniye
- [ ] LAN hızı > 10 MB/s
- [ ] İnternet hızı > 5 MB/s
- [ ] Memory kullanımı < 100 MB

### Teslim Çıktıları
- ✅ Tüm testler geçti
- ✅ Performans hedeflere ulaştı
- ✅ Bilinen buglar düzeltildi
- ✅ Final exe hazır

---

## 🎯 Başarı Kriterleri

Her fazın sonunda aşağıdakiler sağlanmalı:

### FAZ 1
- [x] Cloudflared çalışıyor
- [x] Public URL alınabiliyor

### FAZ 2
- [x] Flask server dosya sunuyor
- [x] Streaming çalışıyor
- [x] ZIP desteği var

### FAZ 3
- [x] GUI çalışıyor
- [x] Dosya seçimi çalışıyor
- [x] URL gösteriliyor

### FAZ 4
- [x] URL'den indirme çalışıyor
- [x] Progress bar doğru

### FAZ 5
- [x] Exe oluşturuluyor
- [x] Boyut < 5 MB

### FAZ 6
- [x] Tüm testler geçti
- [x] Performans OK

---

## 📊 Zaman Tahmini

| Faz | Süre | Kümülatif |
|-----|------|-----------|
| FAZ 1 | 45 dk | 45 dk |
| FAZ 2 | 1.5 saat | 2h 15m |
| FAZ 3 | 1.5 saat | 3h 45m |
| FAZ 4 | 1 saat | 4h 45m |
| FAZ 5 | 45 dk | 5h 30m |
| FAZ 6 | 1-2 saat | 6h 30m - 7h 30m |

**Toplam: ~6-8 saat**

---

## 🚀 Başlamadan Önce Checklist

- [ ] Python 3.10+ kurulu
- [ ] pip çalışıyor
- [ ] Git kurulu (opsiyonel)
- [ ] İnternet bağlantısı var (cloudflared indirme için)
- [ ] Windows (test ortamı)

---

## 📝 Notlar

- Her faz sonunda commit yap (git kullanıyorsan)
- Her faz bağımsız test edilebilir
- Sorun çıkarsa önceki faza dön
- Optimizasyonu en sona bırak (premature optimization kaça)

---

## 🎓 Öğrenilecekler

Bu projeyi tamamladığında şunları öğrenmiş olacaksın:
- Flask streaming API
- Tkinter GUI + Threading
- Cloudflare Tunnel kullanımı
- PyInstaller ile exe paketleme
- HTTP chunk transfer
- Progress tracking
- Error handling best practices

İyi çalışmalar! 🚀

---
---

# 🔮 QuickShare v2.0 — İyileştirme Yol Haritası

> Yukarıdaki fazlar tamamlandı. Aşağıdaki yol haritası projeyi production-ready seviyesine taşımak içindir.

---

## FAZ 7: P2P Transfer Performansı ⚡

**Hedef:** Transfer hızını 258 KB/s → 5-15 MB/s çıkarmak  
**Durum:** ✅ TAMAMLANDI

### Yapılan Değişiklikler (İlk Aşama)

- [x] `config.py` — Chunk boyutu 16KB → 64KB (Geçici genel iyileştirme)
- [x] `webrtc_manager.py` — Buffer threshold `CHUNK_SIZE*4` → `CHUNK_SIZE*16` (1 MB)  
- [x] `webrtc_manager.py` — Adaptive sleep: sabit 50ms → 1-50ms exponential backoff
- [x] ~~Unordered DataChannel~~ — İPTAL (raw binary'de sıra bozulursa dosya çöker)

### Yapılacaklar (İleri Seviye)

- [ ] **Adaptive Chunking (Dinamik Parçalama)** — `webrtc_manager.py`
  - Dosya boyutuna göre chunk belirleme (Küçük dosyalar için 16-32KB, devasa dosyalar için 128-256KB max)
  - Ağ darboğazına (congestion) göre anlık chunk boyutu büyütme/küçültme
- [ ] **Binary Header Optimizasyonu** — `webrtc_manager.py`
  - Dosya metadatalarını JSON yerine raw binary gönderme

---

## FAZ 8: Güvenilirlik & Hata Yönetimi 🔄

**Hedef:** Kesilmelerde otomatik devam, veri doğrulama  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **Transfer Resume** — `webrtc_manager.py`, `downloader.py`
  - Dosya offset tracking
  - HTTP `Range` header desteği
  - Yarım kalan dosyayı kaldığı yerden devam
- [ ] **Chunk Hash Doğrulama** — `webrtc_manager.py`
  - Her N chunk'ta mini-hash
  - Bozuk veri algılama ve yeniden isteme
- [ ] **Otomatik Yeniden Bağlanma** — `webrtc_manager.py`
  - ICE restart mekanizması
  - 3 deneme sonra HTTP fallback
- [ ] **Heartbeat/Ping-Pong** — `webrtc_manager.py`
  - Her 5 saniyede ping
  - Stale bağlantı algılama (15s timeout)
- [ ] **Graceful Error Handling** — `main_ctk.py`
  - Tüm thread'lere try/catch
  - UI'da anlamlı hata mesajları (messagebox yerine toast)

---

## FAZ 9: Güvenlik & Şifreleme 🔒

**Hedef:** Uçtan uca iletişim güvenliği  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **E2E Şifreleme** — `webrtc_manager.py`
  - DTLS zaten var, ek AES-256-GCM katmanı (opsiyonel)
- [ ] **Transfer Şifresi** — `server.py`, `main_ctk.py`
  - Opsiyonel parola koruması (PIN ile link paylaşımı)
- [ ] **Token Doğrulama** — `server.py`
  - Her indirme isteği için tek kullanımlık token
- [ ] **Rate Limiting** — `server.py`
  - IP bazlı istek limiti (brute-force koruması)

---

## FAZ 10: Ağ Dayanıklılığı & NAT Traversal 🌐

**Hedef:** Her ağ topolojisinde çalışma  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **TURN Sunucusu** — `config.py`
  - Ücretsiz TURN (Metered.ca veya self-hosted coturn)
  - Simetrik NAT arkasında P2P imkanı
- [ ] **NAT Tipi Algılama** — Yeni: `nat_detector.py`
  - STUN ile NAT tipi tespit (Cone/Symmetric)
  - UI'da bilgi gösterimi
- [ ] **ICE Candidate Filtering** — `webrtc_manager.py`
  - Relay-only mod (simetrik NAT durumunda)
- [ ] **Çoklu Sinyal Sunucusu** — `config.py`
  - Yedek signaling URL'leri (Render down olursa fallback)
- [ ] **Bağlantı Kalitesi** — `main_ctk.py`
  - Ping, jitter, paket kaybı → sidebar'da göster

---

## FAZ 11: UX & Kullanılabilirlik ✨

**Hedef:** Profesyonel kullanıcı deneyimi  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **Toast Bildirimleri** — Yeni: `toast.py`
  - `messagebox` yerine modern toast notification
- [ ] **QR Kod** — `main_ctk.py`
  - Paylaşım kodu/linki için QR kod gösterme
- [ ] **Dosya Önizleme** — `main_ctk.py`
  - Resim/video thumbnail
- [ ] **Tema Sistemi** — `main_ctk.py`
  - Light / Dark / System tema seçeneği
- [ ] **Sürükle-Bırak İyileştirme** — `main_ctk.py`
  - Drop zone overlay animasyonu
- [ ] **Dosya Bazlı Progress** — `ui_components.py`
  - TreeView'da her dosya için minik progress bar
- [ ] **İndirme Geçmişi Detay** — `history_frame.py`
  - Grafik, istatistik, dosya bazlı hız analizi

---

## FAZ 12: Ölçeklenebilirlik & Yeni Özellikler 🚀

**Hedef:** Çoklu cihaz, klasör senkronizasyonu  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **Çoklu Peer** — `webrtc_manager.py`
  - Aynı anda birden fazla alıcıya gönderim
- [ ] **Klasör İzleme** — Yeni: `folder_watcher.py`
  - watchdog ile klasör değişikliği algılama
  - Otomatik paylaşım
- [ ] **Sıkıştırma** — `webrtc_manager.py`
  - Opsiyonel zstd/lz4 sıkıştırma
  - Tekst dosyalarında %60-80 kazanç
- [ ] **Chunked Upload API** — `server.py`
  - Büyük dosyaları parçalı upload

---

## FAZ 13: Üretim Kalitesi & Dağıtım 📦

**Hedef:** Taşınabilir, güncellenebilir, izlenebilir uygulama  
**Durum:** ⬜ BEKLEMEDE

### Yapılacaklar

- [ ] **Yapılandırılmış Loglama** — Yeni: `logger.py`
  - `print()` → `logging` modülü
  - Log dosyası + log seviyeleri
- [ ] **Otomatik Güncelleme** — Yeni: `updater.py`
  - GitHub Releases API ile versiyon kontrolü
- [ ] **Tek Dosya EXE** — `build_ctk.py`
  - Nuitka/PyInstaller ile optimize build
- [ ] **Windows Installer** — Yeni: `installer.iss`
  - Inno Setup ile kurulum sihirbazı
- [ ] **Hata Raporlama** — `main_ctk.py`
  - Crash handler + hata log dosyası
- [ ] **Birim Testleri** — `tests/`
  - WebRTC, Downloader, Server için pytest suite

---

## 📊 v2.0 Zaman Tahmini

| Faz | Süre | Öncelik |
|-----|------|---------|
| FAZ 7 — Performans | ✅ Tamamlandı | 🔴 Kritik |
| FAZ 8 — Güvenilirlik | ~2 oturum | 🔴 Kritik |
| FAZ 9 — Güvenlik | ~1 oturum | 🟡 Orta |
| FAZ 10 — NAT Traversal | ~2 oturum | 🟡 Orta |
| FAZ 11 — UX | ~2 oturum | 🟢 Düşük |
| FAZ 12 — Özellikler | ~3 oturum | 🟢 Düşük |
| FAZ 13 — Üretim | ~2 oturum | 🟡 Orta |

> **Önerilen sıra:** 7 → 8 → 10 → 9 → 11 → 12 → 13
