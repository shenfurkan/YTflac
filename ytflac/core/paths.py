from __future__ import annotations

import os
from pathlib import Path

_APP_DIR_NAME = "spotiflac"


def app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            root = Path(base)
        else:
            root = Path.home() / "AppData" / "Local"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = root / _APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_log_path(filename: str) -> Path:
    return app_data_dir() / filename
