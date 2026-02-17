import subprocess
import os
import time

def log(msg):
    with open("results_final.txt", "a", encoding="utf-8") as f:
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
                log(f"Output: {err}")
            except:
                proc.kill()
        else:
            log(f"STATUS: FAILED (Code {proc.returncode})")
            err = proc.stderr.read()
            log(f"Error Output: {err}")
            
    except Exception as e:
        log(f"EXCEPTION: {e}")

# Clear stats
if os.path.exists("results_final.txt"): os.remove("results_final.txt")
os.makedirs("ts_debug_final", exist_ok=True)

# 1. TCP with slashes
test_config("TCP Slashes", [
    "--tun=userspace-networking",
    "--socket=tcp://127.0.0.1:0",
    "--statedir=ts_debug_final",
    "--socks5-server=localhost:1056"
])

# 2. TCP w/o slashes
test_config("TCP No Slashes", [
    "--tun=userspace-networking",
    "--socket=tcp:127.0.0.1:0",
    "--statedir=ts_debug_final",
    "--socks5-server=localhost:1056"
])

# 3. Just Name "qs-pipe"
test_config("Pipe Simple Name", [
    "--tun=userspace-networking",
    "--socket=qs-pipe",
    "--statedir=ts_debug_final",
    "--socks5-server=localhost:1056"
])
