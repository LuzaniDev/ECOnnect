from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QFrame,
)
from frontend.app.widgets.table import StyledTable
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.widgets.history_dialog import HistoryDialog
from frontend.app.api import request_api
from frontend.app.core.logger import logger


STATUS_MAP = {
    "pending": "Pendente",
    "sent": "Enviado",
    "cancelled": "Cancelado",
}

STATUS_COLORS = {
    "pending": "#f8891d",
    "sent": "#22c55e",
    "cancelled": "#ef4444",
}


class RequestEditDialog(QDialog):
    def __init__(self, request_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Requisição")
        self.setMinimumWidth(500)
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
        form = QFormLayout()
        form.setSpacing(10)

        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background-color: #141d32; border: 1px solid #1e2d4a; "
            "border-radius: 8px; padding: 16px; }"
        )
        info_layout = QVBoxLayout(info_frame)

        info = QLabel(
            f"Template: {request_data.get('template_name', '')}\n"
            f"Telefone: {request_data.get('client_phone', '')}\n"
            f"Tag: {request_data.get('tag') or '—'}  |  "
            f"Status: {STATUS_MAP.get(request_data.get('status', ''), request_data.get('status', ''))}"
        )
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        info.setWordWrap(True)
        info_layout.addWidget(info)
        form.addRow(info_frame)

        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("https://wa.me/...")
        self.link_input.setText(request_data.get("link") or "")
        form.addRow("Link da mensagem:", self.link_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {"link": self.link_input.text().strip() or None}


class RequestListView(QWidget):
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
        title = QLabel("Requisições")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #f1f5f9; ")
        header.addWidget(title)
        header.addStretch()

        filter_label = QLabel("Filtrar:")
        filter_label.setStyleSheet("font-size: 12px; color: #64748b;")
        header.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todas", "Pendentes", "Enviadas", "Canceladas"])
        self.filter_combo.currentTextChanged.connect(self._filter_changed)
        header.addWidget(self.filter_combo)

        self.btn_history = QPushButton("Histórico")
        self.btn_history.setVisible(False)
        self.btn_history.clicked.connect(self._show_history)
        header.addWidget(self.btn_history)

        self.btn_edit = QPushButton("Editar Link")
        self.btn_edit.setVisible(False)
        self.btn_edit.clicked.connect(self._edit_selected)
        header.addWidget(self.btn_edit)

        self.btn_send = QPushButton("Enviar")
        self.btn_send.setProperty("accent", True)
        self.btn_send.setStyleSheet("font-weight: 600;")
        self.btn_send.setVisible(False)
        self.btn_send.clicked.connect(self._send_selected)
        header.addWidget(self.btn_send)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("danger", True)
        self.btn_cancel.setStyleSheet("QPushButton[danger=true] { font-weight: 600; }")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_selected)
        header.addWidget(self.btn_cancel)

        layout.addLayout(header)

        self.table = StyledTable(
            ["Template", "Telefone", "Tag", "Status", "Criado por", "Data"]
        )
        self.table.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self.table)

    def _load_requests(self, status_filter: str = None):
        api_status = None
        if status_filter == "Pendentes":
            api_status = "pending"
        elif status_filter == "Enviadas":
            api_status = "sent"
        elif status_filter == "Canceladas":
            api_status = "cancelled"

        run_in_thread(
            request_api.list_requests,
            self._on_requests,
            lambda e: show_error(self, "Erro", str(e)),
            api_status,
        )

    def _on_requests(self, requests: list):
        self.table.clear_all()
        for r in requests:
            template_name = r.get("template_name", "")
            if isinstance(r.get("template"), dict):
                template_name = r["template"].get("name", "")

            creator_name = r.get("created_by_username", "")
            if isinstance(r.get("creator"), dict):
                creator_name = r["creator"].get("username", "")

            status_label = STATUS_MAP.get(r["status"], r["status"])
            tag = r.get("tag") or "—"
            created_at = (r.get("created_at") or "")[:10]

            self.table.add_row(
                [
                    template_name,
                    r.get("client_phone", ""),
                    tag,
                    status_label,
                    creator_name,
                    created_at,
                ],
                {"data": r, "status_color": STATUS_COLORS.get(r["status"], "#64748b")},
            )

    def _on_selection(self):
        data = self.table.selected_data()
        has_selection = data is not None
        req_data = data.get("data") if data else None
        is_pending = bool(req_data and req_data.get("status") == "pending")
        self.btn_send.setVisible(is_pending)
        self.btn_cancel.setVisible(is_pending)
        self.btn_history.setVisible(has_selection)
        self.btn_edit.setVisible(has_selection)

    def _edit_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        req_data = data.get("data")
        dialog = RequestEditDialog(req_data, self)
        if dialog.exec() == QDialog.Accepted:
            update_data = dialog.get_data()
            run_in_thread(
                request_api.update_request_link,
                lambda r: (
                    show_success(self, "OK", "Link atualizado!"),
                    self._load_requests(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                req_data["id"],
                update_data["link"],
            )

    def _show_history(self):
        data = self.table.selected_data()
        if not data:
            return
        req_data = data.get("data")
        phone = req_data.get("client_phone", "")
        if not phone:
            return

        self.btn_history.setEnabled(False)
        run_in_thread(
            request_api.get_history_by_phone,
            lambda result: self._on_history(phone, result),
            lambda e: (
                show_error(self, "Erro", str(e)),
                self.btn_history.setEnabled(True),
            ),
            phone,
        )

    def _on_history(self, phone: str, requests: list):
        self.btn_history.setEnabled(True)
        dialog = HistoryDialog(phone, requests, self)
        dialog.exec()

    def _filter_changed(self, text: str):
        if text == "Todas":
            self._load_requests()
        else:
            self._load_requests(text)

    def _send_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        req_data = data.get("data")
        logger.info("REQ_LIST", "Solicitando envio de requisição", request_id=str(req_data.get("id", ""))[:8])
        confirm = show_confirm(self, "Confirmar", "Enviar esta requisição?")
        if confirm:
            logger.info("REQ_LIST", "Envio confirmado", request_id=str(req_data.get("id", ""))[:8])
            run_in_thread(
                request_api.send_request,
                lambda r: (
                    logger.info("REQ_LIST", "Requisição enviada com sucesso"),
                    show_success(self, "OK", "Requisição enviada!"),
                    self._load_requests(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                req_data["id"],
            )

    def _cancel_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        req_data = data.get("data")
        logger.warning("REQ_LIST", "Solicitando cancelamento de requisição", request_id=str(req_data.get("id", ""))[:8])
        confirm = show_confirm(self, "Confirmar", "Cancelar esta requisição?")
        if confirm:
            logger.info("REQ_LIST", "Cancelamento confirmado", request_id=str(req_data.get("id", ""))[:8])
            run_in_thread(
                request_api.cancel_request,
                lambda r: (
                    logger.info("REQ_LIST", "Requisição cancelada com sucesso"),
                    show_success(self, "OK", "Requisição cancelada!"),
                    self._load_requests(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                req_data["id"],
            )

    def refresh(self):
        self._load_requests()
