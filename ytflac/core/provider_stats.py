"""
Sistema di scoring per le API dei provider.
Porta il pattern Go prioritizeProviders/recordProviderSuccess/Failure.

Le API che falliscono vengono messe in fondo alla lista automaticamente,
quelle che funzionano vengono promosse in cima — senza shuffle casuale.
"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field

from .errors import ErrorKind


@dataclass
class _ProviderStats:
    successes:    int   = 0
    failures:     int   = 0
    last_success: float = 0.0
    last_failure: float = 0.0

    def score(self) -> float:
        """
        Score più alto = API migliore = va in cima alla lista.
        Formula ispirata al Go: premia successi recenti, penalizza fallimenti recenti.
        Un fallimento nelle ultime 5 minuti abbassa drasticamente lo score.
        """
        base = self.successes - (self.failures * 2)
        now  = time.time()

        # Penalità temporale per fallimenti recenti (5 minuti)
        if self.last_failure > 0 and (now - self.last_failure) < 300:
            base -= 10

        # Bonus per successo recente (5 minuti)
        if self.last_success > 0 and (now - self.last_success) < 300:
            base += 5

        return float(base)


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    opened_until: float = 0.0
    last_kind: ErrorKind | None = None


class ProviderScorer:
    """
    Singleton thread-safe che traccia successi/fallimenti per API URL.
    Equivalente a recordProviderSuccess/recordProviderFailure del Go.
    """
    _instance: "ProviderScorer | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ProviderScorer":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._stats: dict[str, _ProviderStats] = {}
                inst._stats_lock = threading.Lock()
                inst._circuit: dict[str, _CircuitState] = {}
                cls._instance = inst
        return cls._instance

    def record_success(self, provider_type: str, api_url: str) -> None:
        key = f"{provider_type}:{api_url}"
        with self._stats_lock:
            s = self._stats.setdefault(key, _ProviderStats())
            s.successes    += 1
            s.last_success  = time.time()

    def record_failure(self, provider_type: str, api_url: str) -> None:
        key = f"{provider_type}:{api_url}"
        with self._stats_lock:
            s = self._stats.setdefault(key, _ProviderStats())
            s.failures    += 1
            s.last_failure = time.time()

    def prioritize(self, provider_type: str, api_urls: list[str]) -> list[str]:
        """
        Ritorna la lista di API ordinata per score decrescente.
        API senza storia mantengono l'ordine originale (score = 0).
        Equivalente a prioritizeProviders() del Go.
        """
        with self._stats_lock:
            def _score(url: str) -> float:
                key = f"{provider_type}:{url}"
                s   = self._stats.get(key)
                return s.score() if s else 0.0

            # sort stabile: a parità di score mantiene ordine originale
            return sorted(api_urls, key=_score, reverse=True)

    def reset(self) -> None:
        """Utile per i test."""
        with self._stats_lock:
            self._stats.clear()
            self._circuit.clear()

    # ------------------------------------------------------------------
    # Provider-level circuit breaker (across tracks)
    # ------------------------------------------------------------------

    def record_provider_success(self, provider_type: str) -> None:
        with self._stats_lock:
            c = self._circuit.setdefault(provider_type, _CircuitState())
            c.consecutive_failures = 0
            c.opened_until = 0.0
            c.last_kind = None

    def record_provider_failure(self, provider_type: str, kind: ErrorKind) -> None:
        now = time.time()
        with self._stats_lock:
            c = self._circuit.setdefault(provider_type, _CircuitState())
            c.last_kind = kind
            c.consecutive_failures += 1

            # Immediate opens for clearly non-transient failures
            if kind == ErrorKind.AUTH_FAILED:
                c.opened_until = max(c.opened_until, now + 300)  # 5 min
                return
            if kind == ErrorKind.RATE_LIMITED:
                c.opened_until = max(c.opened_until, now + 120)  # 2 min
                return

            # Network/unavailable failures: open only after repeated failures
            if kind in {ErrorKind.NETWORK_ERROR, ErrorKind.UNAVAILABLE} and c.consecutive_failures >= 3:
                c.opened_until = max(c.opened_until, now + 90)  # 1.5 min
                return

            # Parsing failures tend to be persistent until update
            if kind == ErrorKind.PARSE_ERROR and c.consecutive_failures >= 2:
                c.opened_until = max(c.opened_until, now + 180)  # 3 min

    def provider_cooldown_remaining(self, provider_type: str) -> int:
        with self._stats_lock:
            c = self._circuit.get(provider_type)
            if not c:
                return 0
            remaining = int(c.opened_until - time.time())
            return remaining if remaining > 0 else 0

    def is_provider_open(self, provider_type: str) -> bool:
        return self.provider_cooldown_remaining(provider_type) <= 0


# Singleton globale — usato dai provider
_scorer = ProviderScorer()


def record_success(provider_type: str, api_url: str) -> None:
    _scorer.record_success(provider_type, api_url)


def record_failure(provider_type: str, api_url: str) -> None:
    _scorer.record_failure(provider_type, api_url)


def prioritize(provider_type: str, api_urls: list[str]) -> list[str]:
    return _scorer.prioritize(provider_type, api_urls)


def record_provider_success(provider_type: str) -> None:
    _scorer.record_provider_success(provider_type)


def record_provider_failure(provider_type: str, kind: ErrorKind) -> None:
    _scorer.record_provider_failure(provider_type, kind)


def provider_cooldown_remaining(provider_type: str) -> int:
    return _scorer.provider_cooldown_remaining(provider_type)


def is_provider_open(provider_type: str) -> bool:
    return _scorer.is_provider_open(provider_type)

# Alias per compatibilità con i provider
prioritize_providers = prioritize
