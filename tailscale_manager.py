import subprocess
import threading
import time
import os
import re
import tempfile
import ctypes
import requests
from typing import Optional, Callable

class TailscaleManager:
    SOCKS_PORT = 1055

    def __init__(self, bin_dir="bin", state_dir="ts_data"):
        self.bin_dir = os.path.abspath(bin_dir)
        self.state_dir = os.path.abspath(state_dir)
        self.daemon_process: Optional[subprocess.Popen] = None
        self._elevated_pid: Optional[int] = None  # PID when launched elevated
        self.auth_url: Optional[str] = None
        self.tailnet_url: Optional[str] = None
        self.status = "Offline"
        self.socket_path = r"\\.\pipe\quickshare-ts"  # Windows named pipe
        self._log_file: Optional[str] = None  # Log file for elevated process
        
        # Binary paths (absolute)
        self.tailscaled_path = os.path.abspath(os.path.join(bin_dir, "tailscaled.exe"))
        self.tailscale_path = os.path.abspath(os.path.join(bin_dir, "tailscale.exe"))
        
        # Ensure directories exist
        os.makedirs(bin_dir, exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

    def check_binaries(self) -> bool:
        """Check if tailscale binaries exist"""
        return os.path.exists(self.tailscaled_path) and os.path.exists(self.tailscale_path)

    @staticmethod
    def _is_admin() -> bool:
        """Check if current process has admin privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def is_port_in_use(self, port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def _is_tailscaled_running(self) -> bool:
        """Check if tailscaled.exe is already running as a process"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq tailscaled.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return "tailscaled.exe" in result.stdout
        except:
            return False

    def start_daemon(self, log_callback: Optional[Callable[[str], None]] = None):
        """Start tailscaled in userspace networking mode with admin privileges"""
        # Check if already running on our SOCKS port
        if self.is_port_in_use(self.SOCKS_PORT):
            if log_callback: log_callback(f"SOCKS5 port {self.SOCKS_PORT} already active. Using existing instance.")
            self.status = "Daemon Running (Shared)"
            return

        # Kill any stale tailscaled processes from previous runs
        self._kill_existing(log_callback)

        if not self._try_start_elevated(log_callback):
            raise RuntimeError("Tailscaled başlatılamadı. Yönetici izni reddedilmiş olabilir.")

    def _kill_existing(self, log_callback):
        """Kill any existing tailscaled processes to avoid conflicts"""
        if self._is_tailscaled_running():
            if log_callback: log_callback("Killing existing tailscaled processes...")
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "tailscaled.exe"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(1)
            except:
                pass

    def _try_start_elevated(self, log_callback) -> bool:
        """Start tailscaled with admin elevation via a batch script"""
        import uuid
        
        # Unique named pipe for this session
        pipe_id = uuid.uuid4().hex[:8]
        self.socket_path = rf"\\.\pipe\quickshare-{pipe_id}"
        
        # Create a log file to capture elevated process output
        log_dir = os.path.join(self.state_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self._log_file = os.path.join(log_dir, f"tailscaled_{pipe_id}.log")
        
        if log_callback: log_callback(f"Starting tailscaled (pipe: quickshare-{pipe_id})...")
        
        # Build the tailscaled command
        args = " ".join([
            f'"{self.tailscaled_path}"',
            "--tun=userspace-networking",
            f'--socket={self.socket_path}',
            f'--statedir="{self.state_dir}"',
            f"--socks5-server=localhost:{self.SOCKS_PORT}",
        ])
        
        # Create a batch script that runs tailscaled and redirects output
        bat_path = os.path.join(self.state_dir, f"start_ts_{pipe_id}.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\n')
            f.write(f'{args} > "{self._log_file}" 2>&1\n')
        
        try:
            if self._is_admin():
                # Already admin - start directly
                if log_callback: log_callback("Running with existing admin privileges...")
                proc = subprocess.Popen(
                    [
                        self.tailscaled_path,
                        "--tun=userspace-networking",
                        f"--socket={self.socket_path}",
                        f"--statedir={self.state_dir}",
                        f"--socks5-server=localhost:{self.SOCKS_PORT}",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.daemon_process = proc
                # Start monitor thread
                threading.Thread(target=self._monitor_output, args=(log_callback,), daemon=True).start()
            else:
                # Need elevation - use ShellExecuteW with runas
                if log_callback: log_callback("Yönetici izni isteniyor (UAC)...")
                
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", bat_path, None, self.state_dir, 0  # 0 = SW_HIDE
                )
                
                if ret <= 32:
                    if log_callback: log_callback(f"Yönetici izni reddedildi veya hata oluştu (kod: {ret})")
                    return False
                
                # Start log file monitor thread
                threading.Thread(
                    target=self._monitor_log_file, args=(log_callback,), daemon=True
                ).start()
            
            # Wait for SOCKS5 port to become ready
            if log_callback: log_callback(f"SOCKS5 proxy bekleniyor (port {self.SOCKS_PORT})...")
            
            start_time = time.time()
            while time.time() - start_time < 20:  # 20 seconds timeout
                if self.is_port_in_use(self.SOCKS_PORT):
                    self.status = "Daemon Running"
                    if log_callback: log_callback("✅ Tailscale daemon başlatıldı - SOCKS5 proxy hazır!")
                    return True
                
                # If we have a direct process handle, check if it died
                if self.daemon_process and self.daemon_process.poll() is not None:
                    err = ""
                    if self.daemon_process.stderr:
                        err = self.daemon_process.stderr.read()
                    if log_callback: log_callback(f"Tailscaled kapandı (kod: {self.daemon_process.returncode}): {err}")
                    self.daemon_process = None
                    return False
                
                # For elevated process, check via log file for errors
                if not self.daemon_process and self._log_file and os.path.exists(self._log_file):
                    try:
                        with open(self._log_file, "r", errors="replace") as lf:
                            content = lf.read()
                        if "safesocket.Listen" in content and "error" in content.lower():
                            if log_callback: log_callback(f"Tailscaled hatası: {content[-300:]}")
                            return False
                    except:
                        pass
                
                # For elevated process, check if tailscaled is running
                if not self.daemon_process and time.time() - start_time > 5:
                    if not self._is_tailscaled_running():
                        if log_callback: log_callback("Tailscaled process bulunamıyor - muhtemelen başlatılamadı.")
                        # Try to read log for details
                        if self._log_file and os.path.exists(self._log_file):
                            try:
                                with open(self._log_file, "r", errors="replace") as lf:
                                    if log_callback: log_callback(f"Log: {lf.read()[-500:]}")
                            except:
                                pass
                        return False
                
                time.sleep(0.5)
            
            # Timeout
            if log_callback: log_callback("Zaman aşımı: SOCKS5 portu aktif olmadı.")
            self.cleanup()
            return False
            
        except Exception as e:
            if log_callback: log_callback(f"Tailscaled başlatma hatası: {e}")
            self.cleanup()
            return False
        finally:
            # Clean up batch file
            try:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
            except:
                pass

    def cleanup(self):
        """Kill daemon on exit"""
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=2)
            except:
                try:
                   self.daemon_process.kill()
                except: pass
            self.daemon_process = None
        
        # For elevated processes, kill by name
        if self._elevated_pid or (self.status != "Offline" and self._is_tailscaled_running()):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "tailscaled.exe"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except:
                pass
            self._elevated_pid = None
        
        self.status = "Offline"

    def _monitor_output(self, log_callback):
        """Monitor daemon stderr for Auth URL (direct process)"""
        try:
            while self.daemon_process and self.daemon_process.poll() is None:
                line = self.daemon_process.stderr.readline()
                if not line: continue
                self._check_line_for_auth(line.strip(), log_callback)
        except:
            pass

    def _monitor_log_file(self, log_callback):
        """Monitor log file for Auth URL (elevated process)"""
        if not self._log_file:
            return
        
        last_pos = 0
        for _ in range(120):  # Monitor for up to 60 seconds
            try:
                if os.path.exists(self._log_file):
                    with open(self._log_file, "r", errors="replace") as f:
                        f.seek(last_pos)
                        new_content = f.read()
                        last_pos = f.tell()
                    
                    if new_content:
                        for line in new_content.strip().split("\n"):
                            self._check_line_for_auth(line.strip(), log_callback)
            except:
                pass
            time.sleep(0.5)

    def _check_line_for_auth(self, line: str, log_callback):
        """Check a line of output for auth URL"""
        if "https://login.tailscale.com/" in line:
            match = re.search(r'(https://login\.tailscale\.com/\S+)', line)
            if match:
                self.auth_url = match.group(1)
                if log_callback: log_callback(f"AUTH REQUIRED: {self.auth_url}")

    def _run_tailscale_cmd(self, args: list, **kwargs):
        """Run a tailscale CLI command, elevating if needed"""
        cmd = [self.tailscale_path, f"--socket={self.socket_path}"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            **kwargs
        )

    def up(self):
        """Run 'tailscale up' to trigger login/connect"""
        self._run_tailscale_cmd(["up", "--hostname=quickshare-app", "--accept-routes"])

    def serve(self, port=5000) -> str:
        """Expose local port using 'tailscale serve'"""
        # 1. Check status
        try:
            res = self._run_tailscale_cmd(["status", "--json"])
            if "BackendState" in res.stdout and "Running" in res.stdout:
                pass # OK
            else:
                return "Not Connected"
        except:
            return "Error Checking Status"

        # 2. Run serve
        self._run_tailscale_cmd(["serve", f"http://localhost:{port}"])
        
        # 3. Get URL
        return self.get_domain()

    def get_domain(self):
        res = self._run_tailscale_cmd(["status", "--json"])
        import json
        try:
            data = json.loads(res.stdout)
            return "https://" + data["Self"]["DNSName"].rstrip(".")
        except:
            return None

    def stop(self):
        self.cleanup()
