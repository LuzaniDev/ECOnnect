import math
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget
from pathlib import Path


class LoadingPopup(QWidget):
    def __init__(self, parent=None):
        main = parent.window() if parent else parent
        super().__init__(main)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        logo_path = Path(__file__).resolve().parents[2] / "assets" / "logo_256.png"
        self._logo_pix = QPixmap(str(logo_path))

        self._angle = 0.0
        self._dot_count = 0
        self._dot_timer = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(30)

        self._cycle_ms = 2000
        self._logo_size = 180
        self._stripe_h = 18
        self._max_offset = 45

        self._logo1 = None
        self._logo2 = None
        self._hidden = True
        self._render_logos()

    def _render_logos(self):
        s = self._logo_size
        scaled = self._logo_pix.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        ox = (s - scaled.width()) // 2
        oy = (s - scaled.height()) // 2
        for inv in (False, True):
            pix = QPixmap(s, s)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawPixmap(ox, oy, scaled)
            p.end()
            img = pix.toImage()
            for y in range(s):
                keep = (y // self._stripe_h) % 2 == (1 if inv else 0)
                if not keep:
                    for x in range(s):
                        img.setPixelColor(x, y, QColor(0, 0, 0, 0))
            result = QPixmap.fromImage(img)
            if inv:
                self._logo2 = result
            else:
                self._logo1 = result

    def showEvent(self, event):
        self._hidden = False
        parent = self.parent()
        if parent:
            self.setGeometry(parent.rect())
        self._angle = 0.0
        self._dot_count = 0
        self._dot_timer = 0
        self._timer.start()
        self.raise_()
        super().showEvent(event)

    def hideEvent(self, event):
        self._hidden = True
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        if self._hidden:
            return
        self._angle += 4
        if self._angle >= 360:
            self._angle -= 360
        self._dot_timer += 1
        if self._dot_timer >= 16:
            self._dot_timer = 0
            self._dot_count = (self._dot_count + 1) % 4
        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        s = self._logo_size
        ms = self._cycle_ms
        t = (self._angle * ms / 360 / 1000) % (ms / 1000) / (ms / 1000)
        phase = t % 1.0

        off = 0
        rot = 0.0
        if phase < 0.1:
            off = 0
            rot = 0.0
        elif phase < 0.35:
            q = (phase - 0.1) / 0.25
            off = q * self._max_offset
            rot = 0.0
        elif phase < 0.66:
            q = (phase - 0.35) / 0.31
            off = self._max_offset
            rot = q * math.pi * 2
        elif phase < 0.9:
            q = (phase - 0.66) / 0.24
            off = (1 - q) * self._max_offset
            rot = math.pi * 2
        else:
            off = 0
            rot = math.pi * 2

        cx = w / 2
        cy = h / 2

        for lx, logo in [(-off, self._logo1), (off, self._logo2)]:
            painter.save()
            painter.translate(cx + lx, cy)
            painter.rotate(math.degrees(rot))
            painter.drawPixmap(-s / 2, -s / 2, s, s, logo)
            painter.restore()

        font = QFont("Arial", 20, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        text = "Carregando" + "." * self._dot_count
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        painter.drawText(QRect(int((w - tw) / 2), int(cy + s / 2 + 30), tw, th), Qt.AlignLeft, text)

        painter.end()
