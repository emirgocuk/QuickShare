"""
QuickShare Flask Server
Dosya sunma, streaming ve WebRTC signaling
"""

from flask import Flask, send_file, jsonify, Response, request, stream_with_context
from werkzeug.utils import secure_filename
import os
import io
import time
import threading
import re
import zipfile
import base64
import json
from typing import List, Dict
from config import CHUNK_SIZE, SERVER_HOST, SERVER_PORT
from utils import create_file_info, get_files_from_directory, calculate_total_size, calculate_file_hash


app = Flask(__name__)

# WebRTC Sender instance (set by main_ctk.py)
webrtc_sender = None

# Transfer Monitoring
class TransferMonitor:
    def __init__(self):
        self.total_sent = 0
        self.total_size = 0  # Gönderilecek toplam boyut
        self.current_speed = 0.0
        self.active_transfers = 0
        self._last_check_time = time.time()
        self._last_sent_bytes = 0
        self.active_files: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def set_total_size(self, size: int):
        with self._lock:
            self.total_size = size

    def add_bytes(self, count: int):
        with self._lock:
            self.total_sent += count

    def update_file_progress(self, filename: str, sent: int, total: int):
        """Dosya bazlı ilerleme güncelle"""
        with self._lock:
            if filename not in self.active_files:
                self.active_files[filename] = {'sent': 0, 'size': total}
            
            self.active_files[filename]['sent'] = sent
            self.active_files[filename]['size'] = total 

    def finish_file(self, filename: str):
        with self._lock:
            if filename in self.active_files:
                del self.active_files[filename]

    def start_transfer(self):
        with self._lock:
            self.active_transfers += 1

    def end_transfer(self):
        with self._lock:
            self.active_transfers = max(0, self.active_transfers - 1)

    def calculate_speed_and_eta(self):
        """Hız ve ETA hesapla"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_check_time
            if elapsed >= 0.5:
                diff = self.total_sent - self._last_sent_bytes
                self.current_speed = diff / elapsed
                self._last_sent_bytes = self.total_sent
                self._last_check_time = now
        
        # ETA hesapla
        eta = 0
        if self.current_speed > 0 and self.total_size > 0:
            remaining = self.total_size - self.total_sent
            if remaining > 0:
                eta = remaining / self.current_speed
        
        return self.current_speed, eta

    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        speed, eta = self.calculate_speed_and_eta()
        with self._lock:
            files_copy = self.active_files.copy()
            
        return {
            "total_sent": self.total_sent,
            "total_size": self.total_size,
            "speed": speed,
            "eta": eta,
            "active": self.active_transfers,
            "files": files_copy
        }

# Global Monitor Instance
transfer_monitor = TransferMonitor()


@app.route('/')
def list_files():
    """
    Paylaşılan dosyaların listesini JSON olarak döndür
    
    Returns:
        JSON: {"files": [{"name": "...", "size": ..., "path": "..."}]}
    """
    files_info = []
    
    for path in shared_files:
        if os.path.isfile(path):
            # Tek dosya
            files_info.append(create_file_info(path))
        elif os.path.isdir(path):
            # Dizin - içindeki tüm dosyaları ekle
            dir_files = get_files_from_directory(path)
            for file in dir_files:
                files_info.append(create_file_info(file, base_path=path))
    
    return jsonify({"files": files_info})


@app.route('/file/<path:filename>')
def download_file(filename: str):
    """
    Tek bir dosyayı stream olarak indir (Monitörlü)
    
    Args:
        filename: İndirilecek dosya adı
        
    Returns:
        Response: Streaming file response
    """
    # Dosyayı shared_files içinde ara
    target_file = None
    
    for path in shared_files:
        if os.path.isfile(path):
            if os.path.basename(path) == filename:
                target_file = path
                break
        elif os.path.isdir(path):
            # Dizin içinde ara
            for file in get_files_from_directory(path):
                # Relative path ile karşılaştır
                rel_path = os.path.relpath(file, path)
                if rel_path.replace('\\', '/') == filename.replace('\\', '/'):
                    target_file = file
                    break
            if target_file:
                break
    
    if not target_file or not os.path.exists(target_file):
        return jsonify({"error": "File not found"}), 404
    
    # Range Header Handling
    range_header = request.headers.get('Range', None)
    file_size = os.path.getsize(target_file)
    
    start_byte = 0
    end_byte = file_size - 1
    length = file_size
    status_code = 200
    
    if range_header:
        try:
            # Parse Range header (format: bytes=start-end)
            range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start_byte = int(range_match.group(1))
                if range_match.group(2):
                    end_byte = int(range_match.group(2))
                
                # Validate range
                if start_byte >= file_size:
                    return Response(
                        "Requested Range Not Satisfiable",
                        status=416,
                        headers={'Content-Range': f'bytes */{file_size}'}
                    )
                
                length = end_byte - start_byte + 1
                status_code = 206
        except ValueError:
            pass  # Invalid range, ignore and send full file

    # Custom generator for monitoring
    def generate_file_stream():
        transfer_monitor.start_transfer()
        try:
            with open(target_file, 'rb') as f:
                if start_byte > 0:
                    f.seek(start_byte)
                
                remaining = length
                while remaining > 0:
                    read_size = min(CHUNK_SIZE, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    transfer_monitor.add_bytes(len(chunk))
                    # Update file progress
                    current_sent = length - remaining
                    transfer_monitor.update_file_progress(os.path.basename(target_file), current_sent, length)
                    yield chunk
        finally:
            transfer_monitor.end_transfer()
            transfer_monitor.finish_file(os.path.basename(target_file))

    # Streaming Response
    headers = {
        'Content-Disposition': 'attachment; filename="file.bin"',
        'Content-Length': str(length),
        'Accept-Ranges': 'bytes'
    }
    
    if status_code == 206:
        headers['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'

    return Response(
        stream_with_context(generate_file_stream()),
        status=status_code,
        mimetype='application/octet-stream',
        headers=headers
    )


@app.route('/file_b64/<path:encoded_filename>')
def download_file_b64(encoded_filename: str):
    """
    Base64 encoded dosya adı ile indirme (Karakter sorunlarına kesin çözüm)
    """
    try:
        # Decode base64 filename
        filename = base64.urlsafe_b64decode(encoded_filename).decode('utf-8')
    except Exception as e:
        return jsonify({"error": f"Invalid filename encoding: {str(e)}"}), 400
        
    # Mevcut download_file mantığını çağır (kod tekrarını önlemek için)
    # Ancak burada doğrudan logic'i tekrar edelim çünkü context generate_file_stream içinde
    
    # Dosyayı shared_files içinde ara
    target_file = None
    
    for path in shared_files:
        if os.path.isfile(path):
            if os.path.basename(path) == filename:
                target_file = path
                break
        elif os.path.isdir(path):
            # Dizin içinde ara
            for file in get_files_from_directory(path):
                # Relative path ile karşılaştır
                rel_path = os.path.relpath(file, path)
                if rel_path.replace('\\', '/') == filename.replace('\\', '/'):
                    target_file = file
                    break
            if target_file:
                break
    
    if not target_file or not os.path.exists(target_file):
        return jsonify({"error": "File not found"}), 404
    
    # Range Header Handling
    range_header = request.headers.get('Range', None)
    file_size = os.path.getsize(target_file)
    
    start_byte = 0
    end_byte = file_size - 1
    length = file_size
    status_code = 200
    
    if range_header:
        try:
            # Parse Range header (format: bytes=start-end)
            range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start_byte = int(range_match.group(1))
                if range_match.group(2):
                    end_byte = int(range_match.group(2))
                
                # Validate range
                if start_byte >= file_size:
                    return Response(
                        "Requested Range Not Satisfiable",
                        status=416,
                        headers={'Content-Range': f'bytes */{file_size}'}
                    )
                
                length = end_byte - start_byte + 1
                status_code = 206
        except ValueError:
            pass  # Invalid range, ignore and send full file

    # Custom generator for monitoring
    def generate_file_stream():
        transfer_monitor.start_transfer()
        try:
            with open(target_file, 'rb') as f:
                if start_byte > 0:
                    f.seek(start_byte)
                
                remaining = length
                while remaining > 0:
                    read_size = min(CHUNK_SIZE, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    transfer_monitor.add_bytes(len(chunk))
                    # Update file progress
                    current_sent = length - remaining
                    transfer_monitor.update_file_progress(os.path.basename(target_file), current_sent, length)
                    yield chunk
        finally:
            transfer_monitor.end_transfer()
            transfer_monitor.finish_file(os.path.basename(target_file))

    # Streaming Response
    headers = {
        'Content-Disposition': 'attachment; filename="file.bin"',
        'Content-Length': str(length),
        'Accept-Ranges': 'bytes'
    }
    
    if status_code == 206:
        headers['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'

    return Response(
        stream_with_context(generate_file_stream()),
        status=status_code,
        mimetype='application/octet-stream',
        headers=headers
    )


@app.route('/download')
def download_all():
    """
    Tüm dosyaları ZIP olarak stream et (Monitörlü)
    
    Returns:
        Response: Streaming ZIP response
    """
    def generate_zip():
        """ZIP'i on-the-fly oluştur ve stream et"""
        transfer_monitor.start_transfer()
        try:
            # In-memory buffer
            buffer = io.BytesIO()
            
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Dosyaları ekle
                for file_path in shared_files:
                    if os.path.isfile(file_path):
                        arcname = os.path.basename(file_path)
                        zf.write(file_path, arcname)
                    elif os.path.isdir(file_path):
                        for root, _, files in os.walk(file_path):
                            for file in files:
                                full_path = os.path.join(root, file)
                                rel_path = os.path.relpath(full_path, os.path.dirname(file_path))
                                zf.write(full_path, rel_path)
            
            # Buffer'ı başa al
            buffer.seek(0)
            
            # Chunk by chunk oku
            while True:
                chunk = buffer.read(CHUNK_SIZE)
                if not chunk:
                    break
                transfer_monitor.add_bytes(len(chunk))
                transfer_monitor.update_file_progress("ALL_FILES.zip", transfer_monitor.total_sent, transfer_monitor.total_size)
                yield chunk
        finally:
            transfer_monitor.end_transfer()
            transfer_monitor.finish_file("ALL_FILES.zip")
    
    return Response(
        stream_with_context(generate_zip()),
        mimetype='application/zip',
        headers={
            'Content-Disposition': 'attachment; filename=download.zip'
        }
    )


