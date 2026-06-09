import os
import sys
from PySide6.QtCore import Qt, QPoint
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
)
from frontend.app.api.client import client
from frontend.app.views.settings import UserSettingsView
from frontend.app.views.mundo_bots import MundoBotsView
from frontend.app.views.dashboard import DashboardView
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

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

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

        self.sidebar = Sidebar(self.user["username"], self.user["role"])
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.dashboard = DashboardView(self.token, self.user)
        self.user_settings = UserSettingsView(self.token, self.user)
        self.mundo_bots = MundoBotsView(self.token, self.user)

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.user_settings)
        self.stack.addWidget(self.mundo_bots)

        self.sidebar.nav_dashboard.connect(self._show_dashboard)
        self.sidebar.nav_settings.connect(self._show_settings)
        self.sidebar.nav_mundo_bots.connect(self._show_mundo_bots)
        self.sidebar.nav_logs.connect(self._open_log_viewer)
        self.sidebar.nav_logout.connect(self._sair)

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
        sys.exit(0)
