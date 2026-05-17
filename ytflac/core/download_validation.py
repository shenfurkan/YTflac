# SpotiFLAC/core/download_validation.py
"""
Port di download_validation.go — rileva preview da 30s e mismatch di durata.
"""

from __future__ import annotations
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

_PREVIEW_MAX_SECONDS = 35
_PREVIEW_EXPECTED_MIN = 60
_LARGE_MISMATCH_MIN = 90
_MIN_ALLOWED_DIFF = 15
_DURATION_DIFF_RATIO = 0.25


def _get_audio_duration(filepath: str) -> float:
    """Usa ffprobe per ottenere la durata in secondi."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                filepath,
            ],
            capture_output=True,
            text=True,
        )
        import json

        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def validate_downloaded_track(
    filepath: str,
    expected_seconds: int,
) -> tuple[bool, str]:
    """
    Controlla che il file scaricato non sia una preview da 30s.
    Ritorna (valido, messaggio_errore).
    Equivalente a ValidateDownloadedTrackDuration() del Go.
    """
    if not filepath or expected_seconds <= 0:
        return True, ""

    actual = _get_audio_duration(filepath)
    if actual <= 0:
        return True, ""

    actual_s = round(actual)

    # Case 1: 30s preview on a long track
    if expected_seconds >= _PREVIEW_EXPECTED_MIN and actual_s <= _PREVIEW_MAX_SECONDS:
        msg = (
            f"Preview detected: file is {actual_s}s, "
            f"expected ~{expected_seconds}s — file removed"
        )
        _remove_file(filepath)
        return False, msg

    # Case 2: large mismatch on long tracks
    if expected_seconds >= _LARGE_MISMATCH_MIN:
        allowed = max(_MIN_ALLOWED_DIFF, round(expected_seconds * _DURATION_DIFF_RATIO))
        diff = abs(actual_s - expected_seconds)
        if diff > allowed:
            msg = (
                f"Wrong duration: file is {actual_s}s, "
                f"expected ~{expected_seconds}s — file removed"
            )
            _remove_file(filepath)
            return False, msg

    return True, ""


def _remove_file(filepath: str) -> None:
    try:
        os.remove(filepath)
        logger.warning("[validation] File rimosso: %s", filepath)
    except OSError as exc:
        logger.warning("[validation] Impossibile rimuovere %s: %s", filepath, exc)
