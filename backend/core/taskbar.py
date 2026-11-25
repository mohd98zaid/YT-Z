"""
YT-Z Windows Taskbar Thumbnail Toolbar & Media Controls Integration
Provides interactive playback controls (Previous, Play/Pause, Next) and dynamic track tooltips
directly inside the Windows Taskbar thumbnail preview window via ITaskbarList3 COM API.
"""

import sys
import logging
import threading

logger = logging.getLogger("YTZ.Taskbar")

_taskbar_manager = None

def get_taskbar_manager():
    global _taskbar_manager
    if _taskbar_manager is None and sys.platform == "win32":
        try:
            _taskbar_manager = WindowsTaskbarManager()
        except Exception as e:
            logger.debug(f"TaskbarManager initialization note: {e}")
            _taskbar_manager = DummyTaskbarManager()
    elif _taskbar_manager is None:
        _taskbar_manager = DummyTaskbarManager()
    return _taskbar_manager

class DummyTaskbarManager:
    def attach(self, form, webview_window):
        pass
    def update_playback(self, is_playing: bool, title: str, artist: str):
        pass

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import clr

    try:
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Windows.Forms as WinForms
        from System.Drawing import Bitmap, Graphics, Color, SolidBrush, PointF, RectangleF
        from System.Drawing.Drawing2D import SmoothingMode
    except Exception as e:
        logger.debug(f"Could not load System.Windows.Forms or System.Drawing: {e}")

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_byte * 8),
        ]

    CLSID_TaskbarList = GUID(
        0x56FDF344, 0xFD6D, 0x11D0, (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90)
    )
    IID_ITaskbarList3 = GUID(
        0xEA1AFB91, 0x9E28, 0x4B86, (ctypes.c_byte * 8)(0x90, 0xE9, 0x9E, 0x9F, 0x8A, 0x5E, 0xEF, 0xAF)
    )

    class THUMBBUTTON(ctypes.Structure):
        _fields_ = [
            ("dwMask", wintypes.DWORD),
            ("iId", wintypes.UINT),
            ("iBitmap", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 260),
            ("dwFlags", wintypes.DWORD),
        ]

    THB_ICON = 0x2
    THB_TOOLTIP = 0x4
    THB_FLAGS = 0x8

    THBF_ENABLED = 0x0
    THBF_DISABLED = 0x1
    THBF_DISMISSONCLICK = 0x2

    WM_COMMAND = 0x0111
    THBN_CLICKED = 0x1800

    class WindowsTaskbarManager:
        BUTTON_PREV = 1
        BUTTON_PLAY_PAUSE = 2
        BUTTON_NEXT = 3

        def __init__(self):
            self.hwnd = None
            self.form = None
            self.webview_window = None
            self.taskbar = None
            self.vtbl = None
            self.buttons_added = False
            self.is_playing = False
            self.current_title = "YT-Z"
            self.current_artist = "Ultimate YouTube Music"

            self.user32 = ctypes.windll.user32
            self.ole32 = ctypes.windll.ole32
            self.WM_TASKBARBUTTONCREATED = self.user32.RegisterWindowMessageW("TaskbarButtonCreated")

            self._init_com()
            self._create_icons()

        def _init_com(self):
            try:
                # Ensure connection to Default interactive desktop if running in an isolated station
                tray = self.user32.FindWindowW("Shell_TrayWnd", None)
                if not tray:
                    try:
                        hdesk = self.user32.OpenDesktopW("Default", 0, False, 0x01FF)
                        if hdesk:
                            self.user32.SetThreadDesktop(hdesk)
                    except Exception:
                        pass

                self.ole32.CoInitialize(None)
                p_taskbar = ctypes.c_void_p()
                hr = self.ole32.CoCreateInstance(
                    ctypes.byref(CLSID_TaskbarList),
                    None,
                    1, # CLSCTX_INPROC_SERVER
                    ctypes.byref(IID_ITaskbarList3),
                    ctypes.byref(p_taskbar),
                )
                if hr == 0 and p_taskbar.value:
                    self.taskbar = p_taskbar
                    vtable_ptr = ctypes.cast(p_taskbar.value, ctypes.POINTER(ctypes.c_void_p)).contents
                    self.vtbl = ctypes.cast(vtable_ptr, ctypes.POINTER(ctypes.c_void_p))

                    # 3: HrInit
                    self.HrInit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(self.vtbl[3])
                    # 15: ThumbBarAddButtons(HWND, UINT, LPTHUMBBUTTON)
                    self.ThumbBarAddButtons = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, wintypes.HWND, wintypes.UINT, ctypes.POINTER(THUMBBUTTON)
                    )(self.vtbl[15])
                    # 16: ThumbBarUpdateButtons(HWND, UINT, LPTHUMBBUTTON)
                    self.ThumbBarUpdateButtons = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, wintypes.HWND, wintypes.UINT, ctypes.POINTER(THUMBBUTTON)
                    )(self.vtbl[16])
                    # 19: SetThumbnailTooltip(HWND, LPCWSTR)
                    self.SetThumbnailTooltip = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.c_wchar_p
                    )(self.vtbl[19])

                    try:
                        self.HrInit(self.taskbar)
                    except Exception:
                        pass
                    logger.info("Windows Shell ITaskbarList3 initialized successfully")
                else:
                    logger.debug(f"CoCreateInstance ITaskbarList3 returned: {hex(hr & 0xFFFFFFFF)}")
            except Exception as e:
                logger.debug(f"Taskbar COM initialization note: {e}")

        def _create_icons(self):
            try:
                size = 24
                brush = SolidBrush(Color.White)

                # 1. Previous Track icon (|<<)
                bmp_prev = Bitmap(size, size)
                g = Graphics.FromImage(bmp_prev)
                g.SmoothingMode = SmoothingMode.AntiAlias
                g.FillRectangle(brush, RectangleF(3.5, 5.0, 2.0, 14.0))
                g.FillPolygon(brush, [PointF(11.0, 5.0), PointF(4.5, 12.0), PointF(11.0, 19.0)])
                g.FillPolygon(brush, [PointF(18.0, 5.0), PointF(11.5, 12.0), PointF(18.0, 19.0)])
                g.Dispose()
                self.hIcon_prev = bmp_prev.GetHicon().ToInt64()

                # 2. Play icon (>)
                bmp_play = Bitmap(size, size)
                g = Graphics.FromImage(bmp_play)
                g.SmoothingMode = SmoothingMode.AntiAlias
                g.FillPolygon(brush, [PointF(7.0, 4.0), PointF(19.0, 12.0), PointF(7.0, 20.0)])
                g.Dispose()
                self.hIcon_play = bmp_play.GetHicon().ToInt64()

                # 3. Pause icon (||)
                bmp_pause = Bitmap(size, size)
                g = Graphics.FromImage(bmp_pause)
                g.SmoothingMode = SmoothingMode.AntiAlias
                g.FillRectangle(brush, RectangleF(6.0, 4.5, 3.5, 15.0))
                g.FillRectangle(brush, RectangleF(14.5, 4.5, 3.5, 15.0))
                g.Dispose()
                self.hIcon_pause = bmp_pause.GetHicon().ToInt64()

                # 4. Next Track icon (>>|)
                bmp_next = Bitmap(size, size)
                g = Graphics.FromImage(bmp_next)
                g.SmoothingMode = SmoothingMode.AntiAlias
                g.FillPolygon(brush, [PointF(6.0, 5.0), PointF(12.5, 12.0), PointF(6.0, 19.0)])
                g.FillPolygon(brush, [PointF(13.0, 5.0), PointF(19.5, 12.0), PointF(13.0, 19.0)])
                g.FillRectangle(brush, RectangleF(18.5, 5.0, 2.0, 14.0))
                g.Dispose()
                self.hIcon_next = bmp_next.GetHicon().ToInt64()
            except Exception as e:
                logger.debug(f"Media icon generation note: {e}")
                self.hIcon_prev = 0
                self.hIcon_play = 0
                self.hIcon_pause = 0
                self.hIcon_next = 0

        def attach(self, form, webview_window):
            self.form = form
            self.webview_window = webview_window
            if not form or not hasattr(form, "Handle"):
                return

            self.hwnd = form.Handle.ToInt64()
            logger.info(f"Attaching TaskbarManager to window handle: {self.hwnd}")

            manager_self = self
            class TaskbarHookWindow(WinForms.NativeWindow):
                def WndProc(self, m):
                    try:
                        msg = m.Msg
                        if msg == manager_self.WM_TASKBARBUTTONCREATED:
                            logger.info("Received WM_TASKBARBUTTONCREATED, re-adding taskbar buttons")
                            manager_self.buttons_added = False
                            manager_self._try_add_buttons()
                        elif msg == WM_COMMAND:
                            wparam = m.WParam.ToInt64()
                            hiword = (wparam >> 16) & 0xFFFF
                            loword = wparam & 0xFFFF
                            if hiword == THBN_CLICKED:
                                manager_self._on_button_clicked(loword)
                    except Exception as ex:
                        logger.debug(f"WndProc taskbar hook exception: {ex}")
                    super().WndProc(m)

            try:
                self.native_window = TaskbarHookWindow()
                self.native_window.AssignHandle(form.Handle)
                logger.info("Successfully hooked WndProc for taskbar messages")
            except Exception as ex:
                logger.debug(f"NativeWindow AssignHandle note: {ex}")

            self._try_add_buttons()

        def _on_button_clicked(self, button_id: int):
            action = None
            if button_id == self.BUTTON_PREV:
                action = "previous"
            elif button_id == self.BUTTON_PLAY_PAUSE:
                action = "togglePlay"
            elif button_id == self.BUTTON_NEXT:
                action = "next"

            if not action or not self.webview_window:
                return

            logger.info(f"Taskbar button clicked: {action}")
            def dispatch():
                try:
                    js = f"window.dispatchEvent(new CustomEvent('ytz-taskbar-action', {{ detail: '{action}' }}));"
                    self.webview_window.evaluate_js(js)
                except Exception as ex:
                    logger.debug(f"Dispatch taskbar action note: {ex}")

            threading.Thread(target=dispatch, daemon=True).start()

        def _build_buttons(self, is_playing: bool):
            btn_prev = THUMBBUTTON()
            btn_prev.dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            btn_prev.iId = self.BUTTON_PREV
            btn_prev.hIcon = self.hIcon_prev
            btn_prev.szTip = "Previous Track"
            btn_prev.dwFlags = THBF_ENABLED

            btn_play = THUMBBUTTON()
            btn_play.dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            btn_play.iId = self.BUTTON_PLAY_PAUSE
            btn_play.hIcon = self.hIcon_pause if is_playing else self.hIcon_play
            btn_play.szTip = "Pause" if is_playing else "Play"
            btn_play.dwFlags = THBF_ENABLED

            btn_next = THUMBBUTTON()
            btn_next.dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            btn_next.iId = self.BUTTON_NEXT
            btn_next.hIcon = self.hIcon_next
            btn_next.szTip = "Next Track"
            btn_next.dwFlags = THBF_ENABLED

            return (THUMBBUTTON * 3)(btn_prev, btn_play, btn_next)

        def _try_add_buttons(self):
            if not self.taskbar or not self.hwnd or self.buttons_added:
                return
            try:
                btns = self._build_buttons(self.is_playing)
                hr = self.ThumbBarAddButtons(self.taskbar, self.hwnd, 3, btns)
                if hr == 0:
                    self.buttons_added = True
                    logger.info("Successfully added Taskbar Thumbnail Toolbar buttons!")
                    self._update_tooltip()
                else:
                    logger.debug(f"ThumbBarAddButtons returned: {hex(hr & 0xFFFFFFFF)}")
            except Exception as e:
                logger.debug(f"ThumbBarAddButtons note: {e}")

        def update_playback(self, is_playing: bool, title: str, artist: str):
            self.is_playing = bool(is_playing)
            if title:
                self.current_title = str(title).strip()
            if artist is not None:
                self.current_artist = str(artist).strip()

            if not self.taskbar or not self.hwnd:
                return

            if not self.buttons_added:
                self._try_add_buttons()

            try:
                btns = self._build_buttons(self.is_playing)
                self.ThumbBarUpdateButtons(self.taskbar, self.hwnd, 3, btns)
                self._update_tooltip()
            except Exception as e:
                logger.debug(f"ThumbBarUpdateButtons note: {e}")

        def _update_tooltip(self):
            if not self.taskbar or not self.hwnd:
                return
            try:
                tip = (
                    f"{self.current_title} - {self.current_artist} | YT-Z"
                    if self.current_artist
                    else f"{self.current_title} | YT-Z"
                )
                if len(tip) > 250:
                    tip = tip[:247] + "..."
                self.SetThumbnailTooltip(self.taskbar, self.hwnd, tip)
            except Exception as e:
                logger.debug(f"SetThumbnailTooltip note: {e}")
