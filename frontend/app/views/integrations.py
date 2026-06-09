from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QFrame,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QCheckBox,
    QSplitter,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.api import integration_api
from frontend.app.core.logger import logger
import httpx
import json


HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


class IntegrationDialog(QDialog):
    def __init__(self, data: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova Integração" if not data else "Editar Integração")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self._data = data
        self.setStyleSheet("""
            QDialog { background-color: #0a1220; color: #f1f5f9; }
            QLabel { color: #f1f5f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex: Meta WhatsApp Business")
        if data:
            self.name_input.setText(data.get("name", ""))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.exemplo.com/v1/messages")
        if data:
            self.url_input.setText(data.get("url", ""))

        self.method_combo = QComboBox()
        self.method_combo.addItems(HTTP_METHODS)
        if data:
            self.method_combo.setCurrentText(data.get("method", "POST"))

        method_layout = QHBoxLayout()
        method_layout.addWidget(self.method_combo)
        method_layout.addWidget(self.url_input, 1)

        form.addRow("Nome:", self.name_input)
        form.addRow("Endpoint:", method_layout)

        layout.addLayout(form)

        headers_label = QLabel("Headers (um por linha: Chave: Valor)")
        headers_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        layout.addWidget(headers_label)

        self.headers_input = QTextEdit()
        self.headers_input.setPlaceholderText("Content-Type: application/json\nAuthorization: Bearer TOKEN")
        self.headers_input.setMaximumHeight(100)
        self.headers_input.setStyleSheet("""
            QTextEdit {
                background-color: #0d1525;
                border: 1px solid #1e2d4a;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                color: #f1f5f9;
            }
        """)
        if data:
            headers_str = ""
            for k, v in data.get("headers", {}).items():
                headers_str += f"{k}: {v}\n"
            self.headers_input.setPlainText(headers_str)
        layout.addWidget(self.headers_input)

        body_label = QLabel("Body (use {{param}} para placeholders)")
        body_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        layout.addWidget(body_label)

        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText('{\n  "to": "{{phone}}",\n  "template": "{{template_name}}"\n}')
        self.body_input.setStyleSheet("""
            QTextEdit {
                background-color: #0d1525;
                border: 1px solid #1e2d4a;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                color: #f1f5f9;
            }
        """)
        if data:
            self.body_input.setPlainText(data.get("body_template", ""))
        layout.addWidget(self.body_input)

        params_label = QLabel("Parâmetros aceitos (separados por vírgula)")
        params_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        layout.addWidget(params_label)

        self.params_input = QLineEdit()
        self.params_input.setPlaceholderText("phone, template_name, param1, param2")
        if data:
            params_list = data.get("parameters", [])
            if isinstance(params_list, list):
                params_list = ", ".join(params_list)
            self.params_input.setText(params_list)
        layout.addWidget(self.params_input)

        self.active_check = QCheckBox("Integração ativa")
        self.active_check.setChecked(data.get("is_active", True) if data else True)
        layout.addWidget(self.active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        method = self.method_combo.currentText()
        headers_text = self.headers_input.toPlainText()
        body_template = self.body_input.toPlainText()
        params_text = self.params_input.text().strip()
        is_active = self.active_check.isChecked()

        headers = {}
        for line in headers_text.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        parameters = [p.strip() for p in params_text.split(",") if p.strip()]

        return {
            "name": name,
            "url": url,
            "method": method,
            "headers": headers,
            "body_template": body_template,
            "parameters": parameters,
            "is_active": is_active,
        }


class IntegrationTesterDialog(QDialog):
    def __init__(self, integration: dict, parent=None):
        super().__init__(parent)
        self._integration = integration
        self.setWindowTitle(f"Testar: {integration.get('name', 'Integração')}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet("""
            QDialog { background-color: #0a1220; color: #f1f5f9; }
            QLabel { color: #f1f5f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        info_label = QLabel(f"Método: {integration.get('method', 'POST')} | URL: {integration.get('url', '')}")
        info_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info_label)

        params = integration.get("parameters", [])
        self.param_widgets = {}

        if params:
            params_label = QLabel("Parâmetros")
            params_label.setStyleSheet("font-weight: 600;")
            layout.addWidget(params_label)

            for param in params:
                row = QHBoxLayout()
                lbl = QLabel(f"{param}:")
                lbl.setMinimumWidth(100)
                edit = QLineEdit()
                edit.setPlaceholderText(f"Valor para {param}")
                row.addWidget(lbl)
                row.addWidget(edit, 1)
                self.param_widgets[param] = edit
                layout.addLayout(row)
        else:
            no_params = QLabel("Esta integração não requer parâmetros")
            no_params.setStyleSheet("color: #64748b; font-style: italic;")
            layout.addWidget(no_params)

        self.result_label = QLabel("Resultado: Aguardando teste...")
        self.result_label.setStyleSheet("color: #94a3b8; padding: 12px; background-color: #141d32; border-radius: 8px;")
        layout.addWidget(self.result_label)

        self.response_body = QTextEdit()
        self.response_body.setReadOnly(True)
        self.response_body.setStyleSheet("""
            QTextEdit {
                background-color: #0a0f1a;
                border: 1px solid #1e2d4a;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                color: #22c55e;
            }
        """)
        self.response_body.setMaximumHeight(200)
        layout.addWidget(self.response_body)

        btn_test = QPushButton("Enviar Requisição")
        btn_test.setProperty("accent", True)
        btn_test.setStyleSheet("""
            QPushButton[accent="true"] {
                background-color: #014998;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: 700;
            }
            QPushButton[accent="true"]:hover {
                background-color: #025db8;
            }
        """)
        btn_test.clicked.connect(self._send_test)
        layout.addWidget(btn_test)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _send_test(self):
        integration = self._integration
        method = integration.get("method", "POST")
        url = integration.get("url", "")
        headers = integration.get("headers", {})
        body_template = integration.get("body_template", "")

        values = {}
        for param, widget in self.param_widgets.items():
            values[param] = widget.text().strip()

        body_str = body_template
        for param, value in values.items():
            body_str = body_str.replace(f"{{{param}}}", value)

        self.result_label.setText("Enviando...")
        self.result_label.setStyleSheet("color: #f8891d; padding: 12px; background-color: #141d32; border-radius: 8px;")

        def do_request():
            try:
                client = httpx.Client(timeout=30)
                kwargs = {"headers": headers}

                if method in ("POST", "PUT", "PATCH"):
                    try:
                        kwargs["json"] = json.loads(body_str)
                    except:
                        kwargs["data"] = body_str

                response = client.request(method, url, **kwargs)
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "body": response.text,
                }
                client.close()
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}

        import threading
        thread = threading.Thread(target=self._request_thread, args=(do_request,))
        thread.daemon = True
        thread.start()

    def _request_thread(self, func):
        import time
        time.sleep(0.1)
        result = func()
        QTimer.postEvent(self, _IntegrationResultEvent(result))


class _IntegrationResultEvent:
    def __init__(self, result: dict):
        self.result = result


class IntegrationsView(QWidget):
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
        title = QLabel("Integrações")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #f1f5f9;")
        header.addWidget(title)
        header.addStretch()

        self.btn_new = QPushButton("+ Nova Integração")
        self.btn_new.setProperty("accent", True)
        self.btn_new.setStyleSheet("font-weight: 600;")
        self.btn_new.clicked.connect(self._new_integration)
        header.addWidget(self.btn_new)

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.setVisible(False)
        self.btn_edit.clicked.connect(self._edit_selected)
        header.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setProperty("danger", True)
        self.btn_delete.setVisible(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        header.addWidget(self.btn_delete)

        self.btn_test = QPushButton("Testar")
        self.btn_test.setProperty("accent", True)
        self.btn_test.setVisible(False)
        self.btn_test.clicked.connect(self._test_selected)
        header.addWidget(self.btn_test)

        layout.addLayout(header)

        desc = QLabel(
            "Configure integrações com provedores de API para enviar mensagens. "
            "Cada integração define o endpoint, método, headers e body da requisição."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 12px; padding-bottom: 8px;")
        layout.addWidget(desc)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Nome", "Método", "URL", "Parâmetros", "Ativo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.currentItemChanged.connect(self._on_selection)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1525;
                color: #f1f5f9;
                border: 1px solid #1e2d4a;
                border-radius: 10px;
                gridline-color: #1a2640;
                font-size: 13px;
            }
            QTableWidget::item { padding: 10px; }
            QTableWidget::item:selected { background-color: #014998; }
            QHeaderView::section {
                background-color: #0a1220;
                color: #94a3b8;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #014998;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)

    def _load_integrations(self):
        run_in_thread(
            integration_api.list_integrations,
            self._on_integrations,
            lambda e: show_error(self, "Erro", str(e)),
        )

    def _on_integrations(self, integrations: list):
        self.table.setRowCount(0)
        for cfg in integrations:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(cfg.get("name", ""))
            method_item = QTableWidgetItem(cfg.get("method", "POST"))
            url_item = QTableWidgetItem(cfg.get("url", ""))
            params = cfg.get("parameters", [])
            params_str = ", ".join(params) if isinstance(params, list) else str(params)
            params_item = QTableWidgetItem(params_str)
            active_item = QTableWidgetItem("Sim" if cfg.get("is_active") else "Não")

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, method_item)
            self.table.setItem(row, 2, url_item)
            self.table.setItem(row, 3, params_item)
            self.table.setItem(row, 4, active_item)

            for col in range(5):
                self.table.item(row, col).setData(Qt.UserRole, cfg)

    def _on_selection(self):
        has_selection = self.table.currentRow() >= 0
        self.btn_edit.setVisible(has_selection)
        self.btn_delete.setVisible(has_selection)
        self.btn_test.setVisible(has_selection)

    def _get_selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        return None

    def _new_integration(self):
        dialog = IntegrationDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["name"] or not data["url"]:
                show_error(self, "Erro", "Nome e URL são obrigatórios.")
                return
            run_in_thread(
                integration_api.create_integration,
                lambda r: (
                    show_success(self, "OK", "Integração criada!"),
                    self._load_integrations(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data,
            )

    def _edit_selected(self):
        data = self._get_selected()
        if not data:
            return
        dialog = IntegrationDialog(data, self)
        if dialog.exec() == QDialog.Accepted:
            update_data = dialog.get_data()
            run_in_thread(
                integration_api.update_integration,
                lambda r: (
                    show_success(self, "OK", "Integração atualizada!"),
                    self._load_integrations(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data["id"],
                update_data,
            )

    def _delete_selected(self):
        data = self._get_selected()
        if not data:
            return
        confirm = show_confirm(self, "Confirmar", f'Excluir integração "{data.get("name", "")}"?')
        if confirm:
            run_in_thread(
                integration_api.delete_integration,
                lambda r: (
                    show_success(self, "OK", "Integração excluída!"),
                    self._load_integrations(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data["id"],
            )

    def _test_selected(self):
        data = self._get_selected()
        if not data:
            return
        dialog = IntegrationTesterDialog(data, self)
        dialog.exec()

    def customEvent(self, event):
        if isinstance(event, _IntegrationResultEvent):
            self._handle_result(event.result)

    def _handle_result(self, result: dict):
        pass

    def refresh(self):
        self._load_integrations()