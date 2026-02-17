import time
import sys
import ctypes
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
NMPWAIT_USE_DEFAULT_WAIT = 0
INVALID_HANDLE_VALUE = -1

def create_pipe(name):
    print(f"Attempting to create pipe: {name}")
    
    h_pipe = kernel32.CreateNamedPipeW(
        name,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES,
        65536,
        65536,
        0,
        None
    )
    
    if h_pipe == INVALID_HANDLE_VALUE:
        err = kernel32.GetLastError()
        print(f"FAILED. Error code: {err}")
        return False
    else:
        print(f"SUCCESS. Handle: {h_pipe}")
        kernel32.CloseHandle(h_pipe)
        return True

if __name__ == "__main__":
    # Test 1: Standard Name
    create_pipe(r"\\.\pipe\test-python-pipe")
    
    # Test 2: Name with prefix (like tailscale might use?) 
    # Note: \\.\pipe\ is strictly required.
    
    # Test 3: The one we tried
    create_pipe(r"\\.\pipe\quickshare-ts")
