from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QImage


def _icon(svg_body: str) -> QIcon:
    data = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{svg_body}</svg>"""
    img = QImage.fromData(data.encode("utf-8"), "SVG")
    pix = QPixmap.fromImage(img)
    icon = QIcon(pix)
    return icon


_ICONS = {
    "backspace": _icon('<path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/><line x1="18" y1="9" x2="12" y2="15"/><line x1="12" y1="9" x2="18" y2="15"/>'),
    "clear": _icon('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'),
    "divide": _icon('<circle cx="12" cy="6" r="1"/><line x1="5" y1="12" x2="19" y2="12"/><circle cx="12" cy="18" r="1"/>'),
    "multiply": _icon('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'),
    "minus": _icon('<line x1="5" y1="12" x2="19" y2="12"/>'),
    "plus": _icon('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'),
    "equals": _icon('<line x1="5" y1="9" x2="19" y2="9"/><line x1="5" y1="15" x2="19" y2="15"/>'),
    "percent": _icon('<path d="M19 5 5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>'),
}

_BTN_STYLE = """
QPushButton {
    background: {bg}; border: none; border-radius: 8px;
    color: {fg}; font-size: 18px; font-weight: 600;
    padding: 12px; min-width: 60px; min-height: 48px;
}
QPushButton:hover { background: {hover}; }
QPushButton:pressed { background: {pressed}; }
"""

_OP_BTN_STYLE = """
QPushButton {
    background: {bg}; border: none; border-radius: 8px;
    color: #fff; font-size: 20px; font-weight: 700;
    padding: 12px; min-width: 56px; min-height: 48px;
}
QPushButton:hover { background: {hover}; }
QPushButton:pressed { background: {pressed}; }
"""

_EQ_BTN_STYLE = """
QPushButton {
    background: {bg}; border: none; border-radius: 8px;
    color: #fff; font-size: 22px; font-weight: 700;
    padding: 12px; min-width: 56px; min-height: 48px;
}
QPushButton:hover { background: {hover}; }
QPushButton:pressed { background: {pressed}; }
"""


class _BounceButton(QPushButton):
    def __init__(self, text="", icon=None):
        super().__init__(text)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(22, 22))
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(80)
        self._anim.setEasingCurve(QEasingCurve.OutBack)

    def mousePressEvent(self, e):
        g = self.geometry()
        self._anim.setStartValue(g)
        self._anim.setEndValue(g.adjusted(2, 2, -2, -2))
        self._anim.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        g = self.geometry()
        self._anim.setStartValue(g)
        self._anim.setEndValue(g.adjusted(-2, -2, 2, 2))
        self._anim.start()
        super().mouseReleaseEvent(e)


class CalculadoraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculadora")
        self.setFixedSize(320, 440)
        self.setStyleSheet("""
            QDialog { background: #1e293b; border-radius: 16px; }
        """)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        self._expression = ""
        self._result = "0"
        self._last_op = None
        self._last_val = None
        self._clear_next = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._display = QLabel("0")
        self._display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._display.setStyleSheet("""
            background: #0f172a; border-radius: 12px; padding: 16px 20px;
            font-size: 32px; font-weight: 700; color: #f1f5f9;
            min-height: 60px; font-family: 'Courier New', monospace;
        """)
        layout.addWidget(self._display)

        self._sub_display = QLabel("")
        self._sub_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._sub_display.setStyleSheet("""
            background: transparent; padding: 0 20px 4px 20px;
            font-size: 13px; color: #64748b; min-height: 18px;
        """)
        layout.addWidget(self._sub_display)

        buttons = [
            ("C", "op"), ("\u00b1", "op"), ("%", "op"), ("\u00f7", "op"),
            ("7", "num"), ("8", "num"), ("9", "num"), ("\u00d7", "op"),
            ("4", "num"), ("5", "num"), ("6", "num"), ("\u2212", "op"),
            ("1", "num"), ("2", "num"), ("3", "num"), ("+", "op"),
            ("\u232b", "fn"), ("0", "num"), (",", "num"), ("=", "eq"),
        ]

        grid = QVBoxLayout()
        grid.setSpacing(8)
        for row_idx in range(5):
            row_btns = buttons[row_idx * 4:(row_idx + 1) * 4]
            h = QHBoxLayout()
            h.setSpacing(8)
            for text, kind in row_btns:
                btn = _BounceButton(text)
                if kind == "num":
                    btn.setStyleSheet(_BTN_STYLE.format(
                        bg="#334155", fg="#f1f5f9", hover="#475569", pressed="#1e293b",
                    ))
                    btn.clicked.connect(lambda _, t=text: self._on_num(t))
                elif kind == "op":
                    is_eq = text in ("\u00f7", "\u00d7", "\u2212", "+")
                    btn.setStyleSheet(_OP_BTN_STYLE.format(
                        bg="#3b82f6" if not is_eq else "#f59e0b",
                        hover="#2563eb" if not is_eq else "#d97706",
                        pressed="#1d4ed8" if not is_eq else "#b45309",
                    ))
                    btn.clicked.connect(lambda _, t=text: self._on_op(t))
                elif kind == "eq":
                    btn.setStyleSheet(_EQ_BTN_STYLE.format(
                        bg="#10b981", hover="#059669", pressed="#047857",
                    ))
                    btn.clicked.connect(self._on_eq)
                elif kind == "fn":
                    if text == "\u232b":
                        btn.setIcon(_ICONS["backspace"])
                        btn.setIconSize(QSize(22, 22))
                    btn.setStyleSheet(_BTN_STYLE.format(
                        bg="#334155", fg="#f1f5f9", hover="#475569", pressed="#1e293b",
                    ))
                    btn.clicked.connect(lambda: self._on_backspace())
                h.addWidget(btn)
            grid.addLayout(h)
        layout.addLayout(grid)

        self._animate_display()

    def _animate_display(self):
        self._anim = QPropertyAnimation(self._display, b"geometry")
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QEasingCurve.OutQuad)
        g = self._display.geometry()
        self._anim.setStartValue(g.adjusted(0, -2, 0, 0))
        self._anim.setEndValue(g)
        self._anim.start()

    def _update_display(self):
        self._display.setText(self._result if self._result else "0")
        self._animate_display()

    def _on_num(self, char: str):
        if char == ",":
            if self._clear_next or self._result in ("0", "0.0"):
                self._result = "0,"
                self._clear_next = False
                self._update_display()
                return
            if "," in self._result:
                return
            self._result += ","
            self._update_display()
            return

        if self._clear_next or self._result in ("0", "0,0"):
            self._result = char
            self._clear_next = False
        else:
            self._result += char
        self._update_display()

    def _on_op(self, op: str):
        current = float(self._result.replace(",", "."))
        if self._last_op and not self._clear_next:
            current = self._calc(self._last_val, current, self._last_op)
            self._result = self._fmt(current)
        self._last_val = current
        self._last_op = {"\u00f7": "/", "\u00d7": "*", "\u2212": "-", "+": "+", "%": "%"}.get(op, op)
        self._sub_display.setText(f"{self._fmt(self._last_val)} {self._last_op}")
        self._clear_next = True
        self._update_display()

    def _on_eq(self):
        if self._last_op and self._last_val is not None:
            current = float(self._result.replace(",", "."))
            result = self._calc(self._last_val, current, self._last_op)
            self._sub_display.setText(f"{self._fmt(self._last_val)} {self._last_op} {self._fmt(current)} =")
            self._result = self._fmt(result)
            self._last_op = None
            self._last_val = None
            self._clear_next = True
            self._update_display()

    def _on_backspace(self):
        if len(self._result) > 1:
            self._result = self._result[:-1]
        else:
            self._result = "0"
        self._update_display()

    def _calc(self, a: float, b: float, op: str) -> float:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b if b != 0 else 0
        return 0

    def _fmt(self, v: float) -> str:
        if v == int(v):
            return str(int(v))
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        return s.replace(".", ",")
