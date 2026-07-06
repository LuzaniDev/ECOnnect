from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGraphicsOpacityEffect, QApplication,
)


class LoadingOverlay(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            LoadingOverlay {
                background: rgba(0, 0, 0, 180);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        container = QWidget()
        container.setFixedSize(400, 160)
        container.setStyleSheet("""
            QWidget {
                background: #1e1e2e;
                border: 1px solid #3a3a4a;
                border-radius: 12px;
            }
        """)
        cl = QVBoxLayout(container)
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(16)

        self.lbl_title = QLabel("Processando boletos...")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff; background: transparent; border: none;")
        cl.addWidget(self.lbl_title)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(320)
        self.progress.setFixedHeight(24)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #2a2a3a;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                text-align: center;
                font-size: 11px;
                color: #a0a0b0;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4facfe, stop:1 #00f2fe);
                border-radius: 3px;
            }
        """)
        cl.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 12px; color: #a0a0b0; background: transparent; border: none;")
        cl.addWidget(self.lbl_status)

        layout.addWidget(container)

        self._processados = 0
        self._total = 0

    def show_progress(self, processados: int, total: int):
        self._processados = processados
        self._total = total
        self.progress.setRange(0, total)
        self.progress.setValue(processados)
        self.lbl_status.setText(f"{processados} de {total} boletos processados")

    def set_indeterminate(self, text: str = ""):
        self.progress.setRange(0, 0)
        self.lbl_status.setText(text)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            self.resize(self.parent().size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.resize(self.parent().size())
