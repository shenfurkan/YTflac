"""
Centralised output for user-facing messages (not logging).
Separates user-facing messages from debug loggers.
"""

from __future__ import annotations
import sys
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Fixed width for the source banner
_BANNER_WIDTH = 60


def print_track_header(
    position: int,
    total: int,
    title: str,
    artists: str,
    album: str,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    bar = "─" * _BANNER_WIDTH
    pos = f"[{position}/{total}]"
    header = f"{pos} {artists} — {title} [{album}]"
    print(f"\n┌{bar}┐")
    print(f"│ {pos} {artists[:40]!s:<40} │")
    print(f"│   ↳ {title[:50]!s:<50} │")
    print(f"│   ↳ {album[:50]!s:<50} │")
    print(f"└{bar}┘")
    if log_callback:
        log_callback(header, "info")


def print_source_banner(
    provider: str,
    api: str,
    quality: str,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    label = _shorten_api(api)
    line = f"  📡  {provider.upper()}  ·  {label}  ·  {quality}"
    print(f"{'─' * _BANNER_WIDTH}")
    print(f"{line}")
    print(f"{'─' * _BANNER_WIDTH}")
    if log_callback:
        log_callback(f"{provider}: found {quality}", "success")


def print_official_source(
    provider: str, quality: str, log_callback: Callable[[str, str], None] | None = None
) -> None:
    line = f"  💎  {provider.upper()}  ·  Official API  ·  {quality}"
    print(f"{'─' * _BANNER_WIDTH}")
    print(f"{line}")
    print(f"{'─' * _BANNER_WIDTH}")
    if log_callback:
        log_callback(f"{provider}: official API — {quality}", "success")


def print_summary(
    total: int,
    succeeded: int,
    failed: list[tuple[str, str, str]],
    elapsed_s: float,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    bar = "═" * _BANNER_WIDTH
    print(f"\n╔{bar}╗")
    print(f"║  📊 SESSION SUMMARY{'':<41}║")
    print(f"╠{bar}╣")
    print(f"║  Total tracks  : {total:<42}║")
    print(f"║  Completed     : {succeeded:<42}║")
    print(f"║  Failed        : {len(failed):<42}║")
    print(f"║  Elapsed time  : {_fmt_seconds(elapsed_s):<41}║")
    if failed:
        print(f"╠{bar}╣")
        print(f"║  ✗ FAILURES{'':<49}║")
        for title, artists, err in failed:
            short = f"{title[:22]} — {artists[:16]}: {err[:14]}"
            print(f"║    {short:<56}║")
    print(f"╚{bar}╝")
    if log_callback:
        log_callback(
            f"Finished — {succeeded} ok, {len(failed)} failed in {_fmt_seconds(elapsed_s)}",
            "info",
        )


def print_skip(
    filepath: str,
    size_mb: float,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    print(f"  ⏭  already exists  ·  {filepath[-45:]!s}  ({size_mb:.1f} MB)")
    if log_callback:
        log_callback(f"Skipped — already exists ({size_mb:.1f} MB)", "warning")


def print_api_failure(
    provider: str,
    api: str,
    reason: str,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    label = _shorten_api(api)
    print(f"  ✗  {provider}  ·  {label}  ·  {reason}", file=sys.stderr)
    if log_callback:
        log_callback(f"{provider} failed: {reason}", "error")


def print_quality_fallback(
    provider: str,
    from_q: str,
    to_q: str,
    log_callback: Callable[[str, str], None] | None = None,
) -> None:
    print(f"  ⬇  {provider}: quality {from_q} not available — fallback → {to_q}")
    if log_callback:
        log_callback(
            f"{provider}: {from_q} not available, falling back to {to_q}", "warning"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _shorten_api(url: str) -> str:
    """Return only the domain, without scheme or path."""
    return url.removeprefix("https://").removeprefix("http://").split("/")[0]


def _fmt_seconds(s: float) -> str:
    s = round(s)
    parts = []
    for unit, div in [("h", 3600), ("m", 60), ("s", 1)]:
        val, s = divmod(s, div)
        if val:
            parts.append(f"{val}{unit}")
    return " ".join(parts) or "0s"
