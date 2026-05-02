from __future__ import annotations

import contextlib
import os
import ctypes


_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def _is_windows() -> bool:
    return os.name == "nt"


def _set_thread_execution_state(flags: int) -> int:
    if not _is_windows():
        return 1
    try:
        return int(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:
        return 0


@contextlib.contextmanager
def keep_awake(*, display: bool = True):
    if not _is_windows():
        yield
        return

    flags = _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
    if display:
        flags |= _ES_DISPLAY_REQUIRED

    _set_thread_execution_state(flags)
    try:
        yield
    finally:
        _set_thread_execution_state(_ES_CONTINUOUS)
