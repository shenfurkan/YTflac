from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication, QMessageBox, QTextEdit
from PyQt6.QtCore import Qt
import os
import sys
from .. import style as S
from ...core.errors import classify_error, friendly_label, friendly_explanation, ErrorKind
from ...core.paths import app_log_path

class FailureDialog(QDialog):
    """Detailed per-track failure breakdown with copy + open-log actions."""

    def __init__(
        self, track_title: str, track_artist: str, raw_error: str, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Download Failed")
        self.setMinimumSize(560, 420)
        self._raw_error = raw_error

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 14)

        # Track header
        title_lbl = QLabel(f"<b>{track_title}</b>")
        title_lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(track_artist)
        sub_lbl.setObjectName("muted")
        layout.addWidget(sub_lbl)

        # Per-provider parsed table
        per_provider = self._parse_provider_errors(raw_error)
        if per_provider:
            providers_lbl = QLabel("Providers tried:")
            providers_lbl.setObjectName("section")
            layout.addWidget(providers_lbl)

            for prov, kind, detail in per_provider:
                badge_text = friendly_label(kind)
                explanation = friendly_explanation(kind)

                row = QFrame()
                row.setStyleSheet(
                    f"background: {S.BG_ELEV}; border-radius: 8px; "
                    f"border: 1px solid {S.LINE};"
                )
                rl = QVBoxLayout(row)
                rl.setContentsMargins(12, 10, 12, 10)
                rl.setSpacing(4)

                head = QHBoxLayout()
                head.setSpacing(8)
                prov_lbl = QLabel(f"<b>{prov}</b>")
                prov_lbl.setStyleSheet("font-size: 13px;")
                head.addWidget(prov_lbl)
                head.addStretch()
                kind_badge = QLabel(badge_text)
                kind_badge.setObjectName("badge_warn")
                head.addWidget(kind_badge)
                rl.addLayout(head)

                expl_lbl = QLabel(explanation)
                expl_lbl.setObjectName("muted")
                expl_lbl.setWordWrap(True)
                rl.addWidget(expl_lbl)

                detail_lbl = QLabel(detail)
                detail_lbl.setObjectName("faint")
                detail_lbl.setWordWrap(True)
                detail_lbl.setStyleSheet(f"color: {S.TEXT_DIM}; font-size: 11px;")
                detail_lbl.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                rl.addWidget(detail_lbl)

                layout.addWidget(row)
        else:
            # Fallback: just show the raw error
            raw_view = QTextEdit()
            raw_view.setReadOnly(True)
            raw_view.setPlainText(raw_error)
            raw_view.setMinimumHeight(150)
            layout.addWidget(raw_view)

        layout.addStretch(1)

        # Action row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        copy_btn = QPushButton("Copy details")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_box.addWidget(copy_btn)

        open_log_btn = QPushButton("Open failure log")
        open_log_btn.setObjectName("ghost")
        open_log_btn.clicked.connect(self._open_log)
        btn_box.addWidget(open_log_btn)

        btn_box.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)

    @staticmethod
    def _parse_provider_errors(raw: str) -> list[tuple[str, ErrorKind, str]]:
        """Parse 'All providers failed — tidal [KIND]: msg || qobuz [KIND]: msg' format."""
        if not raw:
            return []
        # Strip leading prefix (handles both em-dash and -- variants)
        body = raw
        for marker in (
            "All providers failed —",
            "All providers failed --",
            "All providers failed -",
        ):
            if marker in body:
                body = body.split(marker, 1)[1].strip()
                break

        out: list[tuple[str, ErrorKind, str]] = []
        # Split by '||' (new format) or fall back to '; '
        parts = body.split(" || ") if " || " in body else body.split("; ")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Format: "provider [KIND]: detail"  (preferred)
            #     or: "provider: detail"        (legacy)
            if ":" not in part:
                continue
            head, _, detail = part.partition(":")
            head = head.strip()
            detail = detail.strip()
            kind_name = ""
            prov = head
            if "[" in head and head.endswith("]"):
                prov, kind_part = head.split("[", 1)
                kind_name = kind_part.rstrip("]").strip()
                prov = prov.strip()
            kind = classify_error(f"{kind_name} {detail}".strip())
            out.append((prov, kind, detail))
        return out

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self._raw_error)

    def _open_log(self):
        log_path = str(app_log_path("ytflac_failures.log"))
        if not os.path.exists(log_path):
            QMessageBox.information(
                self,
                "No log yet",
                f"The failure log will be created here on the next failure:\n{log_path}",
            )
            return
        # Open with system default
        try:
            if sys.platform == "win32":
                os.startfile(log_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", log_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", log_path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open log file: {e}")
