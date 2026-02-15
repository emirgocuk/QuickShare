"""
QuickShare Build Script - Nuitka Edition
C++ compiler kullanarak daha küçük ve hızlı exe oluşturma

AVANTAJLAR:
- Daha küçük exe boyutu (~30-40% azalma)
- Daha hızlı çalışma (C++ compile edilmiş)
- Daha stabil (native code)

DEZAVANTAJLAR:
- Çok daha uzun build süresi (10-30 dakika)
- C++ compiler gerekir (MSVC veya MinGW)

KURULUM:
pip install nuitka ordered-set zstandard
"""

import os
import sys
import subprocess


def check_requirements():
    """Gerekli araçları kontrol et"""
    print("🔍 Checking requirements...\n")
    
    # Nuitka kontrolü
    try:
        import nuitka
        print("✅ Nuitka installed")
    except ImportError:
        print("❌ Nuitka not found!")
        print("   Install: pip install nuitka ordered-set zstandard")
        return False
    
    # Cloudflared kontrolü
    cloudflared_path = "bin/cloudflared.exe"
    if not os.path.exists(cloudflared_path):
        print(f"❌ cloudflared.exe not found at {cloudflared_path}")
        return False
    
    print(f"✅ cloudflared.exe found ({os.path.getsize(cloudflared_path) / 1024 / 1024:.2f} MB)")
    
    # C++ compiler kontrolü (opsiyonel uyarı)
    print("\n⚠️  C++ Compiler Required:")
    print("   - Windows: Visual Studio veya MinGW64")
    print("   - Nuitka otomatik bulacak, yoksa uyarı verecek\n")
    
    return True


def build_with_nuitka():
    """Nuitka ile build et"""
    print("🔨 Building with Nuitka...\n")
    print("⏱️  This will take 10-30 minutes (much slower than PyInstaller!)\n")
    
    # Nuitka komut satırı
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",                          # Standalone exe
        "--onefile",                             # Tek dosya
        "--windows-disable-console",             # Console gizle
        "--output-filename=QuickShare.exe",      # Exe adı
        "--output-dir=dist_nuitka",              # Output klasörü
        "--include-data-files=bin/cloudflared.exe=bin/cloudflared.exe",  # Binary ekle
        "--enable-plugin=tk-inter",              # Tkinter plugin
        "--follow-imports",                      # Import'ları takip et
        "--assume-yes-for-downloads",            # Otomatik indir
        "--show-progress",                       # Progress göster
        "--show-memory",                         # Memory kullanımı göster
        "main.py"
    ]
    
    # Windows-specific: MSVC tercih et
    if os.name == 'nt':
        cmd.insert(3, "--msvc=latest")
    
    print("Command:", " ".join(cmd), "\n")
    
    try:
        # Build başlat
        result = subprocess.run(cmd, check=True)
        
        # Başarı kontrolü
        exe_path = "dist_nuitka/QuickShare.exe"
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / 1024 / 1024
            print(f"\n✅ Build successful!")
            print(f"   Output: {exe_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"\n📊 Comparison with PyInstaller:")
            print(f"   PyInstaller: ~67 MB")
            print(f"   Nuitka: {size_mb:.2f} MB")
            print(f"   Reduction: {((67 - size_mb) / 67 * 100):.1f}%")
        else:
            print("\n❌ Build failed - exe not created")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False
    
    return True


def main():
    """Ana fonksiyon"""
    print("=" * 60)
    print("QuickShare - Nuitka Build")
    print("=" * 60)
    print()
    
    if not check_requirements():
        print("\n❌ Requirements not met. Please install missing components.")
        sys.exit(1)
    
    print("\n⚠️  WARNING:")
    print("   Nuitka build is MUCH slower than PyInstaller (10-30 min)")
    print("   But produces smaller, faster exe\n")
    
    response = input("Continue with Nuitka build? (y/N): ")
    if response.lower() != 'y':
        print("Build cancelled.")
        sys.exit(0)
    
    print()
    if build_with_nuitka():
        print("\n🎉 Build complete! Exe ready for distribution.")
    else:
        print("\n❌ Build failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
