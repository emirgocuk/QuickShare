"""
WebRTC P2P Test - Loopback test for sender/receiver
Tests: SDP exchange, DataChannel connection, file transfer
"""
import asyncio
import os
import sys
import time
import tempfile
import hashlib

# Fix Windows console encoding for emoji
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webrtc_manager import WebRTCSender, WebRTCReceiver


def create_test_file(path, size_kb=100):
    """Create a test file with random-ish data"""
    data = os.urandom(size_kb * 1024)
    with open(path, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def test_p2p_transfer():
    """Test P2P file transfer locally"""
    print("=" * 50)
    print("WebRTC P2P Loopback Test")
    print("=" * 50)

    # Create test file
    test_dir = tempfile.mkdtemp(prefix="quickshare_test_")
    test_file = os.path.join(test_dir, "test_100kb.bin")
    expected_hash = create_test_file(test_file, size_kb=100)
    print(f"\n✅ Test file created: {test_file}")
    print(f"   Hash: {expected_hash}")
    print(f"   Size: {os.path.getsize(test_file)} bytes")

    # Save dir
    save_dir = tempfile.mkdtemp(prefix="quickshare_recv_")
    print(f"   Save dir: {save_dir}")

    # Create sender
    print("\n--- Setting up Sender ---")
    sender = WebRTCSender()
    sender.log_callback = lambda msg: print(f"  [SENDER] {msg}")
    sender.set_files([{
        "name": "test_100kb.bin",
        "path": test_file,
        "size": os.path.getsize(test_file)
    }])
    sender.start()
    time.sleep(0.5)
    print("  Sender started.")

    # Create receiver
    print("\n--- Setting up Receiver ---")
    receiver = WebRTCReceiver()
    receiver.save_path = save_dir
    receiver.log_callback = lambda msg: print(f"  [RECV]   {msg}")
    
    progress_updates = []
    def on_progress(dl, total, speed, cf, tf):
        pct = (dl / total * 100) if total else 0
        progress_updates.append(pct)
        if len(progress_updates) % 5 == 0:
            print(f"  [PROG]   {pct:.1f}% ({dl}/{total})")
    receiver.progress_callback = on_progress

    # Step 1: Receiver creates offer
    print("\n--- Step 1: Create Offer ---")
    offer = receiver.create_offer_sync()
    print(f"  Offer SDP type: {offer['type']}")
    print(f"  Offer SDP length: {len(offer['sdp'])} chars")

    # Step 2: Sender creates answer from offer
    print("\n--- Step 2: Create Answer ---")
    answer = sender.handle_offer_sync(offer["sdp"])
    print(f"  Answer SDP type: {answer['type']}")
    print(f"  Answer SDP length: {len(answer['sdp'])} chars")

    # Step 3: Receiver sets answer
    print("\n--- Step 3: Set Answer ---")
    receiver.set_answer_sync(answer["sdp"])

    # Step 4: Wait for connection
    print("\n--- Step 4: Waiting for P2P connection ---")
    connected = receiver.wait_for_connection(timeout=15)
    
    if not connected:
        print("  ❌ Connection TIMEOUT!")
        sender.stop()
        receiver.stop()
        return False
    
    if receiver.status == "failed":
        print("  ❌ Connection FAILED!")
        sender.stop()
        receiver.stop()
        return False
    
    print(f"  ✅ Connected! Receiver status: {receiver.status}")

    # Step 5: Sender sends files (triggered by "ready" message from receiver)
    print("\n--- Step 5: Waiting for sender to detect 'ready' ---")
    time.sleep(1)  # Give time for "ready" message to arrive
    
    # Manually trigger send if needed
    if sender.status == "connected":
        print("  Triggering file send...")
        sender.send_files()
    
    # Step 6: Wait for transfer
    print("\n--- Step 6: Waiting for transfer to complete ---")
    done = receiver.wait_for_transfer(timeout=30)
    
    if not done:
        print("  ❌ Transfer TIMEOUT!")
        sender.stop()
        receiver.stop()
        return False

    # Step 7: Verify
    print("\n--- Step 7: Verification ---")
    received_file = os.path.join(save_dir, "test_100kb.bin")
    
    if not os.path.exists(received_file):
        print(f"  ❌ File not found at {received_file}")
        sender.stop()
        receiver.stop()
        return False
    
    with open(received_file, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    
    print(f"  Expected: {expected_hash}")
    print(f"  Actual:   {actual_hash}")
    
    if expected_hash == actual_hash:
        print(f"  ✅ Hash MATCH! File transfer successful!")
        print(f"  Progress updates: {len(progress_updates)}")
        success = True
    else:
        print(f"  ❌ Hash MISMATCH!")
        success = False

    # Cleanup
    sender.stop()
    receiver.stop()
    time.sleep(0.5)
    
    # Clean temp files
    try:
        os.remove(test_file)
        os.remove(received_file)
        os.rmdir(test_dir)
        os.rmdir(save_dir)
    except:
        pass
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ PASSED' if success else '❌ FAILED'}")
    print("=" * 50)
    return success


if __name__ == "__main__":
    success = test_p2p_transfer()
    sys.exit(0 if success else 1)
