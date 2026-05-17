"""
YouTube Music HTML parsing helpers — pure string/JSON extraction,
no HTTP calls.  Extracted from ``youtube_input.py`` to keep file sizes
manageable.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_PLAYLIST_VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
_WATCH_ENDPOINT_VIDEO_ID_RE = re.compile(
    r'"watchEndpoint":\{"videoId":"([A-Za-z0-9_-]{11})"'
)
_VIDEO_ID_PATTERN = re.compile(r"([A-Za-z0-9_-]{11})")
_HEX_ESCAPE_RE = re.compile(r"\\x([0-9A-Fa-f]{2})")
_YT_INITIAL_DATA_MARKERS = (
    "var ytInitialData = ",
    "window['ytInitialData'] = ",
    'window["ytInitialData"] = ',
    "ytInitialData = ",
)
_HTML_TITLE_RE = re.compile(r"(?is)<title>(.*?)</title>")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def parse_playlist_title(raw_html: str) -> str:
    m = _HTML_TITLE_RE.search(raw_html)
    if not m:
        return "YouTube Music Playlist"
    title = html_mod.unescape(m.group(1)).strip()
    title = title.removesuffix(" - YouTube Music").removesuffix(" - YouTube").strip()
    return title or "YouTube Music Playlist"


def parse_playlist_video_ids(
    raw_html: str, max_count: int = 0
) -> list[str]:
    raw_html = _decode_js_hex_escapes(raw_html)
    seen: set[str] = set()
    result: list[str] = []

    # Try regex patterns first
    matches = _PLAYLIST_VIDEO_ID_RE.findall(raw_html)
    matches.extend(_WATCH_ENDPOINT_VIDEO_ID_RE.findall(raw_html))

    for vid in matches:
        vid = vid.strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        result.append(vid)
        if max_count and len(result) >= max_count:
            break

    # If regex didn't get enough, try JSON parsing
    if not result or (max_count and len(result) < max_count):
        data = _extract_yt_initial_data(raw_html)
        if data:
            for vid in _collect_video_ids_from_json(data):
                if vid in seen:
                    continue
                seen.add(vid)
                result.append(vid)
                if max_count and len(result) >= max_count:
                    break

    # Fallback: try to extract all 11-char video IDs from the entire HTML
    if not result or (max_count and len(result) < max_count):
        all_ids = _VIDEO_ID_PATTERN.findall(raw_html)
        for vid in all_ids:
            vid = vid.strip()
            if (
                len(vid) == 11
                and vid.replace("_", "").replace("-", "").isalnum()
                and vid not in seen
            ):
                seen.add(vid)
                result.append(vid)
                if max_count and len(result) >= max_count:
                    break

    return result


def extract_continuation_token(raw_html: str) -> str | None:
    """Extract continuation token from YouTube Music HTML."""
    patterns = [
        r'"continuation":"([^"]+)"',
        r'"ctoken":"([^"]+)"',
        r'"continuationCommand":\{"token":"([^"]+)"',
        r'"nextContinuationData":\{"continuation":"([^"]+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, raw_html)
        if matches:
            return matches[-1]

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _decode_js_hex_escapes(text: str) -> str:
    if "\\x" not in text:
        return text
    return _HEX_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def _extract_yt_initial_data(raw_html: str) -> dict | list | None:
    for marker in _YT_INITIAL_DATA_MARKERS:
        start = raw_html.find(marker)
        if start < 0:
            continue
        start = raw_html.find("{", start)
        if start < 0:
            continue
        blob = _extract_balanced_json(raw_html, start)
        if not blob:
            continue
        try:
            return json.loads(blob)
        except Exception as exc:
            logger.debug("[youtube_input] Failed to parse ytInitialData: %s", exc)
    return None


def _extract_balanced_json(text: str, start: int) -> str:
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def _collect_video_ids_from_json(data) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    def _walk(node):
        if isinstance(node, dict):
            vid = node.get("videoId")
            if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                seen.add(vid)
                result.append(vid)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return result
