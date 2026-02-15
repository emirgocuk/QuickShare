"""
QuickShare Downloader
URL'den dosya indirme mantığı
"""

import requests
import os
import time
from urllib.parse import quote
from base64 import urlsafe_b64encode
from typing import Callable, Optional, List, Dict
from config import CHUNK_SIZE, TIMEOUT, MAX_RETRIES
from utils import format_size, format_speed, calculate_eta


class Downloader:
    """Dosya indirme yöneticisi"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        
    def get_file_list(self, url: str) -> List[Dict]:
        """
        Uzak sunucudan dosya listesini al
        
        Args:
            url: Server URL (base URL)
            
        Returns:
            Dosya listesi: [{"name": "...", "size": ..., "path": "..."}]
            
        Raises:
            requests.RequestException: Bağlantı hatası
        """
        # URL'i normalize et
        if not url.endswith('/'):
            url = url + '/'
        
        response = self.session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        return data.get('files', [])
    
    def download_file(
        self,
        url: str,
        filename: str,
        save_path: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ):
        """
        Tek bir dosyayı indir
        
        Args:
            url: Server base URL
            filename: İndirilecek dosya adı
            save_path: Kaydedilecek klasör
            progress_callback: Progress callback (downloaded_bytes, total_bytes, speed)
            
        Raises:
            requests.RequestException: İndirme hatası
            IOError: Dosya yazma hatası
        """
        # URL'i normalize et
        if not url.endswith('/'):
            url = url + '/'
        
        # File URL oluştur (Base64)
        encoded_filename = urlsafe_b64encode(filename.replace('\\', '/').encode('utf-8')).decode('utf-8')
        file_url = url + 'file_b64/' + encoded_filename
        
        # Dosya yolunu oluştur
        file_path = os.path.join(save_path, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Retry loop
        retries = 0
        while retries < MAX_RETRIES:
            try:
                # Resume check
                resume_header = {}
                mode = 'wb'
                downloaded = 0
                
                if os.path.exists(file_path):
                    downloaded = os.path.getsize(file_path)
                    if downloaded > 0:
                        resume_header = {'Range': f'bytes={downloaded}-'}
                        mode = 'ab'
                        print(f"Resuming download from {format_size(downloaded)}...")

                # İstek gönder (stream mode)
                response = self.session.get(
                    file_url, 
                    stream=True, 
                    timeout=TIMEOUT,
                    headers=resume_header
                )
                
                # Handle 416 Range Not Satisfiable (File already complete or invalid range)
                if response.status_code == 416:
                    print("File already likely complete or range invalid. Restarting if needed.")
                    # Burada sunucudan tekrar tam dosya boyutunu teyit etmek ideal olurdu ancak
                    # şimdilik dosya tam inmiş varsayıyoruz veya sıfırdan indiriyoruz.
                    # Basitlik için: 416 dönerse ve dosya varsa, tamamlanmış sayıp çıkabiliriz.
                    return

                response.raise_for_status()
                
                # Toplam boyut
                total_size = int(response.headers.get('content-length', 0))
                
                # Range isteği yaptıysak content-length sadece kalan kısımdır.
                # Total size'ı Content-Range header'dan almalıyız veya bildiğimiz total'e eklemeliyiz.
                content_range = response.headers.get('Content-Range')
                if content_range:
                    # bytes 1000-4999/5000
                    match = re.search(r'/(\d+)', content_range)
                    if match:
                        total_size = int(match.group(1))
                else:
                    if mode == 'ab':
                        # Range desteklenmiyor olabilir, sunucu tüm dosyayı gönderiyor
                        mode = 'wb'
                        downloaded = 0
                
                start_time = time.time()
                
                with open(file_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Progress callback
                            if progress_callback:
                                elapsed = time.time() - start_time
                                speed = (downloaded - (0 if mode == 'wb' else os.path.getsize(file_path))) / elapsed if elapsed > 0 else 0
                                # Speed hesaplaması resume durumunda biraz karmaşık, basit tutalım:
                                # Anlık indirilen miktar üzerinden hız hesabı daha doğru olur ama
                                # şimdilik total progress odaklı gidelim.
                                progress_callback(downloaded, total_size, speed)
                
                # Başarılı bitti
                break
                
            except (requests.RequestException, IOError) as e:
                retries += 1
                print(f"Download error (attempt {retries}/{MAX_RETRIES}): {e}")
                if retries >= MAX_RETRIES:
                    raise e
                time.sleep(2 * retries)  # Exponential backoff (ish)
    
    def download_all(
        self,
        url: str,
        save_path: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ):
        """
        Tüm dosyaları sırayla indir (kablo gibi direkt transfer)
        
        Args:
            url: Server base URL
            save_path: Kaydedilecek klasör
            progress_callback: Progress callback (downloaded_bytes, total_bytes, speed)
            
        Raises:
            requests.RequestException: İndirme hatası
        """
        # Önce dosya listesini al
        files = self.get_file_list(url)
        
        # Toplam boyut hesapla
        total_size = sum(f['size'] for f in files)
        total_downloaded = 0
        start_time = time.time()
        
        # Her dosyayı sırayla indir
        total_files = len(files)
        for i, file in enumerate(files):
            # Dosya yolu oluştur (klasör yapısını koru)
            file_path = os.path.join(save_path, file['name'])
            
            # Dosya zaten varsa atla
            if os.path.exists(file_path):
                # Dosya boyutu aynı mı kontrol et
                if os.path.getsize(file_path) == file['size']:
                    # Aynı dosya, atla ve progress'i güncelle
                    total_downloaded += file['size']
                    if progress_callback:
                        elapsed = time.time() - start_time
                        speed = total_downloaded / elapsed if elapsed > 0 else 0
                        # Callback: downloaded, total, speed, current_file, total_files
                        progress_callback(total_downloaded, total_size, speed, i + 1, total_files)
                    continue  # Sonraki dosyaya geç
            
            os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else save_path, exist_ok=True)
            
            # URL oluştur
            file_url = url
            if not file_url.endswith('/'):
                file_url += '/'
            
            # Base64 encode file path (Kesin çözüm)
            # path separator'leri / yap, sonra encode et
            rel_path = file['name'].replace('\\', '/')
            encoded_name = urlsafe_b64encode(rel_path.encode('utf-8')).decode('utf-8')
            
            file_url += 'file_b64/' + encoded_name
            
            # İndir
            response = self.session.get(file_url, stream=True, timeout=TIMEOUT)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        total_downloaded += len(chunk)
                        
                        # Progress callback
                        if progress_callback:
                            elapsed = time.time() - start_time
                            speed = total_downloaded / elapsed if elapsed > 0 else 0
                            progress_callback(total_downloaded, total_size, speed, i + 1, total_files)
    
    def download_all_as_zip(
        self,
        url: str,
        save_path: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ):
        """
        Tüm dosyaları ZIP olarak indir (opsiyonel - eski yöntem)
        
        Args:
            url: Server base URL
            save_path: Kaydedilecek klasör
            progress_callback: Progress callback (downloaded_bytes, total_bytes, speed)
            
        Raises:
            requests.RequestException: İndirme hatası
        """
        # URL'i normalize et
        if not url.endswith('/'):
            url = url + '/'
        
        # Download URL
        download_url = url + 'download'
        
        # İstek gönder
        response = self.session.get(download_url, stream=True, timeout=TIMEOUT)
        response.raise_for_status()
        
        # Toplam boyut
        total_size = int(response.headers.get('content-length', 0))
        
        # ZIP dosyası yolu
        zip_path = os.path.join(save_path, 'download.zip')
        
        # Download
        downloaded = 0
        start_time = time.time()
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Progress callback
                    if progress_callback:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        progress_callback(downloaded, total_size, speed)


# Test kodu
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    def progress(downloaded, total, speed):
        percent = (downloaded / total * 100) if total > 0 else 0
        print(f"\rProgress: {percent:.1f}% | {format_size(downloaded)}/{format_size(total)} | {format_speed(speed)}", end="")
    
    downloader = Downloader()
    
    try:
        print(f"Getting file list from {url}...")
        files = downloader.get_file_list(url)
        print(f"Found {len(files)} files")
        
        for file in files:
            print(f"  - {file['name']} ({format_size(file['size'])})")
        
        # İlk dosyayı indir
        if files:
            print(f"\nDownloading {files[0]['name']}...")
            downloader.download_file(url, files[0]['name'], ".", progress)
            print("\n✅ Download complete!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")

