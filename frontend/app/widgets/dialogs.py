from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow
from frontend.app.core.logger import logger


DIALOG_BASE_STYLE = """
QMessageBox {
    background-color: #0a1220;
    color: #f1f5f9;
}
QLabel {
    color: #f1f5f9;
    font-size: 13px;
}
QPushButton {
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    min-width: 80px;
    font-weight: 600;
}
"""


def show_error(parent, title: str, message: str):
    logger.error("DIALOG", f"{title}: {message}")
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + """
        QPushButton {
            background-color: #ef4444;
        }
        QPushButton:hover {
            background-color: #f87171;
        }
    """
    )
    msg.show()
    msg.raise_()
    msg.activateWindow()
    msg.exec()


def show_success(parent, title: str, message: str):
    logger.info("DIALOG", f"{title}: {message}")
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + """
        QPushButton {
            background-color: #22c55e;
        }
        QPushButton:hover {
            background-color: #34d16e;
        }
    """
    )
    msg.exec()


class InputDialog(QDialog):
    def __init__(self, parent, title: str, label: str, default: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(500, 300)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QTextEdit {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(lbl)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(default)
        self.text_edit.setPlaceholderText("Cole o comando curl aqui...")
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()


def show_confirm(parent, title: str, message: str) -> bool:
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.No)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + """
        QPushButton {
            background-color: #014998;
        }
        QPushButton:hover {
            background-color: #025db8;
        }
        QPushButton[class="yes"] {
            background-color: #f8891d;
        }
    """
    )
    return msg.exec() == QMessageBox.Yes
