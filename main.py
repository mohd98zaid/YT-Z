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
    print("=" * 65)
    print("           YT-Z: Ultimate YouTube Music & Downloader")
    print("             High-Fidelity Audio & 4K Engine")
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
