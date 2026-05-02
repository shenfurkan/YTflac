"""
In-memory job manager for SpotiFLAC download sessions.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobState(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class JobInfo:
    id: str
    state: JobState = JobState.PENDING
    current: int = 0
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    _listeners: list[Any] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state.value,
            "current": self.current,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "errors": self.errors,
        }

    def push_event(self, event: dict) -> None:
        with self._lock:
            for q in self._listeners:
                q.put_nowait(event)

    def add_listener(self, q) -> None:
        with self._lock:
            self._listeners.append(q)

    def remove_listener(self, q) -> None:
        with self._lock:
            try:
                self._listeners.remove(q)
            except ValueError:
                pass


class JobManager:
    """Thread-safe registry of download jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.Lock()

    def create(self, total: int = 0) -> JobInfo:
        job_id = uuid.uuid4().hex[:12]
        job = JobInfo(id=job_id, total=total)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[JobInfo]:
        with self._lock:
            return list(self._jobs.values())
