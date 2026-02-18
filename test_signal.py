import socketio
import asyncio

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("✅ Bağlantı Başarılı!")
    print("Sinyal sunucusu çalışıyor.")
    await sio.disconnect()

@sio.event
async def connect_error(data):
    print(f"❌ Bağlantı Hatası: {data}")

@sio.event
async def disconnect():
    print("Bağlantı kesildi.")

async def main():
    try:
        print("Sunucuya bağlanılıyor: https://quickshare-signal.onrender.com")
        await sio.connect('https://quickshare-signal.onrender.com', wait_timeout=10)
        await sio.wait()
    except Exception as e:
        print(f"Hata oluştu: {e}")

if __name__ == '__main__':
    asyncio.run(main())
