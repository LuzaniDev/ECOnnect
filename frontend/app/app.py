import os
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
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
from frontend.app.views.requisicoes import RequisicoesView
from frontend.app.views.admin_tabs import AdminTabsView
from frontend.app.views.template_list import TemplateListView
from frontend.app.views.template_form import TemplateFormView
from frontend.app.views.meta_view import MetaView
from frontend.app.views.data_pipeline import DataPipelineView
from frontend.app.widgets.sidebar import Sidebar
from frontend.app.widgets.dialogs import show_error
from frontend.app.widgets.loading_overlay import LoadingOverlay
from frontend.app.widgets.worker import run_in_thread
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb
from frontend.app.core.theme import theme_manager, Theme, _build_sidebar_qss
from frontend.app.api.auth_api import eco_login as api_eco_login


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

        self.outer = QFrame()
        self.outer.setObjectName("outer_container")
        outer_layout = QVBoxLayout(self.outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        outer_layout.addWidget(self.content_widget, 1)

        self.setCentralWidget(self.outer)

        self._setup_theme()
        self._show_login()

    def _setup_theme(self):
        theme_manager.apply_theme(self)
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        theme_manager.apply_theme(self)
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'refresh_theme') and callable(widget.refresh_theme):
                widget.refresh_theme()

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

        self._show_loading_overlay()
        self._start_initial_scan()

    def _show_loading_overlay(self):
        self._clear_content()
        self._loading_overlay = LoadingOverlay(self)
        self._loading_overlay.set_indeterminate("Preparando processamento de boletos...")
        self.content_layout.addWidget(self._loading_overlay)
        self._loading_overlay.show()
        QApplication.processEvents()

    def _hide_loading_overlay(self):
        if hasattr(self, "_loading_overlay") and self._loading_overlay:
            self._loading_overlay.hide()
            self._loading_overlay.deleteLater()
            self._loading_overlay = None

    def _start_initial_scan(self):
        logger.info("APP", "Iniciando scan inicial de boletos...")
        total = 0
        try:
            from frontend.app.services.boleto_watcher import executar_scan_completo
            total = executar_scan_completo()
            logger.info("APP", f"Scan inicial concluido: {total} boletos processados")
        except Exception as e:
            logger.error("APP", f"Erro no scan inicial de boletos: {e}")
            import traceback
            logger.error("APP", traceback.format_exc())

        if hasattr(self, "_loading_overlay") and self._loading_overlay:
            self._loading_overlay.set_indeterminate(f"{total} boletos processados" if total else "Nenhum boleto pendente")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, self._pos_scan)

    def _pos_scan(self):
        self._hide_loading_overlay()
        self._init_watcher()
        self._show_main()
        # Verifica jobs perdidos enquanto estava offline
        try:
            if hasattr(self, "mundo_bots") and self.mundo_bots:
                self.mundo_bots._check_missed_jobs()
        except Exception:
            pass

    def _init_watcher(self):
        try:
            from frontend.app.services.boleto_watcher import BoletoWatcher
            self._boleto_watcher = BoletoWatcher()
            self._boleto_watcher.start()
            logger.info("APP", "BoletoWatcher (watchdog) iniciado")
        except Exception as e:
            logger.error("APP", f"Erro ao iniciar BoletoWatcher: {e}")

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
        self.sidebar.setStyleSheet(_build_sidebar_qss(theme_manager.current()))
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.dashboard = DashboardView(self.token, self.user)
        self.user_settings = UserSettingsView(self.token, self.user)
        self.mundo_bots = MundoBotsView(self.token, self.user)
        self.requisicoes = RequisicoesView(self.token, self.user)
        self.admin_tabs = AdminTabsView(self.token, self.user)
        self.meta = MetaView(self.token, self.user)
        self.template_list = TemplateListView(self.token, self.user)
        self.template_form = TemplateFormView(self.token, self.user)
        self.data_pipeline = DataPipelineView()

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.user_settings)
        self.stack.addWidget(self.mundo_bots)
        self.stack.addWidget(self.requisicoes)
        self.stack.addWidget(self.meta)
        self.stack.addWidget(self.admin_tabs)
        self.stack.addWidget(self.template_list)
        self.stack.addWidget(self.template_form)
        self.stack.addWidget(self.data_pipeline)

        self.sidebar.nav_dashboard.connect(self._show_dashboard)
        self.sidebar.nav_settings.connect(self._show_settings)
        self.sidebar.nav_mundo_bots.connect(self._show_mundo_bots)
        self.sidebar.nav_requisicoes.connect(self._show_requisicoes)
        self.sidebar.nav_meta.connect(self._show_meta)
        self.sidebar.nav_admin_tabs.connect(self._show_admin_tabs)
        self.sidebar.nav_data_pipeline.connect(self._show_data_pipeline)
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

    def _show_data_pipeline(self):
        self.stack.setCurrentWidget(self.data_pipeline)
        self.data_pipeline.refresh()

    def _show_templates(self):
        self.stack.setCurrentWidget(self.template_list)
        self.template_list.refresh()

    def _show_template_form(self, data: dict | None):
        self.template_form.load_template(data)
        self.stack.setCurrentWidget(self.template_form)

    def _show_meta(self):
        self.stack.setCurrentWidget(self.meta)
        self.meta.refresh()

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