@app.route('/hash/<path:filename>')
def get_file_hash(filename: str):
    """
    Dosyanın SHA256 hash'ini hesapla ve döndür
    
    Args:
        filename: Dosya adı (veya relative path)
        
    Returns:
        JSON: {"hash": "..."}
    """
    # Dosyayı shared_files içinde ara
    target_file = None
    
    for path in shared_files:
        if os.path.isfile(path):
            if os.path.basename(path) == filename:
                target_file = path
                break
        elif os.path.isdir(path):
            for file in get_files_from_directory(path):
                rel_path = os.path.relpath(file, path)
                if rel_path.replace('\\', '/') == filename.replace('\\', '/'):
                    target_file = file
                    break
            if target_file:
                break
    
    if not target_file or not os.path.exists(target_file):
        return jsonify({"error": "File not found"}), 404
        
    # Hash hesapla (bu işlem büyük dosyalarda zaman alabilir)
    # TODO: Cache mekanizması eklenebilir
    try:
        file_hash = calculate_file_hash(target_file)
        return jsonify({"hash": file_hash})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def set_shared_files(files: List[str]):
    """
    Paylaşılacak dosyaları set et
    
    Args:
        files: Dosya path listesi
    """
    global shared_files
    shared_files = files
    
    # Toplam boyutu hesapla ve monitöre bildir (ETA için)
    total_size = calculate_total_size(files)
    transfer_monitor.set_total_size(total_size)


