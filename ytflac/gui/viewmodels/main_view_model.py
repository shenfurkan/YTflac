from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import QObject, pyqtSignal


class _ObservableSelectionSet(set):
    def __init__(self, notify_change, iterable=()):
        super().__init__(iterable)
        self._notify_change = notify_change

    def add(self, element):
        if element not in self:
            super().add(element)
            self._notify_change()

    def discard(self, element):
        if element in self:
            super().discard(element)
            self._notify_change()

    def clear(self):
        if self:
            super().clear()
            self._notify_change()

    def update(self, *others):
        before = len(self)
        super().update(*others)
        if len(self) != before:
            self._notify_change()

    def remove(self, element):
        super().remove(element)
        self._notify_change()

    def pop(self):
        value = super().pop()
        self._notify_change()
        return value


class MainViewModel(QObject):
    selectionChanged = pyqtSignal(int)
    downloadStateChanged = pyqtSignal(bool)
    resultChanged = pyqtSignal(object)
    filterChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_batch_depth = 0
        self._selection_dirty = False
        self._selected_indices = _ObservableSelectionSet(self._on_selection_mutated)
        self._is_downloading = False
        self._result = None
        self._filter_text = ""

    @property
    def selected_indices(self) -> set[int]:
        return self._selected_indices

    @property
    def is_downloading(self) -> bool:
        return self._is_downloading

    @property
    def result(self):
        return self._result

    @property
    def filter_text(self) -> str:
        return self._filter_text

    def set_is_downloading(self, busy: bool) -> None:
        busy = bool(busy)
        if self._is_downloading == busy:
            return
        self._is_downloading = busy
        self.downloadStateChanged.emit(busy)

    def set_selected_indices(self, indices: set[int] | list[int]) -> None:
        target = set(indices)
        if target == set(self._selected_indices):
            return
        with self.selection_batch():
            self._selected_indices.clear()
            self._selected_indices.update(target)

    def set_result(self, result) -> None:
        if self._result is result:
            return
        self._result = result
        self.resultChanged.emit(result)

    def set_filter_text(self, text: str) -> None:
        text = text or ""
        if self._filter_text == text:
            return
        self._filter_text = text
        self.filterChanged.emit(text)

    @contextmanager
    def selection_batch(self):
        self._selection_batch_depth += 1
        try:
            yield self._selected_indices
        finally:
            self._selection_batch_depth -= 1
            if self._selection_batch_depth == 0 and self._selection_dirty:
                self._selection_dirty = False
                self.selectionChanged.emit(len(self._selected_indices))

    def _on_selection_mutated(self) -> None:
        if self._selection_batch_depth > 0:
            self._selection_dirty = True
            return
        self.selectionChanged.emit(len(self._selected_indices))
