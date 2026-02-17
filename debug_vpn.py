"""
Debug script - Captures full tailscaled output to diagnose startup failure
"""
import subprocess
import time
import os
import socket
import sys

BIN_DIR = "bin"
STATE_DIR = "ts_data"
TAILSCALED = os.path.join(BIN_DIR, "tailscaled.exe")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def check_existing_processes():
    """Check if tailscaled is already running"""
    print("--- Checking for existing tailscaled processes ---")
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq tailscaled.exe"],
        capture_output=True, text=True
    )
    print(result.stdout)
    
    print(f"Port 1055 in use: {is_port_in_use(1055)}")

def check_state_dir():
    """Check state directory contents"""
    print(f"\n--- State directory: {STATE_DIR} ---")
    if os.path.exists(STATE_DIR):
        for f in os.listdir(STATE_DIR):
            full = os.path.join(STATE_DIR, f)
            size = os.path.getsize(full) if os.path.isfile(full) else "DIR"
            print(f"  {f}: {size}")
    else:
        print("  (does not exist)")

def try_start(socket_path, label):
    """Try starting tailscaled and capture ALL output"""
    print(f"\n{'='*60}")
    print(f"Trying: {label} (socket={socket_path})")
    print(f"{'='*60}")
    
    cmd = [
        TAILSCALED,
        "--tun=userspace-networking",
        f"--socket={socket_path}",
        f"--statedir={STATE_DIR}",
        "--socks5-server=localhost:1055",
        "-verbose=2"  # Extra verbose
    ]
    print(f"Command: {' '.join(cmd)}")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait longer for output
        start = time.time()
        while time.time() - start < 8:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        
        rc = proc.poll()
        if rc is not None:
            print(f"\nProcess exited with code: {rc}")
        else:
            print(f"\nProcess is still running after 8 seconds (PID: {proc.pid})")
            print(f"Port 1055 active: {is_port_in_use(1055)}")
            proc.terminate()
            proc.wait(timeout=3)
        
        # Read all output
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
        
        if stdout:
            print(f"\n--- STDOUT ---")
            print(stdout[:3000])
        if stderr:
            print(f"\n--- STDERR ---")
            print(stderr[:3000])
        if not stdout and not stderr:
            print("\n(No output captured)")
            
        return rc
        
    except Exception as e:
        print(f"Exception: {e}")
        return -1

def try_version():
    """Check tailscaled version"""
    print("\n--- tailscaled version ---")
    try:
        result = subprocess.run([TAILSCALED, "--version"], capture_output=True, text=True, timeout=5)
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        print(f"rc: {result.returncode}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    print(f"CWD: {os.getcwd()}")
    print(f"tailscaled exists: {os.path.exists(TAILSCALED)}")
    print(f"Python: {sys.version}")
    print(f"User: {os.getenv('USERNAME')}")
    
    try_version()
    check_existing_processes()
    check_state_dir()
    
    # Kill any existing tailscaled first
    print("\n--- Killing existing tailscaled processes ---")
    subprocess.run(["taskkill", "/F", "/IM", "tailscaled.exe"], 
                   capture_output=True, text=True)
    time.sleep(1)
    
    # Attempt 1: Named pipe (the proper Windows way)
    try_start(r"\\.\pipe\quickshare-debug", "Named Pipe")
    
    time.sleep(2)
    
    # Attempt 2: Try with a fresh state dir
    fresh_state = "ts_data_fresh_debug"
    os.makedirs(fresh_state, exist_ok=True)
    print(f"\n--- Trying with fresh state dir: {fresh_state} ---")
    
    cmd = [
        TAILSCALED,
        "--tun=userspace-networking",
        f"--socket=\\\\.\\ pipe\\quickshare-debug2",
        f"--statedir={fresh_state}",
        "--socks5-server=localhost:1055",
        "-verbose=2"
    ]
    print(f"Command: {' '.join(cmd)}")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        start = time.time()
        while time.time() - start < 8:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        
        rc = proc.poll()
        if rc is not None:
            print(f"Process exited with code: {rc}")
        else:
            print(f"Process still running (PID: {proc.pid}) - SUCCESS!")
            print(f"Port 1055 active: {is_port_in_use(1055)}")
            proc.terminate()
            proc.wait(timeout=3)
        
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
        if stdout: print(f"STDOUT:\n{stdout[:3000]}")
        if stderr: print(f"STDERR:\n{stderr[:3000]}")
        
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
