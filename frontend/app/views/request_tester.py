from PySide6.QtCore import Qt, Signal, QTimer
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractButton,
    QButtonGroup,
    QGroupBox,
    QFormLayout,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
)
import httpx
import json
from datetime import datetime
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.core.logger import logger


HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

PROVIDERS = [
    ("meta", "Meta WhatsApp Business"),
    ("blip", "Blip"),
    ("mundobots", "Mundo dos Bots"),
]

RESULT_STYLE = """
QFrame#resultCard {
    background-color: #0d1525;
    border: 1px solid #1e2d4a;
    border-radius: 12px;
    padding: 24px;
}
QLabel#resultTitle {
    font-size: 14px;
    font-weight: 700;
    color: #f1f5f9;
    padding-bottom: 12px;
}
QLabel#statusSuccess {
    font-size: 32px;
    font-weight: 800;
    color: #22c55e;
}
QLabel#statusError {
    font-size: 32px;
    font-weight: 800;
    color: #ef4444;
}
QLabel#statusPending {
    font-size: 18px;
    font-weight: 600;
    color: #f8891d;
}
QTextEdit#responseBody {
    background-color: #0a0f1a;
    border: 1px solid #1e2d4a;
    border-radius: 8px;
    padding: 16px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    color: #22c55e;
}
"""


class KeyValueEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Chave", "Valor"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setRowCount(1)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        add_btn = QPushButton("+ Adicionar")
        add_btn.setStyleSheet("QPushButton { background-color: #1e2d4a; color: #94a3b8; border: none; padding: 8px 16px; border-radius: 6px; } QPushButton:hover { background-color: #2a3d5e; color: #f1f5f9; }")
        add_btn.clicked.connect(self._add_row)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

    def get_data(self) -> dict:
        result = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)
            if key_item and key_item.text().strip():
                key = key_item.text().strip()
                value = val_item.text().strip() if val_item else ""
                result[key] = value
        return result

    def set_data(self, data: dict):
        self.table.setRowCount(0)
        for i, (key, value) in enumerate(data.items()):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(key))
            self.table.setItem(i, 1, QTableWidgetItem(value))
        self.table.insertRow(self.table.rowCount())


