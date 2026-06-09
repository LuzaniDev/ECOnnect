from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QDialogButtonBox,
    QFrame,
)
from frontend.app.widgets.table import StyledTable
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.api import user_api
from frontend.app.core.logger import logger


class UserEditDialog(QDialog):
    def __init__(self, user_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Usuário")
        self.setMinimumWidth(450)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0a1220;
                color: #f1f5f9;
            }
            QLabel { color: #f1f5f9; }
        """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #141d32; border: 1px solid #1e2d4a; "
            "border-radius: 8px; padding: 16px; }"
        )
        header_layout = QHBoxLayout(header)

        avatar = QLabel(user_data.get("username", "U")[0].upper())
        avatar.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: #014998; "
            "background-color: rgba(1, 73, 152, 0.15); "
            "border-radius: 20px; padding: 6px 14px;"
        )
        header_layout.addWidget(avatar)

        info = QLabel(
            f'<b style="color:#f1f5f9;">{user_data.get("username", "")}</b><br>'
            f'<span style="color:#64748b;">{user_data.get("email", "")}</span>'
        )
        info.setTextFormat(Qt.RichText)
        header_layout.addWidget(info)
        header_layout.addStretch()

        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)

        self.email_input = QLineEdit(user_data.get("email", ""))
        form.addRow("Email:", self.email_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        self.role_combo.setCurrentText(user_data.get("role", "user"))
        form.addRow("Função:", self.role_combo)

        self.active_check = QCheckBox()
        self.active_check.setChecked(user_data.get("is_active", True))
        form.addRow("Ativo:", self.active_check)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 720)
        self.cooldown_spin.setSuffix(" horas")
        self.cooldown_spin.setValue(user_data.get("cobranca_cooldown_hours", 48))
        form.addRow("Cooldown cobrança:", self.cooldown_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "email": self.email_input.text().strip(),
            "role": self.role_combo.currentText(),
            "is_active": self.active_check.isChecked(),
            "cobranca_cooldown_hours": self.cooldown_spin.value(),
        }


class AdminUsersView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Gerenciar Usuários")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #f1f5f9; ")
        header.addWidget(title)
        header.addStretch()

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.setVisible(False)
        self.btn_edit.clicked.connect(self._edit_selected)
        header.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setProperty("danger", True)
        self.btn_delete.setStyleSheet("QPushButton[danger=true] { }")
        self.btn_delete.setVisible(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        header.addWidget(self.btn_delete)

        layout.addLayout(header)

        self.table = StyledTable(
            ["Usuário", "Email", "Função", "Ativo", "Cooldown", "Criado em"]
        )
        self.table.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self.table)

    def _load_users(self):
        run_in_thread(
            user_api.list_users,
            self._on_users,
            lambda e: show_error(self, "Erro", str(e)),
        )

    def _on_users(self, users: list):
        self.table.clear_all()
        for u in users:
            self.table.add_row(
                [
                    u["username"],
                    u["email"],
                    "Admin" if u["role"] == "admin" else "Usuário",
                    "Sim" if u["is_active"] else "Não",
                    f'{u.get("cobranca_cooldown_hours", 48)}h',
                    (u.get("created_at") or "")[:10],
                ],
                u,
            )

    def _on_selection(self):
        has_selection = self.table.selected_data() is not None
        self.btn_edit.setVisible(has_selection)
        self.btn_delete.setVisible(has_selection)

    def _edit_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        logger.info("ADMIN_USERS", "Editando usuário", username=data["username"], user_id=str(data.get("id", ""))[:8])
        dialog = UserEditDialog(data, self)
        if dialog.exec() == QDialog.Accepted:
            update_data = dialog.get_data()
            logger.info("ADMIN_USERS", "Salvando alterações de usuário", username=data["username"], update=update_data)
            run_in_thread(
                user_api.update_user,
                lambda r: (
                    logger.info("ADMIN_USERS", "Usuário atualizado com sucesso", username=r.get("username")),
                    show_success(self, "OK", "Usuário atualizado!"),
                    self._load_users(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data["id"],
                update_data,
            )

    def _delete_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        if data["id"] == self.user["id"]:
            logger.warning("ADMIN_USERS", "Tentativa de auto-exclusão")
            show_error(self, "Erro", "Você não pode excluir a si mesmo.")
            return
        logger.warning("ADMIN_USERS", "Solicitando exclusão de usuário", username=data["username"])
        confirm = show_confirm(
            self, "Confirmar", f'Excluir usuário "{data["username"]}"?'
        )
        if confirm:
            logger.info("ADMIN_USERS", "Exclusão confirmada", username=data["username"])
            run_in_thread(
                user_api.delete_user,
                lambda r: (
                    logger.info("ADMIN_USERS", "Usuário excluído com sucesso"),
                    show_success(self, "OK", "Usuário excluído!"),
                    self._load_users(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data["id"],
            )

    def refresh(self):
        self._load_users()
