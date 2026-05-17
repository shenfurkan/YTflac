import sys
import logging
import os
import traceback
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QFontDatabase, QFont
from PyQt6.QtCore import Qt

from . import fluent as F
from .main_window import SpotiflacApp
from . import style as S
from ..core.paths import app_log_path

def _log_crash(exctype, value, tb):
    """Global crash handler."""
    log_path = app_log_path("ytflac_crash.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat()}] FATAL CRASH\n")
        traceback.print_exception(exctype, value, tb, file=f)
    print(f"FATAL CRASH. Details saved to {log_path}", file=sys.stderr)
    sys.__excepthook__(exctype, value, tb)

def _resource_path(*parts: str) -> str:
    """Resolve a bundled resource path for both dev and PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)

def run():
    from .main_window_shared import _setup_debug_logging
    _setup_debug_logging()

    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YtFLAC")

    sys.excepthook = _log_crash
    try:
        # PyQt6 enables high DPI scaling by default — no attribute needed
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(S.QSS)
        
        # Configure font rendering for smooth edges
        font = app.font()
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        app.setFont(font)

        # Load custom fonts (Google Sans)
        google_sans_dir = _resource_path("ytflac", "fonts", "google sans")
        if os.path.isdir(google_sans_dir):
            for root_dir, _, files in os.walk(google_sans_dir):
                for f in files:
                    if f.endswith(".ttf"):
                        id_ = QFontDatabase.addApplicationFont(os.path.join(root_dir, f))
                        if id_ >= 0:
                            families = QFontDatabase.applicationFontFamilies(id_)
                            if families:
                                logging.info(f"Loaded font: {families[0]}")
                        else:
                            logging.warning(f"Failed to load font: {f}")

        # Initialize theme from settings
        from PyQt6.QtCore import QSettings
        settings = QSettings("YtFLAC", "YtFLAC")
        saved_theme = settings.value("theme", "light", type=str).lower()
        S.set_theme(saved_theme)
        F.apply_fluent_theme(saved_theme, S.ACCENT)
        app.setStyleSheet(S.QSS)
        logging.info("Style source: %s", getattr(S, "__file__", "<unknown>"))
        logging.info("Style theme: %s", saved_theme)
        logging.info("Style QSS hash: %s", hex(abs(hash(S.QSS)) & 0xFFFFFFFF))
        logging.info("Python executable: %s", sys.executable)

        icon_path = _resource_path("images", "APPLOGO.ico")
        if not os.path.exists(icon_path):
            icon_path = _resource_path("images", "APPLOGO.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        window = SpotiflacApp()

        # Windows 11 rounded corners via DWM
        if sys.platform == "win32":
            try:
                import ctypes
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                hwnd = int(window.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
                    ctypes.sizeof(ctypes.c_int),
                )
            except Exception:
                pass

        window.show()

        ret = app.exec()
        logging.info("YtFLAC GUI exited with code %d", ret)
        return ret
    except Exception:
        _log_crash(*sys.exc_info())
        return 1
