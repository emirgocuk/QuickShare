"""
QuickShare Build Script
PyInstaller ile exe oluşturma

FAZ 5: Bu script çalıştırılacak
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
        print("   İndirme: https://github.com/cloudflare/cloudflared/releases")
        sys.exit(1)
    
    print("🔨 Building QuickShare.exe...")
    print(f"   Cloudflared: {cloudflared_path} ({os.path.getsize(cloudflared_path) / 1024 / 1024:.2f} MB)")
    
    # PyInstaller parametreleri
    args = [
        'main.py',                                # Ana dosya
        '--onefile',                              # Tek exe
        '--windowed',                             # Console gizle
        '--name=QuickShare',                      # Exe adı
        f'--add-binary={cloudflared_path};bin',   # Cloudflared bin/ klasörüne embed et
        '--hidden-import=tkinter',                # Tkinter import
        '--hidden-import=flask',                  # Flask import
        '--clean',                                # Önceki build'i temizle
        '--noconfirm',                            # Overwrite onayı otomatik
    ]
    
    # İsteğe bağlı: İcon ekle
    if os.path.exists('icon.ico'):
        args.append('--icon=icon.ico')
        print("   Icon: icon.ico")
    
    # Build
    print("\n🚀 Starting build process...")
    print("   This may take 2-3 minutes...\n")
    
    try:
        PyInstaller.__main__.run(args)
        
        # Başarı kontrolü
        exe_path = "dist/QuickShare.exe"
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / 1024 / 1024
            print(f"\n✅ Build successful!")
            print(f"   Output: {exe_path}")
            print(f"   Size: {size_mb:.2f} MB")
            
            if size_mb > 5:
                print(f"\n⚠️  Warning: Exe boyutu 5 MB'ın üzerinde ({size_mb:.2f} MB)")
                print("   UPX compression kullanmayı düşünebilirsin")
            
        else:
            print("\n❌ Build failed - exe oluşturulamadı")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Build error: {e}")
        sys.exit(1)


def clean():
    """Build artifactlarını temizle"""
    import shutil
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['QuickShare.spec']
    
    print("🧹 Cleaning build artifacts...")
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed: {dir_name}/")
    
    for file_name in files_to_clean:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"   Removed: {file_name}")
    
    print("✅ Clean complete")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build()
