from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
from PyQt6.QtCore import Qt
from .. import style as S
from ..components import TickCheckBox

class LowConfidenceDialog(QDialog):
    """
    Pre-download dialog shown when one or more tracks have a low Spotify
    match confidence. Lets the user review and deselect suspicious tracks
    before confirming the download.
    """

    def __init__(self, suspicious: list[tuple[int, object]], parent=None):
        """
        suspicious: list of (row_index_0based, TrackMetadata) for tracks with
                    match_confidence < 60.
        """
        super().__init__(parent)
        self.setWindowTitle("Review Low-Confidence Matches")
        self.setMinimumSize(560, 380)
        self._deselect: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        # Header
        hdr_lbl = QLabel(
            f"⚠  {len(suspicious)} track{'s' if len(suspicious) != 1 else ''} "
            "may have been matched incorrectly."
        )
        hdr_lbl.setStyleSheet(
            f"color: {S.WARNING}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        hdr_lbl.setWordWrap(True)
        layout.addWidget(hdr_lbl)

        sub = QLabel(
            "These YouTube tracks had a low Spotify match score. "
            "Uncheck any tracks you want to skip."
        )
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Track list
        from PyQt6.QtWidgets import QWidget as _W
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = _W()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        self._checks: list[tuple[int, TickCheckBox]] = []
        for idx, track in suspicious:
            confidence = getattr(track, "match_confidence", 0)
            cb = TickCheckBox(
                f"{track.title}  ·  {track.artists}"
                f"    —  {confidence}% confidence"
            )
            cb.setChecked(True)  # checked = include in download
            cb.setStyleSheet(f"color: {S.TEXT}; font-size: 12px;")
            inner_layout.addWidget(cb)
            self._checks.append((idx, cb))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        skip_all_btn = QPushButton("Skip all flagged")
        skip_all_btn.setObjectName("ghost")
        skip_all_btn.clicked.connect(self._uncheck_all)
        btn_row.addWidget(skip_all_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel download")
        cancel_btn.setObjectName("ghost")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        continue_btn = QPushButton("Download selected")
        continue_btn.setObjectName("primary")
        continue_btn.clicked.connect(self._accept)
        btn_row.addWidget(continue_btn)

        layout.addLayout(btn_row)

    def _uncheck_all(self):
        for _, cb in self._checks:
            cb.setChecked(False)

    def _accept(self):
        self._deselect = {idx for idx, cb in self._checks if not cb.isChecked()}
        self.accept()

    def deselected_indices(self) -> set[int]:
        """Return 0-based indices of tracks the user chose to skip."""
        return self._deselect


