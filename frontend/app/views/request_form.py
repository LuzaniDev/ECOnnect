from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QSplitter,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.api import template_api, request_api, meta_api
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager, _hex_to_rgb

TAG_OPTIONS = ["", "aviso", "cobrança", "promoção", "outro"]

TAG_LABELS = {
    "": "Selecione uma tag",
    "aviso": "Aviso",
    "cobrança": "Cobrança",
    "promoção": "Promoção",
    "outro": "Outro",
}

FORM_FRAME_STYLE = ""


class RequestFormView(QWidget):
    saved = Signal()

    def __init__(self, token: str, user: dict, use_meta_api: bool = False):
        super().__init__()
        self.token = token
        self.user = user
        self.use_meta_api = use_meta_api
        self.templates: list[dict] = []
        self.selected_template: dict | None = None
        self.param_widgets: list[QLineEdit] = []
        self._setup_ui()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        is_admin = self.user.get("role") == "admin"
        title = QLabel("Enviar Mensagem" if not is_admin else "Nova Requisição")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        # Template section
        template_section = QFrame()
        template_section.setObjectName("formSection")
        template_section.setStyleSheet(FORM_FRAME_STYLE)
        template_layout = QVBoxLayout(template_section)
        template_layout.setSpacing(8)

        template_label = QLabel("Template")
        template_label.setObjectName("sectionLabel")
        template_layout.addWidget(template_label)

        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(self._on_template_change)
        template_layout.addWidget(self.template_combo)

        tag_label = QLabel("Tag da Mensagem")
        tag_label.setObjectName("sectionLabel2")
        template_layout.addWidget(tag_label)

        self.tag_combo = QComboBox()
        for val, label in TAG_LABELS.items():
            self.tag_combo.addItem(label, val)
        template_layout.addWidget(self.tag_combo)

        layout.addWidget(template_section)

        # Phone section
        phone_section = QFrame()
        phone_section.setObjectName("formSection")
        phone_section.setStyleSheet(FORM_FRAME_STYLE)
        phone_layout = QVBoxLayout(phone_section)
        phone_layout.setSpacing(8)

        phone_label = QLabel("Telefone do Cliente")
        phone_label.setObjectName("sectionLabel")
        phone_layout.addWidget(phone_label)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("556699301421")
        phone_layout.addWidget(self.phone_input)

        layout.addWidget(phone_section)

        # Link section (admin only)
        self.link_section = QFrame()
        self.link_section.setObjectName("formSection")
        self.link_section.setStyleSheet(FORM_FRAME_STYLE)
        self.link_section.setVisible(is_admin)
        link_layout = QVBoxLayout(self.link_section)
        link_layout.setSpacing(8)

        link_label = QLabel("Link da Mensagem")
        link_label.setObjectName("sectionLabel")
        link_layout.addWidget(link_label)

        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("https://...")
        link_layout.addWidget(self.link_input)

        layout.addWidget(self.link_section)

        # Parameters section
        params_section = QFrame()
        params_section.setObjectName("formSection")
        params_section.setStyleSheet(FORM_FRAME_STYLE)
        self.params_layout = QVBoxLayout(params_section)
        self.params_layout.setSpacing(8)

        params_label = QLabel("Parâmetros da Mensagem")
        params_label.setObjectName("sectionLabel")
        self.params_layout.addWidget(params_label)

        self.params_frame = QFrame()
        self.params_inner = QVBoxLayout(self.params_frame)
        self.params_inner.setSpacing(8)
        self.params_frame.setVisible(False)
        self.params_layout.addWidget(self.params_frame)

        t = theme_manager.current()
        self.cooldown_warning = QLabel()
        self.cooldown_warning.setStyleSheet(
            f"color: {t.warning}; font-size: 12px; padding: 8px 12px; "
            f"background-color: rgba({_hex_to_rgb(t.warning)}, 0.1); "
            f"border: 1px solid rgba({_hex_to_rgb(t.warning)}, 0.3); "
            f"border-radius: 6px;"
        )
        self.cooldown_warning.setVisible(False)
        self.params_layout.addWidget(self.cooldown_warning)

        layout.addWidget(params_section)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_send = QPushButton("Enviar Requisição")
        self.btn_send.setProperty("success", True)
        self.btn_send.setStyleSheet("font-size: 14px; padding: 12px 32px;")
        self.btn_send.clicked.connect(self._send)
        btn_layout.addWidget(self.btn_send)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("ghost", True)
        self.btn_cancel.setStyleSheet("font-size: 14px; padding: 12px 32px;")
        self.btn_cancel.clicked.connect(lambda: self.saved.emit())
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

        scroll.setWidget(container)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(scroll)

        # Right panel - Preview
        right = QFrame()
        right.setObjectName("previewPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        preview_header = QLabel("Prévia da Mensagem")
        preview_header.setObjectName("previewHeader")
        right_layout.addWidget(preview_header)

        preview_sub = QLabel("Visualização em tempo real")
        preview_sub.setObjectName("previewSub")
        right_layout.addWidget(preview_sub)

        preview_content_frame = QFrame()
        preview_content_frame.setStyleSheet(
            "border-radius: 10px; margin: 8px 16px; padding: 20px;"
        )
        preview_inner = QVBoxLayout(preview_content_frame)

        self.preview_content = QLabel(
            "Selecione um template e preencha\nos parâmetros para visualizar\na mensagem completa."
        )
        self.preview_content.setWordWrap(True)
        self.preview_content.setStyleSheet("font-size: 13px;")
        preview_inner.addWidget(self.preview_content)

        right_layout.addWidget(preview_content_frame)
        right_layout.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([550, 400])
        splitter.setHandleWidth(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def _load_templates(self):
        run_in_thread(
            template_api.list_templates,
            self._on_templates,
            lambda e: show_error(self, "Erro", str(e)),
            active_only=True,
        )

    def _on_templates(self, templates: list):
        self.templates = templates
        self.template_combo.clear()
        self.template_combo.addItem("— Selecione um template —", None)
        for t in templates:
            self.template_combo.addItem(t["name"], t["id"])

    def _on_template_change(self):
        self.param_widgets.clear()
        self.cooldown_warning.setVisible(False)
        while self.params_inner.count():
            item = self.params_inner.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        idx = self.template_combo.currentIndex()
        if idx <= 0:
            self.params_frame.setVisible(False)
            self.selected_template = None
            self.preview_content.setText(
                "Selecione um template e preencha\nos parâmetros para visualizar\na mensagem completa."
            )
            self.preview_content.setStyleSheet("font-size: 13px;")
            return

        template_id = self.template_combo.currentData()
        for t in self.templates:
            if t["id"] == template_id:
                self.selected_template = t
                break

        if not self.selected_template:
            return

        self.params_frame.setVisible(True)
        param_count = self.selected_template.get("parameter_count", 0)
        for i in range(param_count):
            order = i + 1
            label = QLabel(f"Parâmetro {order}")
            label.setStyleSheet("font-size: 12px; padding-top: 6px;")
            self.params_inner.addWidget(label)

            edit = QLineEdit()
            edit.setPlaceholderText(f"Valor do parâmetro {order}")
            edit.textChanged.connect(self._update_preview)
            self.param_widgets.append(edit)
            self.params_inner.addWidget(edit)

        self._update_preview()

    def _update_preview(self):
        if not self.selected_template:
            return

        body = self.selected_template.get("body", "")
        values = [w.text() for w in self.param_widgets]

        preview = body
        for i, val in enumerate(values):
            placeholder = "{{" + str(i + 1) + "}}"
            display = val if val else f"{{{{{i+1}}}}}"
            preview = preview.replace(placeholder, display, 1)

        self.preview_content.setText(preview)
        self.preview_content.setStyleSheet("font-size: 13px;")

    def _send(self):
        if not self.selected_template:
            logger.warning("REQ_FORM", "Tentativa de envio sem template selecionado")
            show_error(self, "Erro", "Selecione um template.")
            return

        phone = self.phone_input.text().strip()
        if not phone:
            logger.warning("REQ_FORM", "Telefone não informado")
            show_error(self, "Erro", "Informe o telefone do cliente.")
            return

        param_values = {}
        for i, widget in enumerate(self.param_widgets):
            value = widget.text().strip()
            if not value:
                logger.warning("REQ_FORM", f"Parâmetro {i+1} vazio")
                show_error(
                    self,
                    "Erro",
                    f"Parâmetro {i+1} é obrigatório.",
                )
                return
            param_values[str(i + 1)] = value

        tag_data = self.tag_combo.currentData()
        payload = {
            "template_id": self.selected_template["id"],
            "client_phone": phone,
            "tag": tag_data or None,
            "link": self.link_input.text().strip() or None,
            "parameter_values": param_values,
        }

        logger.info("REQ_FORM", "Enviando requisição", template_id=payload["template_id"], telefone=phone)
        self.btn_send.setEnabled(False)
        if self.use_meta_api:
            run_in_thread(
                meta_api.send_message,
                self._on_sent,
                self._on_send_error,
                payload,
            )
        else:
            run_in_thread(
                request_api.create_request,
                self._on_sent,
                self._on_send_error,
                payload,
            )

    def _on_sent(self, result: dict):
        self.btn_send.setEnabled(True)
        msg_id = result.get("message_id") or result.get("id", "")
        logger.info("REQ_FORM", "Requisição criada com sucesso", request_id=str(msg_id)[:12])
        show_success(self, "Enviado!", "Mensagem enviada com sucesso!")
        self.saved.emit()

    def _on_send_error(self, error: str):
        self.btn_send.setEnabled(True)
        logger.error("REQ_FORM", "Erro ao criar requisição", erro=error)
        if "Intervalo" in error:
            self.cooldown_warning.setText(error)
            self.cooldown_warning.setVisible(True)
        show_error(self, "Erro", error)

    def refresh(self):
        self._load_templates()
