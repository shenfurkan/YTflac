from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QFrame, QLabel, QListWidget, QListWidgetItem, QSizePolicy

from .. import style as S


def section_label(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setObjectName("section")
    return lbl


class ToggleList(QListWidget):
    _NAME_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, all_items: list[str], enabled: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("chips")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setSpacing(4)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        order = [s for s in enabled if s in all_items]
        for s in all_items:
            if s not in order:
                order.append(s)
        en_set = set(enabled)
        for name in order:
            self._add(name, name in en_set)
        self.itemClicked.connect(self._toggle)
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

    def _add(self, name: str, on: bool):
        it = QListWidgetItem(name)
        it.setData(self._NAME_ROLE, name)
        it.setData(Qt.ItemDataRole.UserRole, on)
        self._paint(it, on)
        self.addItem(it)

    def _toggle(self, it: QListWidgetItem):
        on = not bool(it.data(Qt.ItemDataRole.UserRole))
        it.setData(Qt.ItemDataRole.UserRole, on)
        self._paint(it, on)

    @staticmethod
    def _paint(it: QListWidgetItem, on: bool):
        from PyQt6.QtGui import QColor

        base_name = it.data(ToggleList._NAME_ROLE) or it.text().lstrip("✓ ").strip()
        it.setText(f"✓ {base_name}" if on else str(base_name))
        it.setForeground(QColor(S.TEXT if on else S.TEXT_FAINT))

    def enabled_ordered(self) -> list[str]:
        return [
            self.item(i).data(self._NAME_ROLE)
            for i in range(self.count())
            if bool(self.item(i).data(Qt.ItemDataRole.UserRole))
        ]
