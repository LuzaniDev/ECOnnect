from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QStackedWidget
from frontend.app.views.meta_credentials import MetaCredentialsView
from frontend.app.views.template_list import TemplateListView
from frontend.app.views.template_form import TemplateFormView
from frontend.app.views.request_form import RequestFormView
from frontend.app.views.ecochat_view import ECOchatView
from frontend.app.views.whatsweb_view import WhatsWebView
from frontend.app.core.theme import theme_manager


class MetaView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._setup_ui()

    def _setup_ui(self):
        t = theme_manager.current()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: {t.bg}; border: none; }}
            QTabBar::tab {{
                background: transparent; color: {t.text_secondary}; border: none;
                padding: 10px 24px; font-size: 13px; font-weight: 500;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{ color: {t.accent_blue}; border-bottom: 2px solid {t.accent_blue}; }}
            QTabBar::tab:hover {{ color: {t.text}; }}
        """)

        self.creds_view = MetaCredentialsView()
        self._build_templates_tab()
        self.send_view = RequestFormView(self.token, self.user, use_meta_api=True)
        self.ecochat_view = ECOchatView()
        self.whatsweb_view = WhatsWebView()

        self.tabs.addTab(self.creds_view, "Credenciais")
        self.tabs.addTab(self.template_container, "Templates")
        self.tabs.addTab(self.send_view, "Enviar")
        self.tabs.addTab(self.ecochat_view, "ECOchat")
        self.tabs.addTab(self.whatsweb_view, "WhatsWeb")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _build_templates_tab(self):
        self.template_container = QWidget()
        layout = QVBoxLayout(self.template_container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.template_stack = QStackedWidget()
        layout.addWidget(self.template_stack)

        self.template_list_view = TemplateListView(self.token, self.user)
        self.template_form_view = TemplateFormView(self.token, self.user)

        self.template_stack.addWidget(self.template_list_view)
        self.template_stack.addWidget(self.template_form_view)

        self.template_list_view.navigate_to_form.connect(self._show_template_form)
        self.template_form_view.saved.connect(self._show_template_list)

    def _show_template_form(self, data: dict | None):
        self.template_form_view.load_template(data)
        self.template_stack.setCurrentWidget(self.template_form_view)

    def _show_template_list(self):
        self.template_stack.setCurrentWidget(self.template_list_view)
        self.template_list_view.refresh()

    def refresh(self):
        idx = self.tabs.currentIndex()
        self._on_tab_changed(idx)

    def _on_tab_changed(self, idx: int):
        if idx == 0:
            self.creds_view.refresh()
        elif idx == 1:
            self.template_list_view.refresh()
        elif idx == 2:
            self.send_view.refresh()
        elif idx == 3:
            self.ecochat_view.refresh()
