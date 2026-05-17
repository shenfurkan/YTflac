from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QPushButton,
    QLineEdit,
    QSizePolicy,
)

from .. import style as S

class ServicePriorityBar(QListWidget):
    """Drag-reorderable horizontal chip list. Click to toggle enabled/disabled."""
    changed = pyqtSignal()
    _NAME_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, services: list[str], enabled: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("chips")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setMovement(QListWidget.Movement.Snap)
        self.setSpacing(4)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        enabled_set = set(enabled if enabled is not None else services)
        for svc in services:
            self._add_chip(svc, svc in enabled_set)

        self.itemClicked.connect(self._toggle_item)
        self.model().rowsMoved.connect(lambda *_: self.changed.emit())
        self._update_height()

    def _update_height(self):
        """Compute and set height to show all chip rows without scrolling."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rows = 1
        x = 0
        for i in range(self.count()):
            item = self.item(i)
            w = self.sizeHintForIndex(self.indexFromItem(item)).width() + self.spacing()
            if x + w > self.contentsRect().width() and x > 0:
                rows += 1
                x = w
            else:
                x += w
        row_h = self.sizeHintForRow(0) if self.count() > 0 else 24
        h = rows * row_h + (rows - 1) * self.spacing() + self.contentsMargins().top() + self.contentsMargins().bottom() + 4
        self.setFixedHeight(max(h, row_h + 8))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_height()

    def _add_chip(self, name: str, on: bool):
        item = QListWidgetItem(name)
        item.setData(self._NAME_ROLE, name)
        item.setData(Qt.ItemDataRole.UserRole, on)
        self._apply_visual(item, on)
        self.addItem(item)

    def _toggle_item(self, item: QListWidgetItem):
        on = not bool(item.data(Qt.ItemDataRole.UserRole))
        item.setData(Qt.ItemDataRole.UserRole, on)
        self._apply_visual(item, on)
        self.changed.emit()

    @staticmethod
    def _apply_visual(item: QListWidgetItem, on: bool):
        base_name = item.data(ServicePriorityBar._NAME_ROLE) or item.text().lstrip("✓ ").strip()
        item.setText(f"✓ {base_name}" if on else str(base_name))
        if on:
            item.setForeground(QColor(S.TEXT))
        else:
            item.setForeground(QColor(S.TEXT_FAINT))

    def ordered_services(self) -> list[str]:
        return [self.item(i).data(self._NAME_ROLE) for i in range(self.count())]

    def enabled_services(self) -> list[str]:
        return [
            self.item(i).data(self._NAME_ROLE)
            for i in range(self.count())
            if bool(self.item(i).data(Qt.ItemDataRole.UserRole))
        ]


class UnmatchedPanel(QFrame):
    """Collapsible card listing YouTube tracks that could not be matched on Spotify."""
    manual_match = pyqtSignal(int, str)

    def __init__(self, unmatched: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("unmatchedPanel")
        self._expanded = False
        self._unmatched = list(unmatched)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        icon = QLabel("⚠")
        icon.setObjectName("warningIcon")
        icon.setFixedWidth(22)
        hdr.addWidget(icon)

        count_lbl = QLabel(
            f"{len(unmatched)} unmatched track{'s' if len(unmatched) != 1 else ''} need review"
        )
        count_lbl.setObjectName("unmatchedTitle")
        hdr.addWidget(count_lbl, stretch=1)

        self._toggle_btn = QPushButton("Show ▾")
        self._toggle_btn.setObjectName("ghost")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.clicked.connect(self._toggle)
        hdr.addWidget(self._toggle_btn)

        outer.addLayout(hdr)

        from PyQt6.QtWidgets import QScrollArea
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMaximumHeight(280)
        self._scroll.setObjectName("unmatchedScroll")

        self._list_widget = QFrame()
        self._list_widget.setObjectName("unmatchedList")
        list_layout = QVBoxLayout(self._list_widget)
        list_layout.setContentsMargins(12, 10, 12, 10)
        list_layout.setSpacing(6)

        self._row_widgets: list[QFrame] = []
        for i, title in enumerate(unmatched):
            row_frame = QFrame()
            row_frame.setObjectName("unmatchedRow")
            row_frame.setFixedHeight(36)
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(10, 4, 8, 4)
            row_layout.setSpacing(8)

            idx_lbl = QLabel(f"{i + 1:02d}")
            idx_lbl.setFixedWidth(26)
            idx_lbl.setObjectName("unmatchedIndex")
            row_layout.addWidget(idx_lbl)

            lbl = QLabel(title)
            lbl.setObjectName("unmatchedText")
            lbl.setWordWrap(False)
            lbl.setToolTip(title)
            row_layout.addWidget(lbl, stretch=1)

            fix_btn = QPushButton("Fix")
            fix_btn.setObjectName("ghost")
            fix_btn.setFixedSize(48, 24)
            fix_btn.setToolTip("Manually provide a Spotify URL for this track")
            fix_btn.clicked.connect(lambda _c=False, idx=i: self._on_fix(idx))
            row_layout.addWidget(fix_btn)

            list_layout.addWidget(row_frame)
            self._row_widgets.append(row_frame)

        self._scroll.setWidget(self._list_widget)
        self._scroll.setVisible(False)
        outer.addWidget(self._scroll)

    def _toggle(self):
        self._expanded = not self._expanded
        self._scroll.setVisible(self._expanded)
        self._toggle_btn.setText("Hide ▴" if self._expanded else "Show ▾")

    def _on_fix(self, idx: int):
        from PyQt6.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(
            self,
            "Fix Unmatched Track",
            f"Paste a Spotify track URL for:\n\n  {self._unmatched[idx]}\n",
            QLineEdit.EchoMode.Normal,
        )
        if ok and url and url.strip():
            self.manual_match.emit(idx, url.strip())

    def mark_fixed(self, idx: int, new_title: str = ""):
        if 0 <= idx < len(self._row_widgets):
            row = self._row_widgets[idx]
            row.setProperty("fixed", True)
            row.style().unpolish(row)
            row.style().polish(row)
            layout = row.layout()
            fix_btn = layout.itemAt(layout.count() - 1).widget()
            if fix_btn:
                fix_btn.setText("✓")
                fix_btn.setEnabled(False)
