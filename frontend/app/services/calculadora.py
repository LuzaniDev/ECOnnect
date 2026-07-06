from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel,
    QGraphicsDropShadowEffect, QGridLayout,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor


class CalculadoraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from frontend.app.core.theme import theme_manager
        self._t = theme_manager.current()

        self.setWindowTitle("Calculadora")
        self.setFixedSize(280, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        self._expression = ""
        self._result = "0"
        self._last_op = None
        self._last_val = None
        self._clear_next = False
        self._fresh = True

        t = self._t
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.setStyleSheet(f"""
            QDialog {{ background: {t.bg}; border-radius: 12px; }}
        """)

        self._display = QLabel("0")
        self._display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._display.setStyleSheet(f"""
            background: {t.bg_darker if hasattr(t,'bg_darker') else '#0f172a'};
            border-radius: 8px; padding: 12px 16px;
            font-size: 28px; font-weight: 700; color: {t.text};
            min-height: 44px; font-family: 'Courier New', monospace;
        """)
        layout.addWidget(self._display)

        grid = QGridLayout()
        grid.setSpacing(6)

        num_style = f"""
            QPushButton {{ background: {t.surface_elevated}; border: none; border-radius: 6px;
                color: {t.text}; font-size: 17px; font-weight: 600; padding: 10px; }}
            QPushButton:hover {{ background: {t.border}; }}
            QPushButton:pressed {{ background: {t.bg}; }}
        """
        op_style = f"""
            QPushButton {{ background: {t.warning}; border: none; border-radius: 6px;
                color: #fff; font-size: 18px; font-weight: 700; padding: 10px; }}
            QPushButton:hover {{ background: {t.warning_hover if hasattr(t,'warning_hover') else '#d97706'}; }}
            QPushButton:pressed {{ background: #b45309; }}
        """
        fn_style = f"""
            QPushButton {{ background: {t.surface_elevated}; border: none; border-radius: 6px;
                color: {t.text}; font-size: 15px; font-weight: 600; padding: 10px; }}
            QPushButton:hover {{ background: {t.border}; }}
            QPushButton:pressed {{ background: {t.bg}; }}
        """
        eq_style = f"""
            QPushButton {{ background: {t.success}; border: none; border-radius: 6px;
                color: #fff; font-size: 20px; font-weight: 700; padding: 10px; }}
            QPushButton:hover {{ background: {t.success_hover if hasattr(t,'success_hover') else '#059669'}; }}
            QPushButton:pressed {{ background: #047857; }}
        """

        botoes = [
            ("C", 0, 0, "op"),
            ("\u00b1", 0, 1, "op"),
            ("%", 0, 2, "op"),
            ("\u00f7", 0, 3, "op"),
            ("7", 1, 0, "num"),
            ("8", 1, 1, "num"),
            ("9", 1, 2, "num"),
            ("\u00d7", 1, 3, "op"),
            ("4", 2, 0, "num"),
            ("5", 2, 1, "num"),
            ("6", 2, 2, "num"),
            ("-", 2, 3, "op"),
            ("1", 3, 0, "num"),
            ("2", 3, 1, "num"),
            ("3", 3, 2, "num"),
            ("+", 3, 3, "op"),
            ("\u232b", 4, 0, "fn"),
            ("0", 4, 1, "num"),
            (",", 4, 2, "num"),
            ("=", 4, 3, "eq"),
        ]

        def _on_num(char):
            if char == ",":
                if self._clear_next or self._fresh:
                    self._result = "0,"
                    self._clear_next = False
                    self._fresh = False
                    self._atualizar()
                    return
                if "," in self._result:
                    return
                self._result += ","
                self._atualizar()
                return
            if self._clear_next or self._fresh:
                self._result = char
                self._clear_next = False
                self._fresh = False
            else:
                self._result += char
            self._atualizar()

        def _on_op(text):
            if text == "C":
                self._result = "0"
                self._last_op = None
                self._last_val = None
                self._clear_next = False
                self._fresh = True
                self._atualizar()
                return
            op_map = {"\u00f7": "/", "\u00d7": "*", "-": "-", "+": "+", "%": "%"}
            op = op_map.get(text, text)
            current = float(self._result.replace(",", "."))
            if self._last_op is not None and not self._clear_next:
                current = self._calc(self._last_val, current, self._last_op)
                self._result = self._fmt(current)
            self._last_val = current
            self._last_op = op
            self._clear_next = True
            self._fresh = False
            self._atualizar()

        for text, row, col, kind in botoes:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)

            if kind == "num":
                btn.setStyleSheet(num_style)
                btn.clicked.connect(lambda checked=False, t=text: _on_num(t))
            elif kind == "op":
                btn.setStyleSheet(op_style)
                btn.clicked.connect(lambda checked=False, t=text: _on_op(t))
            elif kind == "eq":
                btn.setStyleSheet(eq_style)
                btn.clicked.connect(lambda: self._on_eq())
            elif kind == "fn":
                btn.setStyleSheet(fn_style)
                btn.clicked.connect(lambda: self._on_backspace())

            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

    def _atualizar(self):
        self._display.setText(self._result)

    def _on_eq(self):
        if self._last_op is not None and self._last_val is not None:
            current = float(self._result.replace(",", "."))
            result = self._calc(self._last_val, current, self._last_op)
            self._result = self._fmt(result)
            self._last_op = None
            self._last_val = None
            self._clear_next = True
            self._atualizar()

    def _on_backspace(self):
        if self._result in ("0", "0,0"):
            return
        if len(self._result) > 1:
            self._result = self._result[:-1]
        else:
            self._result = "0"
        self._atualizar()

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
