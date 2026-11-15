"""
YT-Z Launcher
Launches the local backend core engine and opens the native desktop client window or browser.
"""
import sys
import time
import threading
import webbrowser
import logging
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("YTZ.Launcher")

PORT = 47892
APP_URL = f"http://127.0.0.1:{PORT}"

def is_server_running() -> bool:
    try:
        r = requests.get(f"{APP_URL}/api/status", timeout=0.8)
        return r.status_code == 200
    except Exception:
        return False

def start_backend():
    """Starts the FastAPI backend using Uvicorn"""
    from backend.server import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")

def wait_for_server(timeout: int = 15) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_server_running():
            return True
        time.sleep(0.3)
    return False

def main():
    print("=" * 65)
    print("           YT-Z: Ultimate YouTube Music & Downloader")
    print("       Combining ytm-rs + BitChord + StreamFlow Pro Engine")
    print("=" * 65)

    # 1. Check if backend is already running
    if is_server_running():
        print(f"[✓] Core backend is already running on {APP_URL}")
    else:
        print(f"[*] Starting core backend service on {APP_URL}...")
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()

        if not wait_for_server():
            print("[!] Server failed to start within timeout.")
            sys.exit(1)
        print(f"[✓] Core engine online!")

    # 2. Check launch mode
    force_browser = "--browser" in sys.argv or "-b" in sys.argv

    if not force_browser:
        try:
            import webview
            print("[*] Launching native desktop window via pywebview...")
            window = webview.create_window(
                title="YT-Z - Ultimate YouTube Music & Downloader",
                url=APP_URL,
                width=1280,
                height=850,
                min_size=(960, 640),
                background_color="#0a0a0c"
            )
            webview.start(debug=False)
            return
        except Exception as e:
            print(f"[!] Native window note: {e}")

    # Fallback / browser launch
    print(f"[*] Opening YT-Z in your default web browser: {APP_URL}")
    webbrowser.open(APP_URL)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down YT-Z...")

if __name__ == "__main__":
    main()
