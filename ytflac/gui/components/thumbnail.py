from __future__ import annotations
import urllib.request

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QObject,
    QRunnable,
    QThreadPool,
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath

class _ThumbSignals(QObject):
    done = pyqtSignal(str, QPixmap)

class _ThumbLoader(QRunnable):
    def __init__(self, url: str, size: int):
        super().__init__()
        self._url = url
        self._size = size
        self.signals = _ThumbSignals()

    def run(self):
        try:
            req = urllib.request.Request(
                self._url, headers={"User-Agent": "YtFLAC/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            pm = QPixmap()
            pm.loadFromData(data)
            if not pm.isNull():
                pm = pm.scaled(
                    self._size,
                    self._size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (pm.width() - self._size) // 2
                y = (pm.height() - self._size) // 2
                pm = pm.copy(x, y, self._size, self._size)
                self.signals.done.emit(self._url, pm)
        except Exception:
            pass

_thumb_pool = QThreadPool.globalInstance()
_thumb_cache: dict[str, QPixmap] = {}

def load_thumbnail(url: str, size: int, callback):
    if not url:
        return
    key = f"{url}@{size}"
    if key in _thumb_cache:
        callback(_thumb_cache[key])
        return
    loader = _ThumbLoader(url, size)

    def _done(_u, pm):
        _thumb_cache[key] = pm
        callback(pm)

    loader.signals.done.connect(_done)
    _thumb_pool.start(loader)

def rounded_pixmap(pm: QPixmap, radius: int = 8) -> QPixmap:
    if pm.isNull():
        return pm
    out = QPixmap(pm.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pm.width(), pm.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pm)
    painter.end()
    return out
