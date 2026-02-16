import subprocess
import threading
import time
import os
import re
import requests
from typing import Optional, Callable

class TailscaleManager:
    def __init__(self, bin_dir="bin", state_dir="ts_data"):
        self.bin_dir = bin_dir
        self.state_dir = state_dir
        self.daemon_process: Optional[subprocess.Popen] = None
        self.auth_url: Optional[str] = None
        self.tailnet_url: Optional[str] = None
        self.status = "Offline"
        
        # Binary paths
        self.tailscaled_path = os.path.join(bin_dir, "tailscaled.exe")
        self.tailscale_path = os.path.join(bin_dir, "tailscale.exe")
        
        # Ensure directories exist
        os.makedirs(bin_dir, exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

    def check_binaries(self) -> bool:
        """Check if tailscale binaries exist"""
        return os.path.exists(self.tailscaled_path) and os.path.exists(self.tailscale_path)

    def is_port_in_use(self, port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def start_daemon(self, log_callback: Optional[Callable[[str], None]] = None):
        """Start tailscaled in userspace networking mode"""
        if self.daemon_process:
            return

        # Check if already running on port 1055
        if self.is_port_in_use(1055):
            if log_callback: log_callback("Tailscale daemon already running (Port 1055). Using existing instance.")
            self.status = "Daemon Running (Shared)"
            return

        cmd = [
            self.tailscaled_path,
            "--tun=userspace-networking",
            "--socket=ts.sock",
            f"--statedir={self.state_dir}",
            "--socks5-server=localhost:1055"
        ]
        
        if log_callback: log_callback("Starting Tailscale daemon...")
        
        try:
            # Start daemon
            self.daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Start output reader thread
            threading.Thread(target=self._monitor_output, args=(log_callback,), daemon=True).start()
            
            self.status = "Daemon Running"
            if log_callback: log_callback("Tailscale daemon started.")
            
        except Exception as e:
            if log_callback: log_callback(f"Failed to start tailscaled: {e}")
            self.status = "Error"

    def cleanup(self):
        """Kill daemon on exit"""
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=2)
            except:
                self.daemon_process.kill()

    def _monitor_output(self, log_callback):
        """Monitor daemon output for Auth URL"""
        while self.daemon_process and self.daemon_process.poll() is None:
            line = self.daemon_process.stderr.readline()
            if not line: continue
            
            # Check for Auth URL
            # Log: "To authenticate, visit: https://login.tailscale.com/..."
            if "https://login.tailscale.com/" in line:
                match = re.search(r'(https://login\.tailscale\.com/\S+)', line)
                if match:
                    self.auth_url = match.group(1)
                    if log_callback: log_callback(f"AUTH REQUIRED: {self.auth_url}")
            
            # Debug log (optional)
            # if log_callback: log_callback(f"[TS] {line.strip()}")

    def up(self):
        """Run 'tailscale up' to trigger login/connect"""
        cmd = [
            self.tailscale_path,
            "--socket=ts.sock",
            "up",
            "--hostname=quickshare-app",
            "--accept-routes"
        ]
        subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def serve(self, port=5000) -> str:
        """Expose local port using 'tailscale serve'"""
        # 1. Check status
        status_cmd = [self.tailscale_path, "--socket=ts.sock", "status", "--json"]
        try:
            res = subprocess.run(status_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if "BackendState" in res.stdout and "Running" in res.stdout:
                pass # OK
            else:
                return "Not Connected"
        except:
            return "Error Checking Status"

        # 2. Run serve
        # tailscale serve https / http://localhost:5000
        serve_cmd = [
            self.tailscale_path,
            "--socket=ts.sock",
            "serve",
            f"http://localhost:{port}"
        ]
        subprocess.run(serve_cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        # 3. Get URL via 'tailscale serve status' or just 'tailscale status'
        # For simple cases, it's machine-name.tailnet-name.ts.net
        return self.get_domain()

    def get_domain(self):
        cmd = [self.tailscale_path, "--socket=ts.sock", "status", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        # Parse JSON to find Self.DNSName
        import json
        try:
            data = json.loads(res.stdout)
            return "https://" + data["Self"]["DNSName"].rstrip(".")
        except:
            return None

    def stop(self):
        if self.daemon_process:
            self.daemon_process.terminate()
