import os
import sys
import ctypes
from ctypes import wintypes
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QApplication,
    QLabel,
    QPushButton,
    QFrame,
    QSizeGrip,
)

WM_NCHITTEST = 0x0084
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_UP = 0x26
VK_DOWN = 0x28

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_size_t, ctypes.c_longlong)

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_uint32),
        ("scanCode", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_void_p),
    ]
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
from frontend.app.api.client import client
from frontend.app.views.settings import UserSettingsView
from frontend.app.views.mundo_bots import MundoBotsView
from frontend.app.views.dashboard import DashboardView
from frontend.app.views.requisicoes import RequisicoesView
from frontend.app.views.admin_tabs import AdminTabsView
from frontend.app.views.template_list import TemplateListView
from frontend.app.views.template_form import TemplateFormView
from frontend.app.widgets.sidebar import Sidebar
from frontend.app.widgets.dialogs import show_error
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb
from frontend.app.api.auth_api import eco_login as api_eco_login


FRAMELESS_QSS = """
QMainWindow { background: transparent; }
QFrame#outer_container {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 16px;
}
QLabel#title_bar_label {
    color: #8b949e;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QPushButton#title_bar_close {
    background: transparent;
    color: #8b949e;
    border: none;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 600;
    padding: 2px 8px;
}
QPushButton#title_bar_close:hover {
    background-color: #f85149;
    color: #ffffff;
}
"""


