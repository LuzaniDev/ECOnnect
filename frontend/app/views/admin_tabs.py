from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFrame, QMessageBox,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.api import user_api
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager, _hex_to_rgb


ALL_TAB_OPTIONS = [
    ("dashboard", "Dashboard"),
    ("requisicoes", "Requisições"),
    ("templates", "Modelos"),
    ("mundo_bots", "Mundo dos Bots / Cobrança"),
]


class AdminTabsView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._users_data = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Gerenciar Abas — Permissões por Usuário")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setProperty("ghost", True)
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        desc = QLabel(
            "Marque ou desmarque as abas que cada usuário pode visualizar. "
            "Administradores sempre veem todas as abas."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; padding-bottom: 8px;")
        layout.addWidget(desc)

        self.table = QTableWidget()
        col_count = 1 + len(ALL_TAB_OPTIONS)
        self.table.setColumnCount(col_count)
        headers = ["Usuário"] + [label for _, label in ALL_TAB_OPTIONS]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, col_count):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        t = theme_manager.current()
        self.table.setStyleSheet(f"""
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background-color: rgba({_hex_to_rgb(t.primary)},0.15); }}
        """)
        layout.addWidget(self.table, 1)

        btn_save = QPushButton("Salvar Permissões")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setProperty("primary", True)
        btn_save.clicked.connect(self._salvar)
        layout.addWidget(btn_save)

        self.refresh()

    def refresh(self):
        run_in_thread(
            self._list_users,
            self._on_users,
            lambda e: show_error(self, "Erro", str(e)),
        )

    def _list_users(self) -> list:
        return user_api.list_users()

    def _on_users(self, users: list):
        self._users_data = users
        self.table.setRowCount(0)
        for u in users:
            if u.get("role") == "admin":
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(f"{u.get('username', '')} ({u.get('eco_empresa', '')})")
            name_item.setData(Qt.UserRole, u.get("id"))
            self.table.setItem(row, 0, name_item)

            current_perms = u.get("tab_permissions") or []
            for col_idx, (tab_key, _) in enumerate(ALL_TAB_OPTIONS):
                cb = QCheckBox()
                cb.setChecked(tab_key in current_perms)
                cb.setData(Qt.UserRole, tab_key)
                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.setAlignment(Qt.AlignCenter)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.addWidget(cb)
                self.table.setCellWidget(row, col_idx + 1, cb_widget)

    def _salvar(self):
        for row in range(self.table.rowCount()):
            user_id = self.table.item(row, 0).data(Qt.UserRole)
            if not user_id:
                continue
            enabled = []
            for col_idx, (tab_key, _) in enumerate(ALL_TAB_OPTIONS):
                w = self.table.cellWidget(row, col_idx + 1)
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb and cb.isChecked():
                        enabled.append(tab_key)
            try:
                user_api.update_user_permissions(user_id, enabled)
            except Exception as e:
                show_error(self, "Erro", f"Falha ao salvar permissões do usuário {user_id}: {e}")
                return
        show_success(self, "OK", "Permissões salvas com sucesso!")
        logger.info("ADMIN", "Permissoes de abas atualizadas")
