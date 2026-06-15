import os
import json
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QTabWidget


THEME_CONFIG = os.path.join(os.path.expanduser("~"), ".econnect", "theme.json")


class ThemeType(Enum):
    BLACK = "black"
    WHITE = "white"
    MATRIX = "matrix"


@dataclass
class Theme:
    type: ThemeType
    bg: str
    surface: str
    surface_elevated: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_muted: str
    primary: str
    primary_hover: str
    danger: str
    danger_hover: str
    warning: str
    warning_hover: str
    success: str
    success_hover: str
    info: str
    selection: str
    selection_text: str
    accent_blue: str
    accent_green: str
    accent_yellow: str
    accent_red: str
    accent_purple: str
    accent_cyan: str
    accent_pink: str
    accent_sky: str
    accent_coral: str
    accent_emerald: str
    sidebar_active_bg: str
    sidebar_active_text: str
    sidebar_checked_border: str
    sidebar_logout_hover_text: str
    titlebar_dark: bool
    gradient_start: str
    gradient_end: str

    @property
    def sidebar_bg(self) -> str:
        return self.bg

    @property
    def sidebar_hover(self) -> str:
        return self.surface

    @property
    def sidebar_border(self) -> str:
        return self.border

    @property
    def sidebar_brand_text(self) -> str:
        return self.text

    @property
    def sidebar_sub_text(self) -> str:
        return self.text_secondary

    @property
    def sidebar_user_text(self) -> str:
        return self.text_secondary

    @property
    def sidebar_role_text(self) -> str:
        return self.warning

    @property
    def sidebar_role_border(self) -> str:
        return self.border

    @property
    def sidebar_group_text(self) -> str:
        return self.text_secondary

    @property
    def sidebar_logout_text(self) -> str:
        return self.text_secondary

    @property
    def sidebar_logout_hover_bg(self) -> str:
        return f"rgba({_hex_to_rgb(self.danger)},0.08)"


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "0,0,0"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _color_with_brightness(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r = max(0, min(255, int(int(h[0:2], 16) * factor)))
    g = max(0, min(255, int(int(h[2:4], 16) * factor)))
    b = max(0, min(255, int(int(h[4:6], 16) * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


BLACK = Theme(
    type=ThemeType.BLACK,
    bg="#0d1117",
    surface="#161b22",
    surface_elevated="#1c2333",
    border="#30363d",
    border_strong="#484f58",
    text="#c9d1d9",
    text_secondary="#8b949e",
    text_muted="#484f58",
    primary="#1f6feb",
    primary_hover="#388bfd",
    danger="#f85149",
    danger_hover="#ff6b63",
    warning="#d29922",
    warning_hover="#e3b341",
    success="#3fb950",
    success_hover="#4cda64",
    info="#58a6ff",
    selection="#1f6feb",
    selection_text="#ffffff",
    accent_blue="#58a6ff",
    accent_green="#3fb950",
    accent_yellow="#d29922",
    accent_red="#f85149",
    accent_purple="#bc8cff",
    accent_cyan="#39d2c0",
    accent_pink="#f97583",
    accent_sky="#79c0ff",
    accent_coral="#ffa657",
    accent_emerald="#56d364",
    sidebar_active_bg="rgba(31,111,235,0.15)",
    sidebar_active_text="#58a6ff",
    sidebar_checked_border="#1f6feb",
    sidebar_logout_hover_text="#f85149",
    titlebar_dark=True,
    gradient_start="#0d1117",
    gradient_end="#161b22",
)

WHITE = Theme(
    type=ThemeType.WHITE,
    bg="#f6f8fa",
    surface="#ffffff",
    surface_elevated="#ffffff",
    border="#d0d7de",
    border_strong="#8c959f",
    text="#1f2328",
    text_secondary="#656d76",
    text_muted="#8c959f",
    primary="#0969da",
    primary_hover="#218bff",
    danger="#cf222e",
    danger_hover="#a40e26",
    warning="#9a6700",
    warning_hover="#b08800",
    success="#1a7f37",
    success_hover="#2da44e",
    info="#0969da",
    selection="#0969da",
    selection_text="#ffffff",
    accent_blue="#0969da",
    accent_green="#1a7f37",
    accent_yellow="#9a6700",
    accent_red="#cf222e",
    accent_purple="#8250df",
    accent_cyan="#1b7c83",
    accent_pink="#bf3989",
    accent_sky="#218bff",
    accent_coral="#d15704",
    accent_emerald="#2da44e",
    sidebar_active_bg="rgba(9,105,218,0.12)",
    sidebar_active_text="#0969da",
    sidebar_checked_border="#0969da",
    sidebar_logout_hover_text="#cf222e",
    titlebar_dark=False,
    gradient_start="#f6f8fa",
    gradient_end="#ffffff",
)

MATRIX = Theme(
    type=ThemeType.MATRIX,
    bg="#000000",
    surface="#0a0a0a",
    surface_elevated="#0a0a0a",
    border="#00ff41",
    border_strong="#008f11",
    text="#00ee41",
    text_secondary="#00cc33",
    text_muted="#006a00",
    primary="#00ff41",
    primary_hover="#33ff66",
    danger="#ff0000",
    danger_hover="#ff3333",
    warning="#ffff00",
    warning_hover="#ffff66",
    success="#00ff41",
    success_hover="#33ff66",
    info="#00ffff",
    selection="#00ff41",
    selection_text="#000000",
    accent_blue="#00ffff",
    accent_green="#00ff41",
    accent_yellow="#ffff00",
    accent_red="#ff0000",
    accent_purple="#ff00ff",
    accent_cyan="#00ffff",
    accent_pink="#ff69b4",
    accent_sky="#00ffff",
    accent_coral="#ff6600",
    accent_emerald="#00ff41",
    sidebar_active_bg="rgba(0,255,65,0.12)",
    sidebar_active_text="#00ff41",
    sidebar_checked_border="#00ff41",
    sidebar_logout_hover_text="#ff0000",
    titlebar_dark=True,
    gradient_start="#000000",
    gradient_end="#0a0a0a",
)

THEMES = {
    ThemeType.BLACK: BLACK,
    ThemeType.WHITE: WHITE,
    ThemeType.MATRIX: MATRIX,
}


def _set_titlebar_theme(hwnd: int, dark: bool):
    if not hwnd:
        return
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        pass


def _build_palette(t: Theme) -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(t.bg))
    p.setColor(QPalette.WindowText, QColor(t.text))
    p.setColor(QPalette.Base, QColor(t.surface))
    p.setColor(QPalette.AlternateBase, QColor(t.surface_elevated))
    p.setColor(QPalette.Text, QColor(t.text))
    p.setColor(QPalette.Button, QColor(t.surface))
    p.setColor(QPalette.ButtonText, QColor(t.text))
    p.setColor(QPalette.Highlight, QColor(t.selection))
    p.setColor(QPalette.HighlightedText, QColor(t.selection_text))
    p.setColor(QPalette.ToolTipBase, QColor(t.surface_elevated))
    p.setColor(QPalette.ToolTipText, QColor(t.text))
    p.setColor(QPalette.BrightText, QColor(t.warning))
    p.setColor(QPalette.Link, QColor(t.info))
    p.setColor(QPalette.PlaceholderText, QColor(t.text_muted))
    return p


def _build_app_qss(t: Theme) -> str:
    return f"""
QMainWindow, QDialog {{
    background-color: {t.bg}; color: {t.text};
}}
QWidget {{
    background-color: {t.bg}; color: {t.text};
}}
QWidget#outer_container {{
    background-color: {t.bg}; border: 1px solid {t.border};
}}
QScrollArea {{
    background-color: {t.bg}; border: none;
}}
QLabel {{
    color: {t.text}; background: transparent;
}}
QLabel[heading="true"] {{
    font-size: 20px; font-weight: bold; color: {t.text}; padding: 8px 0;
}}
QLabel[subheading="true"] {{
    font-size: 13px; color: {t.text_secondary}; padding: 4px 0;
}}
QLabel[muted="true"] {{
    font-size: 11px; color: {t.text_secondary};
}}
QLabel[success="true"] {{
    color: {t.success}; font-weight: bold;
}}
QLabel[danger="true"] {{
    color: {t.danger}; font-weight: bold;
}}
QLabel[warning="true"] {{
    color: {t.warning}; font-weight: bold;
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    padding: 8px 12px; font-size: 13px;
    selection-background-color: {t.selection}; selection-color: {t.selection_text};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {t.primary}; background-color: {t.surface};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {t.surface}; color: {t.text_secondary}; border-color: {t.border};
}}
QComboBox {{
    background-color: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    padding: 7px 12px; font-size: 13px; min-width: 80px;
}}
QComboBox:focus {{ border-color: {t.primary}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t.text_secondary}; margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    selection-background-color: {t.selection}; selection-color: {t.selection_text};
    outline: none; padding: 4px;
}}
QPushButton {{
    background-color: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    padding: 8px 20px; font-size: 13px; font-weight: 600;
    min-height: 18px; outline: none;
}}
QPushButton:hover {{ background-color: {t.border}; }}
QPushButton:pressed {{ background-color: {t.surface_elevated}; }}
QPushButton:disabled {{
    background-color: {t.surface}; color: {t.text_muted}; border-color: {t.border};
}}
QPushButton[primary="true"] {{
    background-color: {t.primary}; color: {t.selection_text}; border: none;
}}
QPushButton[primary="true"]:hover {{
    background-color: {t.primary_hover};
}}
QPushButton[accent="true"] {{
    background-color: {t.warning}; color: {t.bg}; border: none;
}}
QPushButton[accent="true"]:hover {{
    background-color: {t.warning_hover};
}}
QPushButton[danger="true"] {{
    background-color: {t.danger}; color: {t.selection_text}; border: none;
}}
QPushButton[danger="true"]:hover {{
    background-color: {t.danger_hover};
}}
QPushButton[success="true"] {{
    background-color: {t.success}; color: {t.selection_text}; border: none;
}}
QPushButton[success="true"]:hover {{
    background-color: {t.success_hover};
}}
QPushButton[ghost="true"] {{
    background-color: transparent; color: {t.text_secondary};
    border: 1px solid {t.border};
}}
QPushButton[ghost="true"]:hover {{
    background-color: {t.surface}; color: {t.text};
    border-color: {t.border_strong};
}}
QTableWidget {{
    background-color: {t.bg}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 8px;
    gridline-color: {t.border};
    selection-background-color: {t.selection}; selection-color: {t.selection_text};
    font-size: 13px;
}}
QTableWidget::item {{
    padding: 8px 12px; border-bottom: 1px solid {t.border};
}}
QTableWidget::item:selected {{
    background-color: {t.selection}; color: {t.selection_text};
}}
QTableWidget::item:alternate {{
    background-color: {t.surface};
}}
QHeaderView::section {{
    background-color: {t.surface}; color: {t.text_secondary};
    padding: 10px 12px; border: none;
    border-bottom: 2px solid {t.primary};
    font-weight: bold; font-size: 11px;
}}
QScrollBar:vertical {{
    background-color: {t.bg}; width: 6px; border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {t.border}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t.border_strong};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: {t.bg}; height: 6px; border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {t.border}; border-radius: 3px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {t.border_strong};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QTabWidget::pane {{
    background-color: {t.bg}; border: none; padding: 0;
}}
QTabWidget > QWidget {{
    background-color: {t.bg};
}}
QTabBar {{
    qproperty-drawBase: false;
    background: {t.surface};
}}
QTabBar::tab {{
    background: transparent; color: {t.text_secondary}; border: none;
    padding: 11px 24px; font-size: 13px; font-weight: 500;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {t.bg}; color: {t.primary};
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:hover:!selected {{
    background: {t.surface_elevated}; color: {t.text};
}}
QGroupBox {{
    background-color: {t.surface}; border: 1px solid {t.border};
    border-radius: 8px; margin-top: 12px; padding: 16px;
    font-weight: bold; color: {t.text};
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 2px 12px; color: {t.text};
}}
QCheckBox {{
    color: {t.text}; spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 2px solid {t.border}; background-color: {t.bg};
}}
QCheckBox::indicator:checked {{
    background-color: {t.primary}; border-color: {t.primary};
}}
QCheckBox::indicator:hover {{
    border-color: {t.border_strong};
}}
QRadioButton {{
    color: {t.text}; font-size: 13px; spacing: 8px;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    padding: 6px 10px; font-size: 13px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {t.primary};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border-left: 1px solid {t.border};
    border-top-right-radius: 6px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border-left: 1px solid {t.border};
    border-bottom-right-radius: 6px;
}}
QFrame {{
    background-color: transparent;
}}
QFrame#card, QFrame#chartCard, QFrame#settingsCard {{
    background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px;
}}
QFrame[elevated="true"] {{
    background-color: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 8px;
}}
QFrame[glass="true"] {{
    background-color: {t.bg}; border: 1px solid {t.border}; border-radius: 8px;
}}
QProgressBar {{
    background-color: {t.bg}; border: none; border-radius: 4px;
    height: 6px; text-align: center;
}}
QProgressBar::chunk {{
    background-color: {t.primary}; border-radius: 4px;
}}
QSplitter::handle {{
    background-color: {t.border}; width: 1px;
}}
QStatusBar {{
    background-color: {t.bg}; color: {t.text_secondary};
    border-top: 1px solid {t.border}; font-size: 11px;
}}
QToolTip {{
    background-color: {t.surface_elevated}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 6px;
    padding: 6px 10px; font-size: 12px;
}}
QLabel#sectionTitle {{
    font-size: 14px; font-weight: 700; color: {t.text}; background: transparent;
}}
QLabel#sectionDesc {{
    font-size: 12px; color: {t.text_secondary}; padding-bottom: 14px; background: transparent;
}}
QDialog {{ background-color: {t.bg}; color: {t.text}; }}
QDialog QLabel {{ background: transparent; }}
QFrame#formSection {{
    background-color: {t.surface}; border: 1px solid {t.border};
    border-radius: 10px; padding: 20px;
}}
QFrame#previewPanel {{
    background-color: {t.bg}; border-left: 1px solid {t.border};
}}
QLabel#sectionLabel, QLabel#sectionLabel2 {{
    font-size: 11px; color: {t.text_secondary};
    text-transform: uppercase; font-weight: 600; padding-bottom: 4px;
}}
QLabel#sectionHint {{
    font-size: 11px; color: {t.text_muted}; padding-bottom: 8px;
}}
QWidget#login_card {{
    background-color: {t.surface}; border: 1px solid {t.border};
    border-radius: 16px; min-width: 380px; max-width: 400px;
}}
QWidget#login_card:hover {{
    border-color: {t.primary};
}}
QLabel#login_title {{
    font-size: 26px; font-weight: 800; color: {t.text}; letter-spacing: -0.3px;
}}
QLabel#login_subtitle {{
    font-size: 12px; color: {t.text_secondary};
}}
QLabel#field_label {{
    font-size: 10px; color: {t.text_secondary}; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px; padding-bottom: 2px;
}}
QPushButton#login_btn {{
    background-color: {t.primary}; color: {t.selection_text}; border: none;
    border-radius: 6px; padding: 12px; font-size: 14px; font-weight: 700;
    min-height: 20px;
}}
QPushButton#login_btn:hover {{
    background-color: {t.primary_hover};
}}
QPushButton#login_btn:disabled {{
    background-color: {t.surface}; color: {t.text_muted};
}}
QLabel#previewHeader {{
    font-size: 14px; font-weight: 700; color: {t.text}; padding: 20px 24px 4px 24px;
}}
QLabel#previewSub {{
    font-size: 11px; color: {t.text_secondary}; padding: 0 24px 16px 24px;
    text-transform: uppercase;
}}
QFrame#logViewer {{
    background-color: {t.bg};
}}
QFrame#logToolbar {{
    background-color: {t.surface}; border-bottom: 1px solid {t.border}; padding: 8px 16px;
}}
QLabel#logTitle {{
    font-size: 14px; font-weight: 700; color: {t.text};
}}
QLabel#logCount {{
    font-size: 11px; color: {t.text_secondary};
}}
QTextEdit#logOutput {{
    background-color: {t.bg}; color: {t.text}; border: none;
    padding: 12px 16px; font-family: Consolas; font-size: 10pt;
    selection-background-color: {t.selection};
}}
QLabel#title {{
    font-size: 18px; font-weight: 700; color: {t.text}; padding: 20px 24px 4px 24px;
}}
QLabel#phone_label {{
    font-size: 13px; color: {t.text_secondary}; padding: 0 24px 16px 24px;
}}
QDateTimeEdit {{
    background: {t.surface}; border: 1px solid {t.border};
    border-radius: 4px; padding: 8px; color: {t.text}; font-size: 13px;
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""


def _build_sidebar_qss(t: Theme) -> str:
    return f"""
QWidget#sidebar {{
    background-color: {t.sidebar_bg}; border-right: 1px solid {t.sidebar_border};
    min-width: 200px; max-width: 200px;
}}
QWidget#sidebar QLabel#brand_name {{
    font-size: 16px; font-weight: 800; color: {t.sidebar_brand_text};
}}
QWidget#sidebar QLabel#brand_sub {{
    font-size: 9px; color: {t.text_muted};
}}
QWidget#sidebar QLabel#user_info {{
    font-size: 12px; color: {t.text_muted}; padding: 12px 14px 2px 14px; margin: 0 8px;
}}
QWidget#sidebar QLabel#user_role {{
    font-size: 9px; color: {t.sidebar_role_text}; padding: 0 14px 10px 14px; margin: 0 8px;
    border-bottom: 1px solid {t.border_strong}; text-transform: uppercase; font-weight: 600;
}}
QWidget#sidebar QPushButton {{
    background-color: transparent; color: {t.text_muted}; border: none;
    border-radius: 6px; text-align: left; padding: 10px 12px 10px 36px;
    font-size: 13px; font-weight: 500; margin: 5px 16px; min-height: 20px; outline: none;
}}
QWidget#sidebar QPushButton:hover {{
    background-color: {t.sidebar_hover}; color: {t.text_secondary};
}}
QWidget#sidebar QPushButton:checked {{
    background-color: {t.sidebar_active_bg}; color: {t.sidebar_active_text};
    font-weight: 700; border-left: 3px solid {t.sidebar_checked_border};
}}
QWidget#sidebar QPushButton#logout_btn {{
    color: {t.text_muted}; border-top: 1px solid {t.border};
    border-radius: 6px; margin: 12px 16px 0 16px; padding: 12px 12px;
}}
QWidget#sidebar QPushButton#logout_btn:hover {{
    color: {t.sidebar_logout_hover_text}; background-color: {t.sidebar_logout_hover_bg};
}}
QWidget#sidebar QLabel#nav_group {{
    font-size: 10px; color: {t.text_muted}; padding: 24px 20px 14px 20px;
    text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px;
}}
QWidget#sidebar QFrame#cat_separator {{
    max-height: 1px; min-height: 1px; background-color: {t.border}; border: none;
    margin: 8px 20px;
}}
"""


class ThemeManager(QObject):
    theme_changed = Signal(Theme)

    def __init__(self):
        super().__init__()
        self._theme = BLACK
        saved = self._load()
        if saved in THEMES:
            self._theme = THEMES[saved]

    def current(self) -> Theme:
        return self._theme

    def set_theme(self, theme_type: ThemeType):
        if theme_type in THEMES:
            self._theme = THEMES[theme_type]
            self._save(theme_type)
            self.theme_changed.emit(self._theme)

    def toggle_next(self):
        types = list(ThemeType)
        idx = types.index(self._theme.type)
        self.set_theme(types[(idx + 1) % len(types)])

    def apply_theme(self, main_window):
        t = self._theme
        QApplication.instance().setPalette(_build_palette(t))
        qss = _build_app_qss(t)
        QApplication.instance().setStyleSheet(qss)
        if hasattr(main_window, "sidebar"):
            main_window.sidebar.setStyleSheet(_build_sidebar_qss(t))
        self._fix_tab_content_backgrounds(main_window, t)
        try:
            hwnd = int(main_window.winId())
            _set_titlebar_theme(hwnd, t.titlebar_dark)
        except Exception:
            pass

    def _fix_tab_content_backgrounds(self, widget, t: Theme):
        bg = t.bg
        for tab_widget in widget.findChildren(QTabWidget):
            tab_widget.setStyleSheet(
                tab_widget.styleSheet()
                + f"\nQTabWidget::pane {{ background-color: {bg}; }}"
                + f"\nQTabWidget > QWidget {{ background-color: {bg}; }}"
            )
            for i in range(tab_widget.count()):
                page = tab_widget.widget(i)
                if page:
                    page.setStyleSheet(
                        page.styleSheet()
                        + f"\nQWidget {{ background-color: {bg}; }}"
                    )

    def _load(self) -> ThemeType | None:
        try:
            if os.path.exists(THEME_CONFIG):
                with open(THEME_CONFIG, "r") as f:
                    data = json.load(f)
                return ThemeType(data.get("theme", "black"))
        except Exception:
            pass
        return None

    def _save(self, theme_type: ThemeType):
        try:
            os.makedirs(os.path.dirname(THEME_CONFIG), exist_ok=True)
            with open(THEME_CONFIG, "w") as f:
                json.dump({"theme": theme_type.value}, f)
        except Exception:
            pass


def apply_palette(t: Theme):
    qapp = QApplication.instance()
    if qapp:
        qapp.setPalette(_build_palette(t))


theme_manager = ThemeManager()
