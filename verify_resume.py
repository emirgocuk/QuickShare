import os
import time
import threading
import requests
import shutil
import sys

# Add directory to sys.path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from server import run_server, set_shared_files
from downloader import Downloader
from config import SERVER_PORT, SERVER_HOST

TEST_DIR = "test_data"
DOWNLOAD_DIR = "test_downloads"
TEST_FILE = "large_test_file.bin"
FILE_SIZE = 10 * 1024 * 1024  # 10 MB

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

def create_partial_file():
    # Simulate a partial download (first 1 MB)
    src = os.path.join(TEST_DIR, TEST_FILE)
    dst = os.path.join(DOWNLOAD_DIR, TEST_FILE)
    
    with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
        f_dst.write(f_src.read(1 * 1024 * 1024))
    
    print(f"Created partial file: 1MB")

def test_resume():
    setup_test_env()
    
    # Share the file
    set_shared_files([os.path.join(TEST_DIR, TEST_FILE)])
    
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
    time.sleep(1) # Wait for server
    
    # Create partial file
    create_partial_file()
    
    # Start download
    downloader = Downloader()
    url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    print("Starting download (should resume)...")
    
    def progress(downloaded, total, speed):
        # percent = (downloaded / total * 100) if total > 0 else 0
        # print(f"\r{percent:.1f}% - {downloaded}/{total}", end="")
        pass
        
    try:
        downloader.download_file(url, TEST_FILE, DOWNLOAD_DIR, progress)
        print("\nDownload complete.")
        
        # Verify size
        final_size = os.path.getsize(os.path.join(DOWNLOAD_DIR, TEST_FILE))
        print(f"Final size: {final_size}")
        
        if final_size == FILE_SIZE:
            print("✅ SUCCESS: File size matches!")
        else:
            print(f"❌ FAILURE: Expected {FILE_SIZE}, got {final_size}")
        
        sys.stdout.flush()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.stdout.flush()

if __name__ == "__main__":
    test_resume()
