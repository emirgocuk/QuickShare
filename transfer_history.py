"""
QuickShare Transfer History
JSON tabanlı transfer kayıt sistemi
"""

import json
import os
import uuid
import time
from datetime import datetime
from typing import List, Dict, Optional


# Default history path
DEFAULT_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_HISTORY_FILE = os.path.join(DEFAULT_HISTORY_DIR, "history.json")
MAX_RECORDS = 200


class TransferHistory:
    """Transfer geçmişi yöneticisi — JSON tabanlı"""
    
    def __init__(self, filepath: str = DEFAULT_HISTORY_FILE):
        self.filepath = filepath
        self._ensure_dir()
        self._data = self._load()
    
    def _ensure_dir(self):
        """History dosyasının bulunduğu dizini oluştur"""
        dirpath = os.path.dirname(self.filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
    
    def _load(self) -> dict:
        """JSON dosyasını oku"""
        if not os.path.exists(self.filepath):
            return {"transfers": []}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "transfers" not in data:
                    data["transfers"] = []
                return data
        except (json.JSONDecodeError, IOError):
            return {"transfers": []}
    
    def _save(self):
        """JSON dosyasına yaz"""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[History] Kayıt hatası: {e}")
    
    def _trim(self):
        """MAX_RECORDS'u aşan eski kayıtları sil (FIFO)"""
        if len(self._data["transfers"]) > MAX_RECORDS:
            self._data["transfers"] = self._data["transfers"][-MAX_RECORDS:]
    
    def log_transfer(
        self,
        filename: str,
        size: int,
        direction: str,  # "send" | "receive"
        status: str = "success",  # "success" | "failed" | "cancelled"
        hash_value: str = "",
        duration_sec: float = 0,
        avg_speed: float = 0,
        method: str = "http",  # "http" | "p2p"
    ) -> str:
        """
        Yeni transfer kaydı ekle
        
        Returns:
            Transfer ID (uuid)
        """
        transfer_id = str(uuid.uuid4())[:8]
        
        record = {
            "id": transfer_id,
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "size": size,
            "direction": direction,
            "status": status,
            "hash": hash_value,
            "duration_sec": round(duration_sec, 1),
            "avg_speed": round(avg_speed),
            "method": method,
        }
        
        self._data["transfers"].append(record)
        self._trim()
        self._save()
        
        return transfer_id
    
    def get_recent(self, count: int = 50, direction: Optional[str] = None) -> List[Dict]:
        """
        Son N kaydı döndür (en yeniden en eskiye)
        
        Args:
            count: Döndürülecek kayıt sayısı
            direction: Opsiyonel filtre — "send" veya "receive"
        
        Returns:
            Transfer kayıtları listesi
        """
        records = self._data["transfers"]
        
        if direction:
            records = [r for r in records if r.get("direction") == direction]
        
        # En yeniden en eskiye
        return list(reversed(records[-count:]))
    
    def get_stats(self) -> Dict:
        """
        Genel istatistikleri döndür
        
        Returns:
            {
                "total_transfers": int,
                "total_sent": int (bytes),
                "total_received": int (bytes),
                "success_count": int,
                "failed_count": int,
            }
        """
        records = self._data["transfers"]
        
        total_sent = sum(r["size"] for r in records if r.get("direction") == "send" and r.get("status") == "success")
        total_received = sum(r["size"] for r in records if r.get("direction") == "receive" and r.get("status") == "success")
        success_count = sum(1 for r in records if r.get("status") == "success")
        failed_count = sum(1 for r in records if r.get("status") == "failed")
        
        return {
            "total_transfers": len(records),
            "total_sent": total_sent,
            "total_received": total_received,
            "success_count": success_count,
            "failed_count": failed_count,
        }
    
    def clear(self):
        """Tüm geçmişi sil"""
        self._data["transfers"] = []
        self._save()
    
    def get_last_transfer(self) -> Optional[Dict]:
        """Son transfer kaydını döndür"""
        if self._data["transfers"]:
            return self._data["transfers"][-1]
        return None


# Global instance
history = TransferHistory()
