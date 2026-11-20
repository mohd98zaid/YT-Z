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

def get_lan_ip() -> str:
    """Detects primary local network IP address on current Wi-Fi/Ethernet interface"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def is_server_running() -> bool:
    try:
        r = requests.get(f"{APP_URL}/api/status", timeout=0.8)
        return r.status_code == 200
    except Exception:
        return False

def start_backend():
    """Starts the FastAPI backend using Uvicorn on 0.0.0.0 to enable LAN / multi-device access"""
    from backend.server import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

def wait_for_server(timeout: int = 15) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_server_running():
            return True
        time.sleep(0.3)
    return False

def patch_edgechromium_fullscreen():
    """
    Hooks Microsoft Edge WebView2 ContainsFullScreenElementChanged event
    so that when any HTML5 element (YouTube video player, fullscreen button, or F11)
    enters fullscreen, the native desktop window automatically toggles into true borderless
    fullscreen without window borders or taskbar, and restores cleanly on exit.
    """
    try:
        import webview.platforms.edgechromium as ec
        original_on_webview_ready = ec.EdgeChrome.on_webview_ready

        def hooked_on_webview_ready(self, sender, args):
            original_on_webview_ready(self, sender, args)
            if not getattr(args, "IsSuccess", False):
                return

            def on_fullscreen_changed(c_sender, c_args):
                try:
                    is_fs = bool(c_sender.ContainsFullScreenElement)
                    if hasattr(self, "form") and self.form:
                        current_fs = bool(getattr(self.form, "is_fullscreen", False))
                        if is_fs != current_fs and hasattr(self.form, "toggle_fullscreen"):
                            self.form.toggle_fullscreen()
                except Exception as ex:
                    logger.debug(f"Fullscreen change handler note: {ex}")

            try:
                sender.CoreWebView2.ContainsFullScreenElementChanged += on_fullscreen_changed
                logger.info("Successfully hooked WebView2 ContainsFullScreenElementChanged for native desktop fullscreen")
            except Exception as ex:
                logger.debug(f"Could not register ContainsFullScreenElementChanged: {ex}")

            # Hook WebResourceRequested to supply legitimate Referer header for YouTube iframe embeds
            # This completely eliminates YouTube error: "This video is unavailable / Watch on YouTube"
            try:
                def on_web_resource_requested(c_sender, c_args):
                    try:
                        uri = str(c_args.Request.Uri)
                        if "youtube.com" in uri or "googlevideo.com" in uri:
                            c_args.Request.Headers.SetHeader("Referer", "https://www.youtube.com/")
                    except Exception:
                        pass

                sender.CoreWebView2.AddWebResourceRequestedFilter("*youtube.com*", ec.CoreWebView2WebResourceContext.All)
                sender.CoreWebView2.AddWebResourceRequestedFilter("*googlevideo.com*", ec.CoreWebView2WebResourceContext.All)
                sender.CoreWebView2.WebResourceRequested += on_web_resource_requested
                logger.info("Successfully registered WebView2 Referer override for YouTube player playback")
            except Exception as ex:
                logger.debug(f"Could not register WebResourceRequested filter: {ex}")

        ec.EdgeChrome.on_webview_ready = hooked_on_webview_ready
    except Exception as e:
        logger.debug(f"EdgeChromium patch note: {e}")

def main():
    lan_ip = get_lan_ip()
    lan_url = f"http://{lan_ip}:{PORT}"

    print("=" * 65)
    print("           YT-Z: Ultimate YouTube Music & Streaming Server")
    print("             High-Fidelity Audio & 4K Engine")
    print("=" * 65)

    # 1. Check if backend is already running
    if is_server_running():
        print(f"[✓] Core backend is already running.")
    else:
        print(f"[*] Starting core backend service on 0.0.0.0:{PORT}...")
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()

        if not wait_for_server():
            print("[!] Server failed to start within timeout.")
            sys.exit(1)
        print(f"[✓] Core engine online!")

    print("-" * 65)
    print(f"  [✓] Local access:   {APP_URL}")
    print(f"  [✓] Network access: {lan_url}  (Any phone/device on Wi-Fi)")
    print("-" * 65)

    # Check for server-only / headless LAN media server mode
    server_only = any(arg in sys.argv for arg in ["--server-only", "--server", "--headless", "--no-ui", "-s"])
    if server_only:
        print("\n[*] Running in LAN Media Server mode (Headless).")
        print(f"[*] Open {lan_url} on your Phone, Tablet, Laptop, or TV to stream.")
        print("[*] Press Ctrl+C to stop the server.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down YT-Z server...")
            return

    # 2. Check launch mode
    force_browser = "--browser" in sys.argv or "-b" in sys.argv

    if not force_browser:
        try:
            import webview
            patch_edgechromium_fullscreen()
            print("[*] Launching native desktop window via pywebview (with true fullscreen support)...")
            window = webview.create_window(
                title="YT-Z - Ultimate YouTube Music & Downloader",
                url=APP_URL,
                width=1280,
                height=850,
                min_size=(960, 640),
                background_color="#0a0a0c"
            )
            # Ensure persistent storage for localStorage, cookies, session across restarts
            storage_dir = Path.home() / ".ytz" / "webview_data"
            storage_dir.mkdir(parents=True, exist_ok=True)
            webview.start(debug=False, private_mode=False, storage_path=str(storage_dir))
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
