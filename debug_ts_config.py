import subprocess
import os
import time

def log(msg):
    with open("results.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_config(name, args):
    log(f"\n--- Testing Config: {name} ---")
    log(f"Args: {args}")
    
    cmd = ["bin\\tailscaled.exe"] + args
    
    try:
        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment
        time.sleep(3)
        
        if proc.poll() is None:
            log("STATUS: RUNNING")
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=2)
                log(f"Output (First 500 chars): {err[:500] if err else 'None'}")
            except:
                proc.kill()
        else:
            log(f"STATUS: FAILED (Code {proc.returncode})")
            err = proc.stderr.read()
            log(f"Error Output: {err}")
            
    except Exception as e:
        log(f"EXCEPTION: {e}")

# Clear stats
if os.path.exists("results.txt"): os.remove("results.txt")
os.makedirs("ts_debug_data", exist_ok=True)

# 1. Named Pipe (Simple)
test_config("Named Pipe Simple", [
    "--tun=userspace-networking",
    "--socket=\\\\.\\pipe\\quickshare-ts",
    "--statedir=ts_debug_data",
    "--socks5-server=localhost:1056"
])

# 2. Named Pipe (Local)
test_config("Named Pipe Local", [
    "--tun=userspace-networking",
    "--socket=\\\\.\\pipe\\ProtectedPrefix\\LocalSystem\\tailscaled", 
    "--statedir=ts_debug_data",
    "--socks5-server=localhost:1056"
])

# 3. TCP Socket? (Guessing flag support)
test_config("TCP Socket", [
    "--tun=userspace-networking",
    "--socket=tcp://127.0.0.1:41345",
    "--statedir=ts_debug_data",
    "--socks5-server=localhost:1056"
])
