import os
import time
import threading
import requests
import shutil
import sys
import hashlib

# Add directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from server import run_server, set_shared_files
from downloader import Downloader
from config import SERVER_PORT, SERVER_HOST
from utils import calculate_file_hash

TEST_DIR = "test_hash_data"
DOWNLOAD_DIR = "test_hash_downloads"
TEST_FILE = "hash_test_file.bin"
FILE_SIZE = 1024 * 1024  # 1 MB

def setup_test_env():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    
    os.makedirs(TEST_DIR)
    os.makedirs(DOWNLOAD_DIR)
    
    # Create a random file
    with open(os.path.join(TEST_DIR, TEST_FILE), 'wb') as f:
        f.write(os.urandom(FILE_SIZE))

def test_hash_verification():
    setup_test_env()
    
    file_path = os.path.join(TEST_DIR, TEST_FILE)
    expected_hash = calculate_file_hash(file_path)
    print(f"Original File Hash: {expected_hash}")
    
    # Share the file
    set_shared_files([file_path])
    
    # Suppress logs
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Start server in thread
    server_thread = threading.Thread(
        target=run_server,
        kwargs={'port': SERVER_PORT, 'debug': False},
        daemon=True
    )
    server_thread.start()
    time.sleep(1)
    
    # Start download
    downloader = Downloader()
    url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    print("Starting download and verification...")
    
    def progress(downloaded, total, speed):
        pass
        
    try:
        downloader.download_file(url, TEST_FILE, DOWNLOAD_DIR, progress)
        print("\nDownload process finished.")
        
        # Manually check if verification message appeared in stdout (visual check for user)
        # But we also verify programmatically here
        downloaded_path = os.path.join(DOWNLOAD_DIR, TEST_FILE)
        if os.path.exists(downloaded_path):
            downloaded_hash = calculate_file_hash(downloaded_path)
            if downloaded_hash == expected_hash:
                print("✅ TEST SUCCESS: Hashes match programmatically.")
            else:
                print("❌ TEST FAILURE: Hashes do not match!")
        else:
            print("❌ TEST FAILURE: File not downloaded.")
            
        sys.stdout.flush()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.stdout.flush()

if __name__ == "__main__":
    test_hash_verification()