def run_server(port: int = SERVER_PORT, debug: bool = False):
    """
    Flask server'ı başlat
    
    Args:
        port: Port numarası
        debug: Debug mode
    """
    app.run(host=SERVER_HOST, port=port, debug=debug, threaded=True)


# ===== WebRTC Signaling Endpoints =====

@app.route('/rtc/offer', methods=['POST'])
def rtc_handle_offer():
    """
    Alıcıdan gelen SDP offer'ı al, answer oluştur ve döndür.
    Bu endpoint sadece bağlantı kurulumu için — dosya verisi P2P geçer.
    """
    global webrtc_sender
    
    if not webrtc_sender:
        return jsonify({"error": "WebRTC sender not initialized", "p2p": False}), 503
    
    try:
        data = request.get_json()
        if not data or 'sdp' not in data:
            return jsonify({"error": "Missing SDP offer"}), 400
        
        offer_sdp = data['sdp']
        
        # Generate answer
        answer = webrtc_sender.handle_offer_sync(offer_sdp)
        
        # Start sending files after connection is established
        def _wait_and_send():
            if webrtc_sender.wait_for_connection(timeout=30):
                if webrtc_sender.status == "connected":
                    time.sleep(0.5)
                    webrtc_sender.send_files()
        
        threading.Thread(target=_wait_and_send, daemon=True).start()
        
        return jsonify(answer)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/rtc/status')
def rtc_status():
    """WebRTC P2P bağlantı durumunu döndür"""
    global webrtc_sender
    
    if not webrtc_sender:
        return jsonify({"p2p": False, "status": "not_initialized"})
    
    return jsonify({
        "p2p": True,
        "status": webrtc_sender.status
    })


# Test kodu
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Test dosyası belirtilmişse
        test_path = sys.argv[1]
        if os.path.exists(test_path):
            set_shared_files([test_path])
            print(f"Sharing: {test_path}")
            print(f"Server starting on http://{SERVER_HOST}:{SERVER_PORT}")
            print(f"\nTest URLs:")
            print(f"  - List files: http://{SERVER_HOST}:{SERVER_PORT}/")
            print(f"  - Download: http://{SERVER_HOST}:{SERVER_PORT}/download")
            print(f"  - Ping: http://{SERVER_HOST}:{SERVER_PORT}/ping")
            run_server(debug=True)
        else:
            print(f"Path not found: {test_path}")
    else:
        print("Usage: python server.py <file_or_directory_to_share>")
        print("Example: python server.py test.txt")
        print("Example: python server.py C:\\Users\\Documents")
