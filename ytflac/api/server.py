"""
Thin FastAPI bridge exposing preview / download / progress for the MUI frontend.
Run with:  uvicorn SpotiFLAC.api.server:app --reload --port 8787
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
from queue import Queue, Empty

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..providers.spotify_metadata import SpotifyMetadataClient
from ..providers.youtube_input import is_youtube_url, resolve_youtube_input
from ..downloader import DownloadOptions, DownloadWorker
from ..core.models import TrackMetadata
from .jobs import JobManager, JobState
from ..system_awake import keep_awake

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="SpotiFLAC API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_spotify = SpotifyMetadataClient()
_jobs = JobManager()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PreviewRequest(BaseModel):
    url: str


class PreviewTrack(BaseModel):
    id: str
    title: str
    artist: str
    album: str
    cover: str
    duration_ms: int
    source: str = "spotify"


class PreviewResponse(BaseModel):
    type: str
    name: str
    cover: str
    tracks: list[PreviewTrack]
    unmatched: list[str] = []


class DownloadRequest(BaseModel):
    url: str
    output_dir: str = "./downloads"
    services: list[str] = ["tidal"]
    filename_format: str = "{title} - {artist}"
    quality: str = "LOSSLESS"


class DownloadResponse(BaseModel):
    job_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/preview", response_model=PreviewResponse)
def preview(req: PreviewRequest):
    """Resolve a URL (Spotify or YouTube) and return track list with thumbnails."""
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "url is required")

    unmatched: list[str] = []
    tracks: list[TrackMetadata] = []
    collection_name = ""
    coll_type = "track"
    source = "spotify"

    if is_youtube_url(url):
        source = "youtube"
        try:
            result = resolve_youtube_input(url, _spotify)
            collection_name = result.collection_name
            tracks = result.tracks
            unmatched = result.unmatched_samples
            coll_type = "playlist" if result.is_playlist else "track"
        except Exception as exc:
            raise HTTPException(422, str(exc))
    else:
        try:
            collection_name, tracks = _spotify.get_url(url)
        except Exception as exc:
            raise HTTPException(422, str(exc))
        if len(tracks) > 1:
            coll_type = "playlist"

    cover = tracks[0].cover_url if tracks else ""

    return PreviewResponse(
        type=coll_type,
        name=collection_name,
        cover=cover,
        tracks=[
            PreviewTrack(
                id=t.id,
                title=t.title,
                artist=t.artists,
                album=t.album,
                cover=t.cover_url,
                duration_ms=t.duration_ms,
                source=source,
            )
            for t in tracks
        ],
        unmatched=unmatched,
    )


@app.post("/api/download", response_model=DownloadResponse)
def start_download(req: DownloadRequest):
    """Start a background download job."""
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "url is required")

    # Resolve tracks
    tracks: list[TrackMetadata] = []
    collection_name = ""
    is_playlist = False

    if is_youtube_url(url):
        try:
            result = resolve_youtube_input(url, _spotify)
            collection_name = result.collection_name
            tracks = result.tracks
            is_playlist = result.is_playlist
        except Exception as exc:
            raise HTTPException(422, str(exc))
    else:
        try:
            collection_name, tracks = _spotify.get_url(url)
        except Exception as exc:
            raise HTTPException(422, str(exc))
        is_playlist = len(tracks) > 1

    if not tracks:
        raise HTTPException(422, "No tracks found")

    # Create job
    job = _jobs.create(total=len(tracks))
    job.state = JobState.RUNNING

    opts = DownloadOptions(
        output_dir=req.output_dir,
        services=req.services,
        filename_format=req.filename_format,
        quality=req.quality,
    )

    def _run():
        try:
            worker = DownloadWorker(
                tracks=tracks,
                opts=opts,
                collection_name=collection_name,
                is_playlist=is_playlist,
            )
            keep_awake_enabled = is_playlist or len(tracks) > 1
            with keep_awake(display=True) if keep_awake_enabled else contextlib.nullcontext():
                failed = worker.run()
            job.succeeded = len(tracks) - len(failed)
            job.failed = len(failed)
            job.errors = [
                {"title": t, "artist": a, "error": e}
                for t, a, e in failed
            ]
            job.current = len(tracks)
            job.state = JobState.COMPLETED
            job.push_event({"event": "done", "data": job.to_dict()})
        except Exception as exc:
            logger.exception("Job %s crashed", job.id)
            job.state = JobState.FAILED
            job.errors.append({"title": "", "artist": "", "error": str(exc)})
            job.push_event({"event": "error", "data": job.to_dict()})

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return DownloadResponse(job_id=job.id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """SSE stream for real-time job progress."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    q: Queue = Queue()
    job.add_listener(q)

    async def event_generator():
        try:
            while True:
                try:
                    event = q.get_nowait()
                except Empty:
                    await asyncio.sleep(0.5)
                    # Send heartbeat
                    yield {"event": "ping", "data": ""}
                    continue
                yield event
                if event.get("event") in ("done", "error"):
                    break
        finally:
            job.remove_listener(q)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Serve static UI in production
# ---------------------------------------------------------------------------

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
