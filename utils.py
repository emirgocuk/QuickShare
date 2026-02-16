"""
QuickShare Utility Functions
Yardımcı fonksiyonlar
"""

import os
import hashlib
from typing import List, Dict


def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """
    Dosyanın SHA256 hash'ini hesapla
    
    Args:
        filepath: Dosya yolu
        chunk_size: Okuma buffer boyutu
        
    Returns:
        Hex digest string
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read the file in chunks to avoid using too much memory
        for byte_block in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def format_size(bytes_count: int) -> str:
    """
    Byte sayısını okunabilir formata çevir
    
    Args:
        bytes_count: Byte cinsinden boyut
        
    Returns:
        Formatlanmış string (örn: "1.23 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def format_speed(bytes_per_second: float) -> str:
    """
    Transfer hızını okunabilir formata çevir
    
    Args:
        bytes_per_second: Saniyede byte sayısı
        
    Returns:
        Formatlanmış string (örn: "15.3 MB/s")
    """
    return f"{format_size(int(bytes_per_second))}/s"


def format_time(seconds: int) -> str:
    """
    Saniyeyi okunabilir süreye çevir
    
    Args:
        seconds: Saniye cinsinden süre
        
    Returns:
        Formatlanmış string (örn: "2m 35s" veya "1h 5m")
    """
    if seconds < 0:
        return "Hesaplanıyor..."
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def calculate_eta(total_bytes: int, downloaded_bytes: int, speed_bps: float) -> int:
    """
    Kalan süreyi hesapla
    
    Args:
        total_bytes: Toplam dosya boyutu
        downloaded_bytes: İndirilen miktar
        speed_bps: Saniyedeki hız (bytes/second)
        
    Returns:
        Kalan süre (saniye)
    """
    if speed_bps <= 0:
        return -1
    
    remaining_bytes = total_bytes - downloaded_bytes
    return int(remaining_bytes / speed_bps)


def validate_url(url: str) -> bool:
    """
    URL formatını kontrol et
    
    Args:
        url: Kontrol edilecek URL
        
    Returns:
        True if valid, False otherwise
    """
    # Basit validasyon - trycloudflare.com veya localhost içermeli
    url_lower = url.lower()
    return (
        url_lower.startswith("http://") or url_lower.startswith("https://")
    ) and (
        "trycloudflare.com" in url_lower or "localhost" in url_lower
    )


def get_files_from_directory(directory: str) -> List[str]:
    """
    Dizindeki tüm dosyaları recursive olarak al
    
    Args:
        directory: Aranacak dizin
        
    Returns:
        Dosya path listesi
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files


def create_file_info(filepath: str, base_path: str = None) -> Dict:
    """
    Dosya bilgisi dictionary'si oluştur
    
    Args:
        filepath: Dosya yolu
        base_path: Relative path hesaplamak için base path (opsiyonel)
        
    Returns:
        {"name": "...", "size": ..., "path": "..."}
    """
    if base_path:
        # Relative path hesapla
        name = os.path.relpath(filepath, base_path)
    else:
        name = os.path.basename(filepath)
    
    return {
        "name": name,
        "size": os.path.getsize(filepath),
        "path": filepath
    }


def calculate_total_size(file_paths: List[str]) -> int:
    """
    Dosya listesinin toplam boyutunu hesapla
    
    Args:
        file_paths: Dosya path listesi
        
    Returns:
        Toplam boyut (bytes)
    """
    total = 0
    for path in file_paths:
        if os.path.isfile(path):
            total += os.path.getsize(path)
        elif os.path.isdir(path):
            for file in get_files_from_directory(path):
                total += os.path.getsize(file)
    return total

