from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt


@dataclass
class TrackItemState:
    checked: bool = True
    status: str = "idle"
    progress: int = 0
    error: str = ""


class TrackListRoles:
    TrackRole = Qt.ItemDataRole.UserRole + 1
    IndexRole = Qt.ItemDataRole.UserRole + 2
    CheckedRole = Qt.ItemDataRole.UserRole + 3
    StatusRole = Qt.ItemDataRole.UserRole + 4
    ProgressRole = Qt.ItemDataRole.UserRole + 5
    ErrorRole = Qt.ItemDataRole.UserRole + 6
    SearchBlobRole = Qt.ItemDataRole.UserRole + 7


class TrackListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[object] = []
        self._states: list[TrackItemState] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._tracks)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._tracks):
            return None
        track = self._tracks[row]
        state = self._states[row]

        if role == Qt.ItemDataRole.DisplayRole:
            title = getattr(track, "title", "")
            artists = getattr(track, "artists", "") or getattr(track, "artist", "")
            return f"{title} — {artists}" if artists else title
        if role == TrackListRoles.TrackRole:
            return track
        if role == TrackListRoles.IndexRole:
            return row
        if role == TrackListRoles.CheckedRole:
            return state.checked
        if role == TrackListRoles.StatusRole:
            return state.status
        if role == TrackListRoles.ProgressRole:
            return state.progress
        if role == TrackListRoles.ErrorRole:
            return state.error
        if role == TrackListRoles.SearchBlobRole:
            return " ".join(
                [
                    getattr(track, "title", "") or "",
                    getattr(track, "artists", "") or getattr(track, "artist", "") or "",
                    getattr(track, "album", "") or "",
                ]
            ).lower()
        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        row = index.row()
        if row < 0 or row >= len(self._tracks):
            return False
        state = self._states[row]
        changed = False

        if role == TrackListRoles.CheckedRole:
            new_val = bool(value)
            if state.checked != new_val:
                state.checked = new_val
                changed = True
        elif role == TrackListRoles.StatusRole:
            new_val = str(value)
            if state.status != new_val:
                state.status = new_val
                changed = True
        elif role == TrackListRoles.ProgressRole:
            new_val = max(0, min(100, int(value)))
            if state.progress != new_val:
                state.progress = new_val
                changed = True
        elif role == TrackListRoles.ErrorRole:
            new_val = str(value or "")
            if state.error != new_val:
                state.error = new_val
                changed = True

        if changed:
            self.dataChanged.emit(index, index, [role])
        return changed

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def reset_tracks(self, tracks: list[object]) -> None:
        self.beginResetModel()
        self._tracks = list(tracks)
        self._states = [TrackItemState() for _ in self._tracks]
        self.endResetModel()

    def clear(self) -> None:
        self.reset_tracks([])

    def append_track(self, track: object, checked: bool = True) -> int:
        row = len(self._tracks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tracks.append(track)
        self._states.append(TrackItemState(checked=bool(checked)))
        self.endInsertRows()
        return row

    def set_row_checked(self, row: int, checked: bool) -> bool:
        if row < 0 or row >= len(self._tracks):
            return False
        idx = self.index(row)
        return self.setData(idx, checked, TrackListRoles.CheckedRole)

    def is_row_checked(self, row: int) -> bool:
        if row < 0 or row >= len(self._tracks):
            return False
        return self._states[row].checked

    def set_row_status(self, row: int, status: str, error: str = "") -> bool:
        if row < 0 or row >= len(self._tracks):
            return False
        idx = self.index(row)
        changed = self.setData(idx, status, TrackListRoles.StatusRole)
        if status != "failed" and error:
            error = ""
        changed = self.setData(idx, error, TrackListRoles.ErrorRole) or changed
        if status != "running":
            changed = self.setData(idx, 0, TrackListRoles.ProgressRole) or changed
        return changed

    def set_row_progress(self, row: int, progress: int) -> bool:
        if row < 0 or row >= len(self._tracks):
            return False
        idx = self.index(row)
        return self.setData(idx, progress, TrackListRoles.ProgressRole)

    def row_error(self, row: int) -> str:
        if row < 0 or row >= len(self._tracks):
            return ""
        return self._states[row].error

    def track_at(self, row: int):
        if row < 0 or row >= len(self._tracks):
            return None
        return self._tracks[row]

    def checked_rows(self) -> set[int]:
        return {i for i, state in enumerate(self._states) if state.checked}
