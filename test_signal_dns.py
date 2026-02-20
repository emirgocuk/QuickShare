import socketio
import asyncio
import sys

# Force SelectorEventLoop for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    sio = socketio.AsyncClient()

    @sio.event
    async def connect():
        print("Bağlandı (SelectorEventLoop ile)!")
        await sio.disconnect()

    try:
        await sio.connect('https://quickshare-signal.onrender.com', wait_timeout=10)
        await sio.wait()
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == '__main__':
    asyncio.run(main())
