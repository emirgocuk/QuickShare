"""
QuickShare Downloader
URL'den dosya indirme mantığı
"""

import requests
import os
import time
import re
from urllib.parse import quote
from base64 import urlsafe_b64encode
from typing import Callable, Optional, List, Dict
from config import CHUNK_SIZE, TIMEOUT, MAX_RETRIES
from utils import format_size, format_speed, calculate_eta, calculate_file_hash


class Downloader:
    """Dosya indirme yöneticisi"""
    
    def __init__(self, proxies: Optional[Dict] = None):
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        if proxies:
            self.session.proxies.update(proxies)
        
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
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Tek bir dosyayı indir
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
                        msg = f"Resuming download from {format_size(downloaded)}..."
                        print(msg)
                        if log_callback: log_callback(msg)

                # İstek gönder (stream mode)
                response = self.session.get(
                    file_url,
                    stream=True,
                    timeout=TIMEOUT,
                    headers=resume_header
                )
                
                # Handle 416 Range Not Satisfiable
                if response.status_code == 416:
                    msg = "File already complete or range invalid."
                    print(msg)
                    if log_callback: log_callback(msg)
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
        
        # Verify Hash
        print("Verifying file integrity...")
        try:
            # Server'dan hash al
            hash_url = url + 'hash/' + quote(filename)
            hash_response = self.session.get(hash_url, timeout=TIMEOUT)
            
            if hash_response.status_code == 200:
                server_hash = hash_response.json().get('hash')
                local_hash = calculate_file_hash(file_path)
                
                if server_hash == local_hash:
                    print("✅ Hash verification SUCCESSFUL")
                else:
                    print(f"❌ Hash verification FAILED!")
                    print(f"   Server: {server_hash}")
                    print(f"   Local:  {local_hash}")
                    # Opsiyonel: Dosyayı sil veya yeniden indir?
                    # Şimdilik sadece uyarı veriyoruz.
            else:
                print(f"⚠️ Could not get hash from server (Status: {hash_response.status_code})")
                
        except Exception as e:
            print(f"⚠️ Hash verification skipped: {e}")
    
    def download_all(
        self,
        url: str,
        save_path: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Tüm dosyaları sırayla indir (Resumable)
        
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
        
        # Daha önce ne kadar indirilmiş?
        # Bu biraz karmaşık çünkü her dosyanın ne kadar indiğini diskten bakmalıyız
        total_downloaded = 0
        
        # Global start time
        start_time = time.time()
        
        # Her dosya için callback wrapper
        def file_progress_wrapper(file_downloaded, file_total, file_speed, current_file_idx, total_files_count):
            # Global progress'i hesaplamamız lazım
            # Bu callback tek bir dosya için progress veriyor.
            # Global progress için state tutmalıyız veya basitçe "artış" miktarını eklemeliyiz.
            # Ancak download_file stateless.
            
            # Basit Yöntem:
            # Şu anki dosyanın indirilen kısmını, önceki dosyaların tamamlanmış boyutuna ekle.
            nonlocal total_downloaded
            
            # Toplam indirilen = (Şu ana kadar biten dosyalar) + (Şu anki dosyanın indirilen kısmı)
            current_total = finished_files_size + file_downloaded
            
            elapsed = time.time() - start_time
            avg_speed = current_total / elapsed if elapsed > 0 else 0
            
            if progress_callback:
                progress_callback(current_total, total_size, avg_speed, current_file_idx, total_files_count)

        finished_files_size = 0
        total_files = len(files)

        for i, file in enumerate(files):
            msg = f"Downloading {file['name']} ({i+1}/{total_files})..."
            print(msg)
            if log_callback: log_callback(msg)
            
            # Wrapper callback oluştur
            file_cb = lambda d, t, s: file_progress_wrapper(d, t, s, i + 1, total_files)
            
            # İndir (Retry ve Resume logic'i download_file içinde)
            try:
                self.download_file(url, file['name'], save_path, file_cb, log_callback)
            except Exception as e:
                err_msg = f"Error downloading {file['name']}: {e}"
                print(err_msg)
                if log_callback: log_callback(err_msg)
                # Bir dosya başarısız olursa tüm işlemi durdurmalı mıyız?
                # Evet, raise edelim.
                raise e
            
            # Dosya bitti, boyutunu global sayaca ekle
            finished_files_size += file['size']
    
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

