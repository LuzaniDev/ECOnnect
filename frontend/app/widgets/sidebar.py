import os
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QHBoxLayout,
)



SIDEBAR_STYLE = ""

ALL_TABS = {
    "dashboard": {"label": "Dashboard", "group": "Navegação"},
    "requisicoes": {"label": "Requisições", "group": "Requisições"},
    "mundo_bots": {"label": "Mundo dos Bots", "group": "Mundo dos Bots"},
    "meta": {"label": "Meta", "group": "Meta"},
    "configuracoes": {"label": "Configurações", "group": "Administração"},
    "admin_tabs": {"label": "Gerenciar Abas", "group": "Administração"},
    "logs": {"label": "Logs do Sistema", "group": "Administração"},
}


class Sidebar(QFrame):
    nav_dashboard = Signal()
    nav_requisicoes = Signal()
    nav_meta = Signal()
    nav_mundo_bots = Signal()
    nav_settings = Signal()
    nav_logout = Signal()
    nav_logs = Signal()
    nav_admin_tabs = Signal()


    def __init__(self, username: str, role: str, permitted_tabs: list[str] | None = None):
        super().__init__()
        self.setObjectName("sidebar")
        self._build_ui(username, role, permitted_tabs)

    def _build_ui(self, username: str, role: str, permitted_tabs: list[str] | None = None):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 14, 12, 10)
        header.setSpacing(8)

        logo_label = QLabel()
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "brand_mark.png"
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setFixedSize(28, 28)
        else:
            logo_label.setText("EC")
            logo_label.setStyleSheet("font-size: 16px; font-weight: 800;")
        header.addWidget(logo_label)

        brand_wrapper = QVBoxLayout()
        brand_wrapper.setSpacing(0)
        brand_name = QLabel("ECOnnect")
        brand_name.setObjectName("brand_name")
        brand_wrapper.addWidget(brand_name)
        brand_sub = QLabel("Sistema de Mensagens")
        brand_sub.setObjectName("brand_sub")
        brand_wrapper.addWidget(brand_sub)
        header.addLayout(brand_wrapper)
        header.addStretch()

        layout.addLayout(header)

        user_info = QLabel(f"{username}")
        user_info.setObjectName("user_info")
        layout.addWidget(user_info)

        role_map = {"admin": "Administrador", "user": "Usuario"}
        role_label = QLabel(role_map.get(role, role))
        role_label.setObjectName("user_role")
        layout.addWidget(role_label)

        layout.addSpacing(16)

        is_admin = role == "admin"

        nav_items = [
            ("dashboard", self.nav_dashboard),
            ("requisicoes", self.nav_requisicoes),
            ("meta", self.nav_meta),
            ("mundo_bots", self.nav_mundo_bots),
        ]
        if is_admin:
            nav_items.append(("configuracoes", self.nav_settings))
            nav_items.append(("logs", self.nav_logs))
            nav_items.append(("admin_tabs", self.nav_admin_tabs))

        tab_perms = set(permitted_tabs or []) if not is_admin else None

        current_group = None
        for key, signal in nav_items:
            if tab_perms is not None and key not in tab_perms:
                continue

            info = ALL_TABS.get(key, {})
            group = info.get("group")

            if group != current_group:
                if current_group is not None:
                    sep = QFrame()
                    sep.setObjectName("cat_separator")
                    sep.setFrameShape(QFrame.HLine)
                    layout.addWidget(sep)
                    layout.addSpacing(10)
                current_group = group
                if group:
                    group_label = QLabel(group)
                    group_label.setObjectName("nav_group")
                    layout.addWidget(group_label)

            btn = self._make_button(
                info.get("label", key), f"nav_{key}_btn", signal
            )
            layout.addWidget(btn)

        layout.addStretch()

        btn_logout = self._make_button(
            "Sair", "logout_btn", self.nav_logout
        )
        layout.addWidget(btn_logout)

    def _make_button(self, text: str, obj_name: str, signal: Signal) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(signal.emit)
        return btn