class MainWindow(QMainWindow):
    _resize_margin = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECOnnect — Sistema de Gerenciamento de Mensagens")

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "app_icon.ico"
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.token = None
        self.user = None
        self._log_viewer = None
        self._drag_pos: QPoint | None = None
        self._win_key_state = False
        self._saved_geom = None
        self._hook = None
        self._hook_cb = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.outer = QFrame()
        self.outer.setObjectName("outer_container")
        outer_layout = QVBoxLayout(self.outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.title_bar = self._build_title_bar()
        outer_layout.addWidget(self.title_bar)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        outer_layout.addWidget(self.content_widget, 1)

        grip = QSizeGrip(self.outer)
        grip.setStyleSheet("background: transparent;")
        outer_layout.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)

        self.setCentralWidget(self.outer)
        self.setStyleSheet(FRAMELESS_QSS)

        self._show_login()

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("title_bar")
        bar.setFixedHeight(36)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(8)

        icon_label = QLabel()
        assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        icon_candidates = ["logo_16.png", "logo_32.png", "app_icon.ico"]
        icon_path = ""
        for name in icon_candidates:
            p = os.path.join(assets, name)
            if os.path.exists(p):
                icon_path = p
                break
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)

        title = QLabel("ECOnnect")
        title.setObjectName("title_bar_label")
        layout.addWidget(title)

        layout.addStretch()

        btn_close = QPushButton("\u2715")
        btn_close.setObjectName("title_bar_close")
        btn_close.setFixedSize(32, 24)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return bar

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if pos.y() <= self.title_bar.height() and pos.x() < self.width() - 40:
                self._drag_pos = event.globalPosition().toPoint()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _install_keyboard_hook(self):
        try:
            module = ctypes.windll.kernel32.GetModuleHandleW(None)

            def _proc(nCode, wParam, lParam):
                if nCode >= 0:
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if kb.vkCode in (VK_LWIN, VK_RWIN):
                        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            self._win_key_state = True
                        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                            self._win_key_state = False
                    elif self._win_key_state and wParam == WM_KEYDOWN:
                        if kb.vkCode == VK_UP:
                            QTimer.singleShot(0, self._toggle_maximize)
                            return 1
                        elif kb.vkCode == VK_DOWN:
                            QTimer.singleShot(0, self._handle_win_down)
                            return 1
                return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

            cb = HOOKPROC(_proc)
            self._hook_cb = cb
            self._hook = ctypes.windll.user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, cb, module, 0
            )
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if self._hook is None:
            self._install_keyboard_hook()

    def closeEvent(self, event):
        if self._hook:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
        super().closeEvent(event)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_NCHITTEST:
                packed = msg.lParam & 0xFFFFFFFF
                x = packed & 0xFFFF
                y = (packed >> 16) & 0xFFFF

                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(msg.hWnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top

                r = self._resize_margin
                on_left = x - rect.left <= r
                on_right = rect.right - x <= r
                on_top = y - rect.top <= r
                on_bottom = rect.bottom - y <= r

                if on_top and on_left:
                    return True, HTTOPLEFT
                if on_top and on_right:
                    return True, HTTOPRIGHT
                if on_bottom and on_left:
                    return True, HTBOTTOMLEFT
                if on_bottom and on_right:
                    return True, HTBOTTOMRIGHT
                if on_left:
                    return True, HTLEFT
                if on_right:
                    return True, HTRIGHT
                if on_top:
                    return True, HTTOP
                if on_bottom:
                    return True, HTBOTTOM
        return QMainWindow.nativeEvent(self, eventType, message)

    def _toggle_maximize(self):
        if self._saved_geom is None:
            self._saved_geom = self.geometry()
        if self.isMaximized():
            self.showNormal()
            if self._saved_geom:
                self.setGeometry(self._saved_geom)
        else:
            self._saved_geom = self.geometry()
            self.showMaximized()

    def _handle_win_down(self):
        if self.isMaximized():
            self.showNormal()
            if self._saved_geom:
                self.setGeometry(self._saved_geom)
        else:
            self.showMinimized()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_login(self):
        from frontend.app.views.login import LoginView

        self._clear_content()

        self.login_view = LoginView()
        self.login_view.login_successful.connect(self._autenticar)
        self.content_layout.addWidget(self.login_view)

        self.setMaximumSize(16777215, 16777215)
        self.adjustSize()

    def _autenticar(self, dados_eco: dict):
        logger.info("APP", "ECO autenticado, obtendo token via API",
                    usuario=dados_eco["eco_usuario"], role=dados_eco["role"])

        try:
            result = api_eco_login(
                dados_eco["eco_usuario"],
                dados_eco["eco_empresa"],
                dados_eco["role"],
            )
            self.token = result["access_token"]
            client.set_token(self.token)

            me = client.get("/api/auth/me").json()
            self.user = me
            logger.info("APP", "Usuário logado com sucesso",
                        usuario=me["username"], role=me["role"])

            self._load_fb_config(dados_eco["eco_empresa"])

        except Exception as e:
            logger.error("APP", "Falha ao obter token da API", erro=str(e))
            show_error(
                self,
                "Erro de Autenticação",
                f"Não foi possível autenticar no sistema ECOnnect.\n\nDetalhes: {e}",
            )
            self.login_view.btn_entrar.setEnabled(True)
            self.login_view.btn_entrar.setText("Entrar no ECOnnect")
            return

        self.setMinimumSize(900, 600)
        self.resize(1200, 800)

        self._show_main()

    def _show_main(self):
        self._clear_content()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        permitted_tabs = self.user.get("tab_permissions")
        self.sidebar = Sidebar(
            self.user["username"], self.user["role"], permitted_tabs
        )
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.dashboard = DashboardView(self.token, self.user)
        self.user_settings = UserSettingsView(self.token, self.user)
        self.mundo_bots = MundoBotsView(self.token, self.user)
        self.requisicoes = RequisicoesView(self.token, self.user)
        self.admin_tabs = AdminTabsView(self.token, self.user)
        self.template_list = TemplateListView(self.token, self.user)
        self.template_form = TemplateFormView(self.token, self.user)

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.user_settings)
        self.stack.addWidget(self.mundo_bots)
        self.stack.addWidget(self.requisicoes)
        self.stack.addWidget(self.admin_tabs)
        self.stack.addWidget(self.template_list)
        self.stack.addWidget(self.template_form)

        self.sidebar.nav_dashboard.connect(self._show_dashboard)
        self.sidebar.nav_settings.connect(self._show_settings)
        self.sidebar.nav_mundo_bots.connect(self._show_mundo_bots)
        self.sidebar.nav_requisicoes.connect(self._show_requisicoes)
        self.sidebar.nav_templates.connect(self._show_templates)
        self.sidebar.nav_admin_tabs.connect(self._show_admin_tabs)
        self.sidebar.nav_logs.connect(self._open_log_viewer)
        self.sidebar.nav_logout.connect(self._sair)

        self.template_list.navigate_to_form.connect(self._show_template_form)
        self.template_form.saved.connect(self._show_templates)

        self.content_layout.addWidget(central)
        self._show_dashboard()

    def _show_dashboard(self):
        self.stack.setCurrentWidget(self.dashboard)
        self.dashboard.refresh()

    def _show_settings(self):
        self.stack.setCurrentWidget(self.user_settings)
        self.user_settings.refresh()

    def _show_mundo_bots(self):
        self.stack.setCurrentWidget(self.mundo_bots)
        self.mundo_bots.refresh()

    def _show_requisicoes(self):
        self.stack.setCurrentWidget(self.requisicoes)
        self.requisicoes.refresh()

    def _show_admin_tabs(self):
        self.stack.setCurrentWidget(self.admin_tabs)
        self.admin_tabs.refresh()

    def _show_templates(self):
        self.stack.setCurrentWidget(self.template_list)
        self.template_list.refresh()

    def _show_template_form(self, data: dict | None):
        self.template_form.load_template(data)
        self.stack.setCurrentWidget(self.template_form)

    def _open_log_viewer(self):
        if not hasattr(self, "_log_viewer") or self._log_viewer is None:
            from frontend.app.widgets.log_viewer import LogViewerWindow
            self._log_viewer = LogViewerWindow(self)
            self._log_viewer.destroyed.connect(lambda: setattr(self, "_log_viewer", None))
        self._log_viewer.show()
        self._log_viewer.raise_()
        self._log_viewer.activateWindow()

    def _load_fb_config(self, eco_empresa: str):
        try:
            from frontend.app.api.company_config_api import get_company_config
            config = get_company_config(eco_empresa)
            fb.configure(
                dsn=config["fb_database"],
                user=config["fb_user"],
                password=config["fb_password"],
            )
            logger.info("APP", "Configuracao Firebird carregada do backend",
                        empresa=eco_empresa, database=config["fb_database"])
        except Exception:
            logger.info("APP", "Usando configuracao Firebird padrao (.env)")

    def _sair(self):
        logger.info("APP", "Usuário solicitou sair")
        client.clear_token()
        if hasattr(self, "user_settings") and self.user_settings:
            self.user_settings.deleteLater()
        self._show_login()
