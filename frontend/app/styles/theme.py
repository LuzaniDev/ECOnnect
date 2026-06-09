from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


DARK_QSS = """
/* ===== CORE ===== */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: "Segoe UI", "Arial", sans-serif;
}

/* ===== LABELS ===== */
QLabel {
    color: #c9d1d9;
    background: transparent;
}

QLabel[heading="true"] {
    font-size: 20px;
    font-weight: bold;
    color: #c9d1d9;
    padding: 8px 0;
}

QLabel[subheading="true"] {
    font-size: 13px;
    color: #8b949e;
    padding: 4px 0;
}

QLabel[muted="true"] {
    font-size: 11px;
    color: #8b949e;
}

QLabel[success="true"] {
    color: #3fb950;
    font-weight: bold;
}

QLabel[danger="true"] {
    color: #f85149;
    font-weight: bold;
}

QLabel[warning="true"] {
    color: #d29922;
    font-weight: bold;
}

/* ===== TEXT INPUTS ===== */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #1f6feb;
    background-color: #0d1117;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #161b22;
    color: #8b949e;
    border-color: #21262d;
}

/* ===== COMBOBOX ===== */
QComboBox {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
    min-width: 80px;
}

QComboBox:focus {
    border-color: #1f6feb;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}

/* ===== BUTTONS ===== */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-height: 18px;
    outline: none;
}

QPushButton:hover {
    background-color: #30363d;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton[primary="true"] {
    background-color: #1f6feb;
    color: #ffffff;
    border: none;
}

QPushButton[primary="true"]:hover {
    background-color: #388bfd;
}

QPushButton[accent="true"] {
    background-color: #d29922;
    color: #0d1117;
    border: none;
}

QPushButton[accent="true"]:hover {
    background-color: #e3b341;
}

QPushButton[danger="true"] {
    background-color: #f85149;
    color: #ffffff;
    border: none;
}

QPushButton[danger="true"]:hover {
    background-color: #ff6b63;
}

QPushButton[success="true"] {
    background-color: #238636;
    color: #ffffff;
    border: none;
}

QPushButton[success="true"]:hover {
    background-color: #2ea043;
}

QPushButton[ghost="true"] {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid #30363d;
}

QPushButton[ghost="true"]:hover {
    background-color: #161b22;
    color: #c9d1d9;
    border-color: #484f58;
}

/* ===== TABLES ===== */
QTableWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    gridline-color: #21262d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    font-size: 13px;
}

QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #21262d;
}

QTableWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QTableWidget::item:alternate {
    background-color: #161b22;
}

QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #1f6feb;
    font-weight: bold;
    font-size: 11px;
}

/* ===== SCROLLBARS ===== */
QScrollBar:vertical {
    background-color: #0d1117;
    width: 6px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #0d1117;
    height: 6px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== TABS ===== */
QTabWidget::pane {
    background: transparent;
    border: none;
    padding: 0;
}

QTabBar::tab {
    background: transparent;
    color: #8b949e;
    border: none;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #d29922;
    border-bottom: 2px solid #d29922;
}

QTabBar::tab:hover {
    color: #c9d1d9;
}

/* ===== GROUPBOX ===== */
QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    font-weight: bold;
    color: #c9d1d9;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: #c9d1d9;
}

/* ===== CHECKBOX ===== */
QCheckBox {
    color: #c9d1d9;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid #30363d;
    background-color: #0d1117;
}

QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border-color: #1f6feb;
}

QCheckBox::indicator:hover {
    border-color: #484f58;
}

/* ===== SPINBOX ===== */
QSpinBox, QDoubleSpinBox {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1f6feb;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #30363d;
    border-top-right-radius: 6px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #30363d;
    border-bottom-right-radius: 6px;
}

/* ===== FRAMES ===== */
QFrame {
    background-color: transparent;
}

QFrame[card="true"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 20px;
}

QFrame[elevated="true"] {
    background-color: #1c2333;
    border: 1px solid #30363d;
    border-radius: 8px;
}

QFrame[glass="true"] {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
}

/* ===== PROGRESSBAR ===== */
QProgressBar {
    background-color: #0d1117;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 4px;
}

/* ===== SPLITTER ===== */
QSplitter::handle {
    background-color: #21262d;
    width: 1px;
}

/* ===== STATUS BAR ===== */
QStatusBar {
    background-color: #0d1117;
    color: #8b949e;
    border-top: 1px solid #21262d;
    font-size: 11px;
}

/* ===== TOOLTIP ===== */
QToolTip {
    background-color: #1c2333;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""


def apply_theme(app: QApplication):
    app.setStyleSheet(DARK_QSS)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0d1117"))
    palette.setColor(QPalette.WindowText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Base, QColor("#0d1117"))
    palette.setColor(QPalette.Text, QColor("#c9d1d9"))
    palette.setColor(QPalette.Button, QColor("#21262d"))
    palette.setColor(QPalette.ButtonText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Highlight, QColor("#1f6feb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1c2333"))
    palette.setColor(QPalette.ToolTipText, QColor("#c9d1d9"))
    palette.setColor(QPalette.AlternateBase, QColor("#161b22"))
    palette.setColor(QPalette.BrightText, QColor("#d29922"))
    palette.setColor(QPalette.Link, QColor("#58a6ff"))
    app.setPalette(palette)
