# SpotiFLAC/core/isrc_cache.py
"""
Cache persistente per ISRC — port di isrc_cache.go.
Evita chiamate ridondanti a Songlink/Soundplate per ISRC già risolti.

Performance: writes are coalesced — mutations accumulate in-memory and
are flushed to disk at most once every 5 seconds via a background timer,
rather than on every single put() call.
"""

from __future__ import annotations

import atexit
import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_FILE = Path.home() / ".cache" / "spotiflac" / "isrc-cache.json"
_FLUSH_INTERVAL_S = 5.0  # max seconds between disk writes

_cache_lock = threading.Lock()
_cache: dict[str, dict] | None = None
_dirty = False
_flush_timer: threading.Timer | None = None


def _load() -> dict[str, dict]:
    """Load cache from disk once; subsequent calls return the in-memory dict."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _CACHE_FILE.exists():
            _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        else:
            _cache = {}
    except Exception as exc:
        logger.warning("[isrc_cache] Load failed: %s", exc)
        _cache = {}
    return _cache


def _flush_to_disk() -> None:
    """Write the in-memory cache to disk. Called by the deferred timer."""
    global _dirty, _flush_timer
    with _cache_lock:
        _flush_timer = None
        if not _dirty or _cache is None:
            return
        try:
            _CACHE_FILE.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
            _dirty = False
            logger.debug("[isrc_cache] Flushed %d entries to disk", len(_cache))
        except Exception as exc:
            logger.warning("[isrc_cache] Flush failed: %s", exc)


def _schedule_flush() -> None:
    """Schedule a deferred disk write (coalesces multiple writes into one)."""
    global _flush_timer
    if _flush_timer is not None:
        return  # already scheduled
    _flush_timer = threading.Timer(_FLUSH_INTERVAL_S, _flush_to_disk)
    _flush_timer.daemon = True
    _flush_timer.start()


# Ensure any pending writes are flushed when the process exits.
atexit.register(_flush_to_disk)


def get_cached_isrc(track_id: str) -> str:
    """Return cached ISRC or empty string."""
    track_id = track_id.strip()
    if not track_id:
        return ""
    with _cache_lock:
        cache = _load()
        entry = cache.get(track_id, {})
        return entry.get("isrc", "").upper().strip()


def put_cached_isrc(track_id: str, isrc: str) -> None:
    """Store ISRC in the in-memory cache; schedule a deferred disk flush."""
    global _dirty
    track_id = track_id.strip()
    isrc = isrc.upper().strip()
    if not track_id or not isrc:
        return
    with _cache_lock:
        cache = _load()
        cache[track_id] = {"isrc": isrc, "updated_at": int(time.time())}
        _dirty = True
        _schedule_flush()