class RequestTesterView(QWidget):
    request_sent = Signal(dict)

    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self.templates: list = []
        self.last_response: dict | None = None
        self._setup_ui()
        self._load_templates()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color: #0a1220; border-bottom: 1px solid #1e2d4a; padding: 16px 24px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Testador de Requisições")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f1f5f9;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        view_label = QLabel("Visualização:")
        view_label.setStyleSheet("font-size: 13px; color: #64748b;")
        header_layout.addWidget(view_label)

        self.view_group = QButtonGroup()
        self.btn_tecnica = QPushButton("Técnica")
        self.btn_tecnica.setCheckable(True)
        self.btn_tecnica.setChecked(True)
        self.btn_tecnica.setStyleSheet("QPushButton { background-color: #014998; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; }")
        self.btn_grafica = QPushButton("Gráfica")
        self.btn_grafica.setCheckable(True)
        self.btn_grafica.setStyleSheet("QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #1e2d4a; padding: 10px 20px; border-radius: 8px; }")
        self.view_group.addButton(self.btn_tecnica, 0)
        self.view_group.addButton(self.btn_grafica, 1)
        self.btn_tecnica.clicked.connect(lambda: self._set_view(0))
        self.btn_grafica.clicked.connect(lambda: self._set_view(1))
        header_layout.addWidget(self.btn_tecnica)
        header_layout.addWidget(self.btn_grafica)

        main_layout.addWidget(header)

        self.stack = QWidget()
        stack_layout = QVBoxLayout(self.stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        self.tecnica_view = self._create_technical_view()
        self.grafica_view = self._create_graphical_view()
        stack_layout.addWidget(self.tecnica_view)
        stack_layout.addWidget(self.grafica_view)
        self.grafica_view.setVisible(False)

        main_layout.addWidget(self.stack, 1)

    def _set_view(self, index: int):
        self.tecnica_view.setVisible(index == 0)
        self.grafica_view.setVisible(index == 1)
        if index == 0:
            self.btn_tecnica.setStyleSheet("QPushButton { background-color: #014998; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; }")
            self.btn_grafica.setStyleSheet("QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #1e2d4a; padding: 10px 20px; border-radius: 8px; }")
        else:
            self.btn_grafica.setStyleSheet("QPushButton { background-color: #014998; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; }")
            self.btn_tecnica.setStyleSheet("QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #1e2d4a; padding: 10px 20px; border-radius: 8px; }")

    def _create_technical_view(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(16)

        url_row = QHBoxLayout()
        url_row.setSpacing(12)

        self.method_combo = QComboBox()
        self.method_combo.addItems(HTTP_METHODS)
        self.method_combo.setCurrentText("POST")
        self.method_combo.setStyleSheet("""
            QComboBox {
                background-color: #014998;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 700;
                min-width: 100px;
            }
        """)
        url_row.addWidget(self.method_combo)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.exemplo.com/endpoint")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1525;
                border: 1px solid #1e2d4a;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QLineEdit:focus {
                border: 1px solid #014998;
            }
        """)
        url_row.addWidget(self.url_input, 1)

        left_layout.addLayout(url_row)

        tabs = QTabWidget()

        params_tab = QWidget()
        params_layout = QVBoxLayout(params_tab)
        params_layout.setContentsMargins(0, 12, 0, 0)
        self.params_editor = KeyValueEditor()
        params_layout.addWidget(self.params_editor)
        tabs.addTab(params_tab, "Query Params")

        headers_tab = QWidget()
        headers_layout = QVBoxLayout(headers_tab)
        headers_layout.setContentsMargins(0, 12, 0, 0)
        self.headers_editor = KeyValueEditor()
        headers_layout.addWidget(self.headers_editor)
        tabs.addTab(headers_tab, "Headers")

        body_tab = QWidget()
        body_layout = QVBoxLayout(body_tab)
        body_layout.setContentsMargins(0, 12, 0, 0)
        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText('{\n  "key": "value"\n}')
        self.body_input.setStyleSheet("""
            QTextEdit {
                background-color: #0d1525;
                border: 1px solid #1e2d4a;
                border-radius: 8px;
                padding: 16px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                color: #f1f5f9;
            }
        """)
        body_layout.addWidget(self.body_input)
        tabs.addTab(body_tab, "Body")

        auth_tab = QWidget()
        auth_layout = QFormLayout(auth_tab)
        auth_layout.setContentsMargins(0, 12, 0, 0)
        auth_layout.setSpacing(12)

        self.auth_type = QComboBox()
        self.auth_type.addItems(["None", "Bearer Token", "API Key", "Basic Auth"])
        auth_layout.addRow("Tipo:", self.auth_type)

        self.auth_value = QLineEdit()
        self.auth_value.setPlaceholderText("Token ou chave de API")
        auth_layout.addRow("Token/Key:", self.auth_value)

        auth_layout.addRow("", QWidget())
        tabs.addTab(auth_tab, "Auth")

        left_layout.addWidget(tabs, 1)

        btn_send = QPushButton("Enviar Requisição")
        btn_send.setProperty("success", True)
        btn_send.setStyleSheet("font-weight: 700; font-size: 15px; padding: 14px;")
        btn_send.clicked.connect(self._send_technical)
        left_layout.addWidget(btn_send)

        right = QScrollArea()
        right.setWidgetResizable(True)
        right.setFrameShape(QFrame.NoFrame)
        right.setStyleSheet("background-color: #0a1220; border-left: 1px solid #1e2d4a;")

        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(20, 20, 20, 20)
        result_layout.setSpacing(16)

        self.result_card = QFrame()
        self.result_card.setObjectName("resultCard")
        self.result_card.setStyleSheet(RESULT_STYLE)
        result_layout.addWidget(self.result_card)

        right.setWidget(result_container)
        self._init_result_card()

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

        return widget

    def _create_graphical_view(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(16)

        provider_label = QLabel("Provedor")
        provider_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase;")
        left_layout.addWidget(provider_label)

        self.provider_combo = QComboBox()
        for val, name in PROVIDERS:
            self.provider_combo.addItem(name, val)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        left_layout.addWidget(self.provider_combo)

        template_label = QLabel("Template")
        template_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; padding-top: 8px;")
        left_layout.addWidget(template_label)

        self.template_combo_graf = QComboBox()
        self.template_combo_graf.currentIndexChanged.connect(self._on_template_change_graf)
        left_layout.addWidget(self.template_combo_graf)

        self.params_frame = QFrame()
        self.params_frame.setStyleSheet("QFrame { background-color: #141d32; border: 1px solid #1e2d4a; border-radius: 10px; padding: 16px; }")
        self.params_layout = QVBoxLayout(self.params_frame)
        self.params_layout.setSpacing(12)

        self.params_inner = QVBoxLayout()
        self.params_frame.setVisible(False)
        self.params_layout.addLayout(self.params_inner)
        left_layout.addWidget(self.params_frame)

        phone_label = QLabel("Telefone do Destino")
        phone_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; padding-top: 8px;")
        left_layout.addWidget(phone_label)

        self.phone_input_graf = QLineEdit()
        self.phone_input_graf.setPlaceholderText("556699301421")
        left_layout.addWidget(self.phone_input_graf)

        url_label = QLabel("URL da API (opcional)")
        url_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; padding-top: 8px;")
        left_layout.addWidget(url_label)

        self.url_input_graf = QLineEdit()
        self.url_input_graf.setPlaceholderText("Sobrescrever URL padrão do provedor")
        left_layout.addWidget(self.url_input_graf)

        self.btn_send_graf = QPushButton("Enviar Mensagem")
        self.btn_send_graf.setProperty("success", True)
        self.btn_send_graf.setStyleSheet("font-weight: 700; font-size: 15px; padding: 14px; margin-top: 16px;")
        self.btn_send_graf.clicked.connect(self._send_graphical)
        left_layout.addWidget(self.btn_send_graf)

        left_layout.addStretch()

        right = QScrollArea()
        right.setWidgetResizable(True)
        right.setFrameShape(QFrame.NoFrame)
        right.setStyleSheet("background-color: #0a1220; border-left: 1px solid #1e2d4a;")

        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(20, 20, 20, 20)
        result_layout.setSpacing(16)

        self.result_card_graf = QFrame()
        self.result_card_graf.setObjectName("resultCard")
        self.result_card_graf.setStyleSheet(RESULT_STYLE)
        result_layout.addWidget(self.result_card_graf)

        right.setWidget(result_container)
        self._init_result_card_graf()

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

        return widget

    def _init_result_card(self):
        layout = QVBoxLayout(self.result_card)
        layout.setSpacing(12)

        title = QLabel("Resultado da Requisição")
        title.setObjectName("resultTitle")
        layout.addWidget(title)

        self.status_label = QLabel("Aguardando envio...")
        self.status_label.setObjectName("statusPending")
        layout.addWidget(self.status_label)

        self.status_detail = QLabel("")
        self.status_detail.setStyleSheet("font-size: 13px; color: #64748b;")
        layout.addWidget(self.status_detail)

        self.response_label = QLabel("Resposta:")
        self.response_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; padding-top: 12px;")
        self.response_label.setVisible(False)
        layout.addWidget(self.response_label)

        self.response_body = QTextEdit()
        self.response_body.setObjectName("responseBody")
        self.response_body.setReadOnly(True)
        self.response_body.setMaximumHeight(300)
        self.response_body.setVisible(False)
        layout.addWidget(self.response_body)

        layout.addStretch()

    def _init_result_card_graf(self):
        layout = QVBoxLayout(self.result_card_graf)
        layout.setSpacing(12)

        title = QLabel("Resultado do Envio")
        title.setObjectName("resultTitle")
        layout.addWidget(title)

        self.status_label_graf = QLabel("Aguardando envio...")
        self.status_label_graf.setObjectName("statusPending")
        layout.addWidget(self.status_label_graf)

        self.status_detail_graf = QLabel("")
        self.status_detail_graf.setStyleSheet("font-size: 13px; color: #64748b;")
        layout.addWidget(self.status_detail_graf)

        self.response_label_graf = QLabel("Resposta:")
        self.response_label_graf.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600; padding-top: 12px;")
        self.response_label_graf.setVisible(False)
        layout.addWidget(self.response_label_graf)

        self.response_body_graf = QTextEdit()
        self.response_body_graf.setObjectName("responseBody")
        self.response_body_graf.setReadOnly(True)
        self.response_body_graf.setMaximumHeight(300)
        self.response_body_graf.setVisible(False)
        layout.addWidget(self.response_body_graf)

        layout.addStretch()

    def _load_templates(self):
        from frontend.app.api import template_api
        from frontend.app.widgets.worker import run_in_thread

        run_in_thread(
            template_api.list_templates,
            self._on_templates,
            lambda e: None,
        )

    def _on_templates(self, templates: list):
        self.templates = templates
        self.template_combo_graf.clear()
        self.template_combo_graf.addItem("— Selecione um template —", None)
        for t in templates:
            self.template_combo_graf.addItem(t["name"], t["id"])

    def _on_provider_change(self):
        pass

    def _on_template_change_graf(self):
        while self.params_inner.count():
            item = self.params_inner.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        self.param_widgets_graf = []

        idx = self.template_combo_graf.currentIndex()
        if idx <= 0:
            self.params_frame.setVisible(False)
            return

        template_id = self.template_combo_graf.currentData()
        for t in self.templates:
            if t["id"] == template_id:
                param_count = t.get("parameter_count", 0)
                if param_count > 0:
                    self.params_frame.setVisible(True)
                    for i in range(param_count):
                        label = QLabel(f"Parâmetro {i + 1}")
                        label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
                        self.params_inner.addWidget(label)

                        edit = QLineEdit()
                        edit.setPlaceholderText(f"Valor do parâmetro {i + 1}")
                        self.params_inner.addWidget(edit)
                        self.param_widgets_graf.append(edit)
                else:
                    self.params_frame.setVisible(False)
                break

    def _send_technical(self):
        method = self.method_combo.currentText()
        url = self.url_input.text().strip()

        if not url:
            show_error(self, "Erro", "Informe a URL da requisição.")
            return

        headers = self.headers_editor.get_data()

        auth_type = self.auth_type.currentText()
        auth_value = self.auth_value.text().strip()
        if auth_type == "Bearer Token" and auth_value:
            headers["Authorization"] = f"Bearer {auth_value}"
        elif auth_type == "API Key" and auth_value:
            if ":" in auth_value:
                key, val = auth_value.split(":", 1)
                headers[key] = val
            else:
                headers["X-API-Key"] = auth_value
        elif auth_type == "Basic Auth" and auth_value:
            import base64
            encoded = base64.b64encode(auth_value.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        params = self.params_editor.get_data()

        body = None
        if method in ("POST", "PUT", "PATCH"):
            body_text = self.body_input.toPlainText().strip()
            if body_text:
                try:
                    body = json.loads(body_text)
                except:
                    body = body_text

        self._execute_request(method, url, headers, params, body)

    def _send_graphical(self):
        idx = self.template_combo_graf.currentIndex()
        if idx <= 0:
            show_error(self, "Erro", "Selecione um template.")
            return

        phone = self.phone_input_graf.text().strip()
        if not phone:
            show_error(self, "Erro", "Informe o telefone do destinatário.")
            return

        template_id = self.template_combo_graf.currentData()
        template = None
        for t in self.templates:
            if t["id"] == template_id:
                template = t
                break

        param_values = {}
        if hasattr(self, "param_widgets_graf"):
            for i, widget in enumerate(self.param_widgets_graf):
                value = widget.text().strip()
                if not value:
                    show_error(self, "Erro", f"Parâmetro {i + 1} é obrigatório.")
                    return
                param_values[str(i + 1)] = value

        provider = self.provider_combo.currentData()

        provider_urls = {
            "meta": "https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/messages",
            "blip": "https://http-api.blip.ws/YOUR_BLIP_ID/messages",
            "mundobots": "https://api.mundobots.com.br/send",
        }

        url = self.url_input_graf.text().strip() or provider_urls.get(provider, "")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        body = {
            "template_id": template_id,
            "template_name": template["name"],
            "phone": phone,
            "parameters": param_values,
        }

        self._execute_request("POST", url, headers, {}, body)

    def _execute_request(self, method: str, url: str, headers: dict, params: dict, body: any):
        self.status_label.setText("Enviando...")
        self.status_label.setObjectName("statusPending")
        self.status_detail.setText("")
        self.response_label.setVisible(False)
        self.response_body.setVisible(False)

        self.status_label_graf.setText("Enviando...")
        self.status_label_graf.setObjectName("statusPending")
        self.status_detail_graf.setText("")
        self.response_label_graf.setVisible(False)
        self.response_body_graf.setVisible(False)

        def do_request():
            try:
                client = httpx.Client(timeout=30)
                kwargs = {"headers": headers}
                if params:
                    kwargs["params"] = params
                if body and method in ("POST", "PUT", "PATCH"):
                    kwargs["json"] = body

                response = client.request(method, url, **kwargs)

                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "elapsed": response.elapsed.total_seconds(),
                }
                client.close()
                return result
            except Exception as e:
                return {
                    "success": False,
                    "status_code": 0,
                    "headers": {},
                    "body": str(e),
                    "elapsed": 0,
                    "error": True,
                }

        import threading
        thread = threading.Thread(target=self._request_thread, args=(do_request,))
        thread.daemon = True
        thread.start()

    def _request_thread(self, func):
        import time
        time.sleep(0.1)
        result = func()
        QTimer.postEvent(self, _RequestResultEvent(result))

    def customEvent(self, event):
        if isinstance(event, _RequestResultEvent):
            self._handle_result(event.result)

    def _handle_result(self, result: dict):
        self.last_response = result

        is_error = result.get("error", False)
        status_code = result.get("status_code", 0)
        elapsed = result.get("elapsed", 0)
        body = result.get("body", "")

        if is_error:
            status_text = "ERRO"
            status_color = "statusError"
            detail_text = f"Erro de conexão • {elapsed:.2f}s"
        elif result.get("success"):
            status_text = str(status_code)
            status_color = "statusSuccess"
            detail_text = f"Sucesso • {elapsed:.2f}s"
        else:
            status_text = str(status_code)
            status_color = "statusError"
            detail_text = f"Falha • {elapsed:.2f}s"

        self.status_label.setText(status_text)
        self.status_label.setObjectName(status_color)
        self.status_detail.setText(detail_text)
        self.response_label.setVisible(True)
        self.response_body.setVisible(True)

        try:
            formatted = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
            self.response_body.setStyleSheet("QTextEdit#responseBody { background-color: #0a0f1a; border: 1px solid #1e2d4a; border-radius: 8px; padding: 16px; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #22c55e; }")
        except:
            formatted = body
            self.response_body.setStyleSheet("QTextEdit#responseBody { background-color: #0a0f1a; border: 1px solid #1e2d4a; border-radius: 8px; padding: 16px; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #f8891d; }")

        self.response_body.setPlainText(formatted)

        self.status_label_graf.setText(status_text)
        self.status_label_graf.setObjectName(status_color)
        self.status_detail_graf.setText(detail_text)
        self.response_label_graf.setVisible(True)
        self.response_body_graf.setVisible(True)
        self.response_body_graf.setPlainText(formatted)


class _RequestResultEvent:
    def __init__(self, result: dict):
        self.result = result