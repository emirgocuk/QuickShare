import webview
import os
import sys
from api import QuickShareAPI

def main():
    print("Starting QuickShare WebUI...")
    
    # Enable High DPI support
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    api = QuickShareAPI()
    
    # Pyinstaller compatibility
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    html_file = os.path.join(base_dir, 'web', 'index.html')
    
    # Create window
    # Easy drag-and-drop is natively supported by webview in Windows (WebView2)
    window = webview.create_window(
        title='QuickShare - P2P File Transfer',
        url=f'file:///{html_file}',
        js_api=api,
        width=1100,
        height=750,
        min_size=(900, 600),
        background_color='#0D1117' # Match Tailwind background
    )
    
    # Pass window reference to API if it needs to evaluate JS proactively
    api.window = window

    # Start loop
    webview.start(debug=True)

if __name__ == '__main__':
    main()
