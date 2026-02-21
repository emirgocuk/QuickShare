"""
QuickShare Build Script - WebUI (PyWebView) Version
PyInstaller ile modern Web arayüzünü exe içerisine gömme
"""

import PyInstaller.__main__
import os
import sys

def build():
    """Exe build işlemini gerçekleştir"""
    
    # Cloudflared binary kontrolü
    cloudflared_path = "bin/cloudflared.exe"
    if not os.path.exists(cloudflared_path):
        print("❌ Error: cloudflared.exe bulunamadı!")
        print(f"   Lütfen {cloudflared_path} yoluna cloudflared binary'sini yerleştirin")
        sys.exit(1)
        
    print("🔨 Building QuickShare.exe (WebUI Version)...")
    
    # WebView2 için HTML/CSS/JS dosyalarını dahil etmemiz gerekiyor
    web_dir = 'web'
    if not os.path.exists(web_dir):
        print(f"❌ Error: '{web_dir}' klasörü bulunamadı!")
        sys.exit(1)
        
    # Asset separator is ';' on Windows, ':' on Unix
    sep = ';' if os.name == 'nt' else ':'

    # PyInstaller parametreleri
    args = [
        'main_web.py',                              # Ana dosya
        '--onefile',                                # Tek exe oluştur
        '--windowed',                               # Arka planda siyah konsol (terminal) penceresini gizle
        '--name=QuickShare',                        # Oluşacak Exe adı
        f'--add-binary={cloudflared_path}{sep}bin', # Tunnel binary
        f'--add-data={web_dir}{sep}web',            # Arayüz dosyalarını (HTML, CSS) exe içine göm
        '--hidden-import=webview',
        '--hidden-import=flask',
        '--hidden-import=api',
        '--clean',                                  # Önceki build'i temizle
        '--noconfirm',                              # Overwrite onayı sorma
    ]
    
    # Windows için WebView2 kütüphanelerine de ihtiyaç duyabilir, Pywebview genelde bunu halleder
    
    if os.path.exists('icon.ico'):
        args.append('--icon=icon.ico')
    
    print("\n🚀 Starting pywebview build process...")
    print("   This may take a few minutes...\n")
    
    try:
        PyInstaller.__main__.run(args)
        
        exe_path = "dist/QuickShare.exe"
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / 1024 / 1024
            print(f"\n✅ Build successful!")
            print(f"   Output: {exe_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print("   Note: PyWebView exe files bundle a local web server and browser engine hooks.")
        else:
            print("\n❌ Build failed - exe oluşturulamadı")
            
    except Exception as e:
        print(f"\n❌ Build error: {e}")
        sys.exit(1)

def clean():
    import shutil
    dirs = ['build', 'dist', '__pycache__']
    for d in dirs:
        if os.path.exists(d): shutil.rmtree(d)
    if os.path.exists('QuickShare.spec'): os.remove('QuickShare.spec')
    print("✅ Clean complete")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build()
