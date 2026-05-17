from .errors import (
    SpotiflacError,
    ErrorKind,
    AuthError,
    TrackNotFoundError,
    RateLimitedError,
    NetworkError,
    ParseError,
    InvalidUrlError,
)
from .models import TrackMetadata, DownloadResult, build_filename, sanitize
from .http import HttpClient, RetryConfig
from .tagger import embed_metadata, max_resolution_spotify_cover
from .progress import DownloadManager, ProgressCallback, RichProgressCallback

__all__ = [
    "AuthError",
    "DownloadManager",
    "DownloadResult",
    "ErrorKind",
    "HttpClient",
    "InvalidUrlError",
    "NetworkError",
    "ParseError",
    "ProgressCallback",
    "RateLimitedError",
    "RetryConfig",
    "RichProgressCallback",
    "SpotiflacError",
    "TrackMetadata",
    "TrackNotFoundError",
    "build_filename",
    "embed_metadata",
    "max_resolution_spotify_cover",
    "prioritize_providers",
    "record_failure",
    "record_success",
    "sanitize",
]
from .provider_stats import (
    record_success,
    record_failure,
    prioritize as prioritize_providers,
)
