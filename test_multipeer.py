import asyncio
import threading
import time
import sys
sys.path.append(r"d:\Projects\playroom\FileShareProgram\quickshare")

import os
import hashlib
from webrtc_manager import WebRTCSender, WebRTCReceiver, SignalingClient
from config import SIGNALING_SERVER_URL

def create_dummy_file(filename, size_mb):
    print(f"[{filename}] Oluşturuluyor... {size_mb} MB")
    chunk = os.urandom(1024 * 1024) # 1MB random data
    with open(filename, "wb") as f:
        for _ in range(size_mb):
            f.write(chunk)
    print(f"[{filename}] Oluşturuldu.")
    return filename

def get_hash(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def test_multipeer():
    room_id = "TESTOOM1"
    
    # 1. Server already running on Render 
    time.sleep(1)
    
    # 2. Create Dummy File
    sender_file = "test_sender_data.bin"
    create_dummy_file(sender_file, 1) # 1MB file for fast test
    original_hash = get_hash(sender_file)
    print(f"Orijinal Dosya Hash: {original_hash}")
    
    # 3. Setup WebRTC Sender
    print("--- SENDER BAŞLATILIYOR ---")
    sender = WebRTCSender()
    sender.log_callback = lambda msg: print(f"  [TX] {msg}")
    sender.start()
    sender.wait_until_ready()
    
    file_info = [{"name": "test_sender_data.bin", "path": sender_file, "size": os.path.getsize(sender_file)}]
    sender.set_files(file_info)
    
    sig_sender = SignalingClient(sender._loop, server_url=SIGNALING_SERVER_URL)
    future_tx = asyncio.run_coroutine_threadsafe(sig_sender.connect(room_id), sender._loop)
    future_tx.result(timeout=60) # Wait for network join
    sender.setup_signaling(sig_sender)
    
    time.sleep(2)
    
    # 4. Setup WebRTC Receivers (Peer 1 and Peer 2)
    def run_receiver(peer_id, output_dir):
        print(f"--- RECEIVER {peer_id} BAŞLATILIYOR ---")
        receiver = WebRTCReceiver()
        receiver.save_path = output_dir
        receiver.log_callback = lambda msg: print(f"  [RX{peer_id}] {msg}")
        receiver.start()
        receiver.wait_until_ready()
        
        sig_receiver = SignalingClient(receiver._loop, server_url=SIGNALING_SERVER_URL)
        
        async def setup_rx():
            await sig_receiver.connect(room_id)
            receiver.setup_signaling(sig_receiver)
            await receiver.connect_via_signaling()
            
        future_rx = asyncio.run_coroutine_threadsafe(setup_rx(), receiver._loop)
        future_rx.result(timeout=60) # Wait for network join
        
        # Wait for WebRTC connection
        if not receiver.wait_for_connection(20):
             print(f"[RX {peer_id}] BAĞLANTI ZAMAN AŞIMI!")
             return
        print(f"[RX {peer_id}] Bağlandı! Dosya listesi bekleniyor...")
        
        # Wait file list (sender sends it after "ready" message)
        if not receiver._file_list_event.wait(20):
             print(f"[RX {peer_id}] DOSYA LİSTESİ ALINAMADI!")
             return
             
        filenames = [f["name"] for f in receiver._file_list]
        print(f"[RX {peer_id}] Liste alındı: {filenames}")
        
        # Request all files
        receiver.request_download(filenames)
        
        # Wait transfer to complete
        if not receiver._transfer_done_event.wait(180):
             print(f"[RX {peer_id}] TRANSFER ZAMAN AŞIMI!")
             return
             
        # Verify output file
        out_path = os.path.join(output_dir, filenames[0])
        if not os.path.exists(out_path):
             print(f"[RX {peer_id}] ❌ TRANSFER BAŞARISIZ! (Dosya yok)")
             return
        
        # Verify Hash
        final_hash = get_hash(out_path)
        if final_hash == original_hash:
            print(f"[RX {peer_id}] ✅ BAŞARILI! (Hash eşleşiyor)")
        else:
            print(f"[RX {peer_id}] ❌ BAŞARISIZ! (Hash: {final_hash})")
            
    # Create per-peer output dirs
    os.makedirs("rx1_out", exist_ok=True)
    os.makedirs("rx2_out", exist_ok=True)
    
    # Start receivers in parallel threads
    t1 = threading.Thread(target=run_receiver, args=(1, "rx1_out"))
    t1.start()
    
    # Let first peer connect, wait a bit, then second peer
    time.sleep(3)
    t2 = threading.Thread(target=run_receiver, args=(2, "rx2_out"))
    t2.start()
    
    t1.join()
    t2.join()
    
    print("\n--- TEST TAMAMLANDI ---\nTemizlik yapılıyor...")
    
    sender.stop()
    asyncio.run_coroutine_threadsafe(sig_sender.close(), sender._loop)
    time.sleep(1)
    
    import shutil
    try: os.remove("test_sender_data.bin")
    except: pass
    try: shutil.rmtree("rx1_out")
    except: pass
    try: shutil.rmtree("rx2_out")
    except: pass

if __name__ == "__main__":
    test_multipeer()
