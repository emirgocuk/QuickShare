import subprocess
import os
import time

def log(msg):
    with open("results_pipe.txt", "a", encoding="utf-8") as f:
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
if os.path.exists("results_pipe.txt"): os.remove("results_pipe.txt")
os.makedirs("ts_debug_pipe", exist_ok=True)

# 1. Just Name
test_config("Just Name", [
    "--tun=userspace-networking",
    "--socket=quickshare-ts",
    "--statedir=ts_debug_pipe",
    "--socks5-server=localhost:1056"
])

# 2. Standard Name
test_config("Standard Name", [
    "--tun=userspace-networking",
    "--socket=tailscaled", 
    "--statedir=ts_debug_pipe",
    "--socks5-server=localhost:1056"
])

# 3. Default (No Socket) - Just to see error clearly
test_config("Default", [
    "--tun=userspace-networking",
    "--statedir=ts_debug_pipe",
    "--socks5-server=localhost:1056"
])
