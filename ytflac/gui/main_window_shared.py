from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime

from ..core.paths import app_log_path

SERVICES_ALL = ["tidal", "qobuz", "amazon", "deezer", "apple"]


def _resource_path(*parts: str) -> str:
    """Resolve a bundled resource path for both dev and PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base, *parts)


def _log_crash(exc_type, exc_value, exc_tb):
    try:
        log_path = app_log_path("ytflac_crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"[{datetime.now().isoformat()}] Unhandled exception\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass


def _setup_debug_logging():
    """Setup detailed debug logging on startup."""
    debug_log_path = app_log_path("ytflac_debug.log")
    session_log_path = app_log_path("ytflac_gui_session.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(debug_log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    has_debug_file = any(
        isinstance(h, logging.FileHandler)
        and os.path.abspath(getattr(h, "baseFilename", ""))
        == os.path.abspath(debug_log_path)
        for h in root_logger.handlers
    )
    if not has_debug_file:
        root_logger.addHandler(file_handler)

    session_handler = logging.FileHandler(session_log_path, encoding="utf-8")
    session_handler.setLevel(logging.INFO)
    session_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    session_handler.setFormatter(session_formatter)

    has_session_file = any(
        isinstance(h, logging.FileHandler)
        and os.path.abspath(getattr(h, "baseFilename", ""))
        == os.path.abspath(session_log_path)
        for h in root_logger.handlers
    )
    if not has_session_file:
        root_logger.addHandler(session_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    has_console = any(getattr(h, "_ytflac_console", False) for h in root_logger.handlers)
    if not has_console:
        setattr(console_handler, "_ytflac_console", True)
        root_logger.addHandler(console_handler)

    logging.info("=" * 60)
    logging.info("YtFLAC GUI Starting")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    logging.info(f"Debug log: {debug_log_path}")
    logging.info(f"Session log: {session_log_path}")
    logging.info("=" * 60)

    try:
        from ..core.progress import DownloadManager

        DownloadManager()
        logging.info("✓ DownloadManager initialized")
    except Exception as e:
        logging.warning(f"✗ DownloadManager failed: {e}")

    try:
        from ..core.provider_stats import ProviderScorer

        ProviderScorer()
        logging.info("✓ ProviderScorer initialized")
    except Exception as e:
        logging.warning(f"✗ ProviderScorer failed: {e}")

    try:
        from ..core.history import HistoryManager

        hm = HistoryManager()
        stats = hm.get_stats()
        logging.info(
            f"✓ HistoryManager initialized (total downloads: {stats.get('total', 0)})"
        )
    except Exception as e:
        logging.warning(f"✗ HistoryManager failed: {e}")

    try:
        logging.info("✓ ISRC cache functions loaded")
    except Exception as e:
        logging.warning(f"✗ ISRC cache failed: {e}")
