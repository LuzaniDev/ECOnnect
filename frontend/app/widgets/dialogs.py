from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow, QColor
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager


DIALOG_BASE_STYLE = """
QPushButton {
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    min-width: 80px;
    font-weight: 600;
}
"""


def show_error(parent, title: str, message: str):
    t = theme_manager.current()
    logger.error("DIALOG", f"{title}: {message}")
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + f"""
        QMessageBox {{ background-color: {t.bg}; color: {t.text}; }}
        QLabel {{ color: {t.text}; }}
        QPushButton {{
            background-color: {t.danger};
            color: {t.selection_text};
        }}
        QPushButton:hover {{
            background-color: {t.danger_hover};
        }}
    """
    )
    msg.show()
    msg.raise_()
    msg.activateWindow()
    msg.exec()


def show_success(parent, title: str, message: str):
    t = theme_manager.current()
    logger.info("DIALOG", f"{title}: {message}")
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + f"""
        QMessageBox {{ background-color: {t.bg}; color: {t.text}; }}
        QLabel {{ color: {t.text}; }}
        QPushButton {{
            background-color: {t.success};
            color: {t.selection_text};
        }}
        QPushButton:hover {{
            background-color: {t.success_hover};
        }}
    """
    )
    msg.exec()


class InputDialog(QDialog):
    def __init__(self, parent, title: str, label: str, default: str = ""):
        super().__init__(parent)
        self._t = theme_manager.current()
        self.setWindowTitle(title)
        self.setMinimumSize(500, 300)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {self._t.bg}; color: {self._t.text}; }}
            QLabel {{ color: {self._t.text}; }}
            QTextEdit {{
                background-color: {self._t.bg}; color: {self._t.text};
                border: 1px solid {self._t.border}; border-radius: 4px; padding: 6px;
            }}
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
    t = theme_manager.current()
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.No)
    msg.setStyleSheet(
        DIALOG_BASE_STYLE
        + f"""
        QMessageBox {{ background-color: {t.bg}; color: {t.text}; }}
        QLabel {{ color: {t.text}; }}
        QPushButton {{
            background-color: {t.primary};
            color: {t.selection_text};
        }}
        QPushButton:hover {{
            background-color: {t.primary_hover};
        }}
    """
    )
    return msg.exec() == QMessageBox.Yes
