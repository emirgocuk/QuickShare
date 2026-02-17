from tailscale_manager import TailscaleManager
import os
import shutil
import time

# Clean slate
if os.path.exists("ts_data_clean"): shutil.rmtree("ts_data_clean")

print("--- Testing Tailscale Manager with Pipe ---")
ts = TailscaleManager(state_dir="ts_data_clean")

def log(msg):
    print(f"[TS] {msg}")

# Override socket path for test
ts.socket_path = r"\\.\pipe\quickshare-ts" 

# Patch start_daemon temporarily to use this socket
# Actually, I should just modify tailscale_manager.py if this works?
# But let's run tailscaled manually in this script to be sure

import subprocess
cmd = [
    ts.tailscaled_path,
    "--tun=userspace-networking",
    f"--socket={ts.socket_path}",
    f"--statedir={ts.state_dir}",
    "--socks5-server=localhost:1056"
]

print(f"Running: {cmd}")
try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(5)
    if proc.poll() is None:
        print("SUCCESS: Running!")
        proc.terminate()
    else:
        print(f"FAILED: Code {proc.returncode}")
        print(f"Error: {proc.stderr.read()}")

except Exception as e:
    print(f"EXCEPTION: {e}")
