import threading
import time
import os
import sys

# Ensure we can import from local dir
sys.path.append(os.getcwd())

from tailscale_manager import TailscaleManager

def start_ts(id):
    print(f"[{id}] Starting...")
    ts = TailscaleManager()
    
    def log(msg):
        print(f"[{id}] {msg}")
        
    try:
        ts.start_daemon(log_callback=log)
        print(f"[{id}] FINAL STATUS: {ts.status}")
    except Exception as e:
        print(f"[{id}] CRASHED: {e}")
        
    # Simulate app running
    time.sleep(20)
    
    # Cleanup
    try:
        ts.stop()
        print(f"[{id}] Stopped.")
    except:
        pass

print("--- Starting Race Condition Test ---")

# Start first instance
t1 = threading.Thread(target=start_ts, args=(1,))
t1.start()

# Wait briefly
time.sleep(5)

# Start second instance (should detect active port or lock)
t2 = threading.Thread(target=start_ts, args=(2,))
t2.start()

t1.join()
t2.join()

print("--- Test Finished ---")
