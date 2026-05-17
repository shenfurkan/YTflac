"""
Gerarchia di errori tipati per SpotiFLAC.
Ispirato al pattern Go: sentinel errors + errors.As/Is.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto

import re as _re


class ErrorKind(Enum):
    AUTH_FAILED = auto()
    TRACK_NOT_FOUND = auto()
    RATE_LIMITED = auto()
    NETWORK_ERROR = auto()
    PARSE_ERROR = auto()
    UNAVAILABLE = auto()
    FILE_IO = auto()
    INVALID_URL = auto()
    METADATA_ERROR = auto()


@dataclass
class SpotiflacError(Exception):
    kind: ErrorKind
    message: str
    provider: str = ""
    cause: BaseException | None = field(default=None, repr=False)

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        cause_str = f" (caused by: {self.cause})" if self.cause else ""
        return f"{prefix}{self.kind.name}: {self.message}{cause_str}"

    def is_retryable(self) -> bool:
        return self.kind in {ErrorKind.RATE_LIMITED, ErrorKind.NETWORK_ERROR}


class AuthError(SpotiflacError):
    def __init__(self, provider: str, msg: str, cause: BaseException | None = None):
        super().__init__(ErrorKind.AUTH_FAILED, msg, provider, cause)


class TrackNotFoundError(SpotiflacError):
    def __init__(self, provider: str, identifier: str):
        super().__init__(
            ErrorKind.TRACK_NOT_FOUND,
            f"Track not found for: {identifier}",
            provider,
        )


class RateLimitedError(SpotiflacError):
    def __init__(self, provider: str, retry_after: int = 5):
        super().__init__(
            ErrorKind.RATE_LIMITED,
            f"Rate limited — retry after {retry_after}s",
            provider,
        )
        self.retry_after = retry_after


class NetworkError(SpotiflacError):
    def __init__(self, provider: str, msg: str, cause: BaseException | None = None):
        super().__init__(ErrorKind.NETWORK_ERROR, msg, provider, cause)


class ParseError(SpotiflacError):
    def __init__(self, provider: str, msg: str, cause: BaseException | None = None):
        super().__init__(ErrorKind.PARSE_ERROR, msg, provider, cause)


class InvalidUrlError(SpotiflacError):
    def __init__(self, url: str):
        super().__init__(ErrorKind.INVALID_URL, f"Unsupported or invalid URL: {url}")


# ---------------------------------------------------------------------------
# Friendly error helpers (used by GUI to show actionable messages)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
_KIND_LABELS: dict[ErrorKind, tuple[str, str]] = {
    # ErrorKind                : (short label, friendly explanation)
    ErrorKind.AUTH_FAILED: (
        "Authentication failed",
        "The provider rejected the credentials or a session token expired. "
        "Try again later or restart the app.",
    ),
    ErrorKind.TRACK_NOT_FOUND: (
        "Track not found",
        "This provider does not have this track in its catalog. "
        "Try enabling more services in Settings.",
    ),
    ErrorKind.RATE_LIMITED: (
        "Rate limited",
        "The provider is throttling requests. "
        "Increase the cooldown duration in Settings or wait a few minutes.",
    ),
    ErrorKind.NETWORK_ERROR: (
        "Network error",
        "A request to the provider failed. Check your internet "
        "connection / VPN and try again.",
    ),
    ErrorKind.PARSE_ERROR: (
        "Provider response changed",
        "The provider's API format changed and we could not parse it. "
        "An app update may be required.",
    ),
    ErrorKind.UNAVAILABLE: (
        "Track unavailable",
        "The track exists but cannot be downloaded right now (region lock, "
        "removed, or DRM-only).",
    ),
    ErrorKind.FILE_IO: (
        "File system error",
        "Could not write the file. Check the output folder permissions or free disk space.",
    ),
    ErrorKind.INVALID_URL: ("Invalid URL", "The URL format is not supported."),
    ErrorKind.METADATA_ERROR: ("Metadata error", "Could not read or write track tags."),
}

_RAW_PATTERNS: list[tuple[ErrorKind, _re.Pattern[str]]] = [
    (
        ErrorKind.AUTH_FAILED,
        _re.compile(
            r"\b(401|403|forbidden|unauthor|auth.?fail|invalid.?token)\b", _re.I
        ),
    ),
    (
        ErrorKind.RATE_LIMITED,
        _re.compile(r"\b(429|rate.?limit|too.?many|retry.?after)\b", _re.I),
    ),
    (
        ErrorKind.TRACK_NOT_FOUND,
        _re.compile(r"\b(404|not.?found|no.?match|isrc.?missing)\b", _re.I),
    ),
    (
        ErrorKind.NETWORK_ERROR,
        _re.compile(
            r"\b(timeout|timed.?out|connection|connect.?reset|"
            r"connection.?aborted|getaddrinfo|name.?resolution|ssl|"
            r"5\d\d|bad.?gateway|service.?unavailable|gateway.?timeout)\b",
            _re.I,
        ),
    ),
    (
        ErrorKind.UNAVAILABLE,
        _re.compile(r"\b(unavailable|geo.?block|region|drm|premium.?only)\b", _re.I),
    ),
    (
        ErrorKind.FILE_IO,
        _re.compile(
            r"\b(no.?space|permission.?denied|disk.?full|file.?exists|"
            r"errno|oserror)\b",
            _re.I,
        ),
    ),
    (
        ErrorKind.PARSE_ERROR,
        _re.compile(r"\b(json|parse|decode|unexpected.?response|malformed)\b", _re.I),
    ),
    (
        ErrorKind.METADATA_ERROR,
        _re.compile(r"\b(mutagen|tag|id3|metadata|cover.?art)\b", _re.I),
    ),
]


def classify_error(message: str) -> ErrorKind:
    """Best-effort categorization of a free-form error string."""
    if not message:
        return ErrorKind.UNAVAILABLE
    # Fast path: typed error already includes the kind name
    for kind in ErrorKind:
        if kind.name in message:
            return kind
    # Heuristic match
    for kind, pat in _RAW_PATTERNS:
        if pat.search(message):
            return kind
    return ErrorKind.UNAVAILABLE


def friendly_label(kind: ErrorKind) -> str:
    return _KIND_LABELS.get(kind, ("Unknown error", ""))[0]


def friendly_explanation(kind: ErrorKind) -> str:
    return _KIND_LABELS.get(
        kind, ("Unknown error", "An unrecognised error occurred. See the debug log.")
    )[1]


def summarize_failures(per_provider_errors: dict[str, str]) -> dict[ErrorKind, int]:
    """Group provider error strings by kind, returning counts."""
    out: dict[ErrorKind, int] = {}
    for msg in per_provider_errors.values():
        k = classify_error(msg)
        out[k] = out.get(k, 0) + 1
    return out
