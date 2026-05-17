import json
import time
from pathlib import Path


class HistoryManager:
    """Manages download history (successes + failures) for smart re-import."""

    def __init__(self):
        self.path = Path.home() / ".cache" / "spotiflac" / "download-history.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def add_download(
        self,
        *,
        track_id: str,
        track_name: str,
        artist_name: str,
        provider: str,
        success: bool,
        file_path: str,
    ) -> None:
        history = self.get_all()
        # Remove previous entry for this track (deduplicate)
        history = [h for h in history if h.get("id") != track_id]

        entry = {
            "id": track_id,
            "track_name": track_name,
            "artist_name": artist_name,
            "provider": provider,
            "success": success,
            "file_path": file_path,
            "downloaded_at": int(time.time()),
        }
        history.insert(0, entry)

        # Keep last 5000 entries
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(history[:5000], f, indent=2)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_downloaded_ids(self) -> set[str]:
        """Return IDs of successfully downloaded tracks."""
        return {h["id"] for h in self.get_all() if h.get("success") and "id" in h}

    def get_failed_ids(self) -> set[str]:
        """Return IDs of tracks that failed on every attempt."""
        all_entries = self.get_all()
        # A track is "failed" if its latest entry has success=False
        seen: dict[str, bool] = {}
        for h in all_entries:
            tid = h.get("id")
            if tid and tid not in seen:
                seen[tid] = h.get("success", False)
        return {tid for tid, ok in seen.items() if not ok}

    def get_stats(self) -> dict:
        """Return summary stats."""
        history = self.get_all()
        succeeded = sum(1 for h in history if h.get("success"))
        failed = sum(1 for h in history if not h.get("success"))
        return {
            "total": len(history),
            "succeeded": succeeded,
            "failed": failed,
        }
