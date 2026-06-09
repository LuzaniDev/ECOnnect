from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QGridLayout,
    QSplitter,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.api import template_api
from frontend.app.core.logger import logger


SECTION_STYLE = """
QFrame#formSection {
    background-color: #141d32;
    border: 1px solid #1e2d4a;
    border-radius: 12px;
    padding: 24px;
}
QLabel#sectionLabel {
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    padding-bottom: 6px;
    font-weight: 600;
}
QLabel#sectionHint {
    font-size: 11px;
    color: #475569;
    padding-bottom: 8px;
}
"""


TEMPLATE_CATEGORIES = [
    ("", "Selecione uma categoria"),
    ("TRANSACTIONAL", "Transaccional"),
    ("PROMOTION", "Promoção"),
    ("AUTHENTICATION", "Autenticação"),
    ("ISSUE", "Problema/Avulso"),
    ("MARKETING", "Marketing"),
]

TEMPLATE_CONTENT_TYPES = [
    ("", "Selecione o tipo"),
    ("TEXT", "Texto"),
    ("IMAGE", "Imagem"),
    ("VIDEO", "Vídeo"),
    ("DOCUMENT", "Documento"),
]


class TemplateFormView(QWidget):
    saved = Signal()

    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self.editing_id = None
        self._setup_ui()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        self.title = QLabel("Novo Template")
        self.title.setStyleSheet("font-size: 28px; font-weight: 700; color: #f1f5f9; ")
        layout.addWidget(self.title)

        basic_section = QFrame()
        basic_section.setObjectName("formSection")
        basic_section.setStyleSheet(SECTION_STYLE)
        basic_layout = QVBoxLayout(basic_section)
        basic_layout.setSpacing(12)

        name_label = QLabel("Nome do Template")
        name_label.setObjectName("sectionLabel")
        basic_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex: aviso_cobranca_v1 (exactamente como na Meta)")
        basic_layout.addWidget(self.name_input)

        cat_label = QLabel("Categoria")
        cat_label.setObjectName("sectionLabel")
        basic_layout.addWidget(cat_label)

        self.category_combo = QComboBox()
        for val, text in TEMPLATE_CATEGORIES:
            self.category_combo.addItem(text, val)
        basic_layout.addWidget(self.category_combo)

        type_label = QLabel("Tipo de Conteúdo")
        type_label.setObjectName("sectionLabel")
        basic_layout.addWidget(type_label)

        self.content_type_combo = QComboBox()
        for val, text in TEMPLATE_CONTENT_TYPES:
            self.content_type_combo.addItem(text, val)
        self.content_type_combo.currentIndexChanged.connect(self._on_content_type_change)
        basic_layout.addWidget(self.content_type_combo)

        layout.addWidget(basic_section)

        header_section = QFrame()
        header_section.setObjectName("formSection")
        header_section.setStyleSheet(SECTION_STYLE)
        header_layout = QVBoxLayout(header_section)
        header_layout.setSpacing(12)

        header_label = QLabel("Cabeçalho (opcional)")
        header_label.setObjectName("sectionLabel")
        header_layout.addWidget(header_label)

        header_hint = QLabel("Texto ou URL de mídia que aparecerá no topo da mensagem")
        header_hint.setObjectName("sectionHint")
        header_layout.addWidget(header_hint)

        self.header_input = QLineEdit()
        self.header_input.setPlaceholderText("Texto do cabeçalho ou URL da imagem/vídeo")
        header_layout.addWidget(self.header_input)

        layout.addWidget(header_section)

        body_section = QFrame()
        body_section.setObjectName("formSection")
        body_section.setStyleSheet(SECTION_STYLE)
        body_layout = QVBoxLayout(body_section)
        body_layout.setSpacing(12)

        body_label = QLabel("Corpo da Mensagem *")
        body_label.setObjectName("sectionLabel")
        body_layout.addWidget(body_label)

        body_hint = QLabel("Use {{1}}, {{2}} etc. para os parâmetros dinâmicos")
        body_hint.setObjectName("sectionHint")
        body_layout.addWidget(body_hint)

        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText("Ex: Olá {{1}}, sua fatura {{2}} de R$ {{3}} vence em {{4}}.")
        self.body_input.setMinimumHeight(120)
        self.body_input.textChanged.connect(self._update_preview)
        body_layout.addWidget(self.body_input)

        layout.addWidget(body_section)

        footer_section = QFrame()
        footer_section.setObjectName("formSection")
        footer_section.setStyleSheet(SECTION_STYLE)
        footer_layout = QVBoxLayout(footer_section)
        footer_layout.setSpacing(12)

        footer_label = QLabel("Rodapé (opcional)")
        footer_label.setObjectName("sectionLabel")
        footer_layout.addWidget(footer_label)

        self.footer_input = QLineEdit()
        self.footer_input.setPlaceholderText("Texto que aparecerá no final da mensagem")
        footer_layout.addWidget(self.footer_input)

        layout.addWidget(footer_section)

        params_section = QFrame()
        params_section.setObjectName("formSection")
        params_section.setStyleSheet(SECTION_STYLE)
        params_layout = QVBoxLayout(params_section)
        params_layout.setSpacing(12)

        params_label = QLabel("Configuração do Template")
        params_label.setObjectName("sectionLabel")
        params_layout.addWidget(params_label)

        param_row = QHBoxLayout()
        param_count_title = QLabel("Quantidade de parâmetros:")
        param_count_title.setStyleSheet("color: #94a3b8; font-size: 13px;")
        param_row.addWidget(param_count_title)

        self.param_count_spin = QSpinBox()
        self.param_count_spin.setRange(0, 99)
        self.param_count_spin.setValue(0)
        self.param_count_spin.setMinimumHeight(44)
        self.param_count_spin.setMinimumWidth(140)
        self.param_count_spin.setStyleSheet(
            "QSpinBox { font-size: 22px; padding: 8px 16px; font-weight: 700; }"
        )
        self.param_count_spin.valueChanged.connect(self._on_param_count_change)
        param_row.addWidget(self.param_count_spin)
        param_row.addStretch()
        params_layout.addLayout(param_row)

        layout.addWidget(params_section)

        desc_section = QFrame()
        desc_section.setObjectName("formSection")
        desc_section.setStyleSheet(SECTION_STYLE)
        desc_layout = QVBoxLayout(desc_section)
        desc_layout.setSpacing(12)

        desc_label = QLabel("Descrição (opcional)")
        desc_label.setObjectName("sectionLabel")
        desc_layout.addWidget(desc_label)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Descrição do template para referência interna")
        self.desc_input.setMaximumHeight(80)
        desc_layout.addWidget(self.desc_input)

        layout.addWidget(desc_section)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self.btn_save = QPushButton("Salvar Template")
        self.btn_save.setProperty("success", True)
        self.btn_save.setStyleSheet("font-weight: 700; font-size: 15px; padding: 14px 36px;")
        self.btn_save.clicked.connect(self._save)
        btn_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("ghost", True)
        self.btn_cancel.setStyleSheet("font-size: 15px; padding: 14px 36px;")
        self.btn_cancel.clicked.connect(lambda: self.saved.emit())
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()

        scroll.setWidget(container)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(scroll)

        right = QFrame()
        right.setObjectName("previewPanel")
        right.setStyleSheet(
            """
            QFrame#previewPanel {
                background-color: #0a1220;
                border-left: 1px solid #1e2d4a;
            }
            QLabel#previewHeader {
                font-size: 16px;
                font-weight: 700;
                color: #f1f5f9;
                padding: 28px 28px 8px 28px;
            }
            QLabel#previewSub {
                font-size: 11px;
                color: #64748b;
                padding: 0 28px 20px 28px;
                text-transform: uppercase;
            }
        """
        )
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        preview_header = QLabel("Prévia do Template")
        preview_header.setObjectName("previewHeader")
        right_layout.addWidget(preview_header)

        preview_sub = QLabel("Visualização em tempo real")
        preview_sub.setObjectName("previewSub")
        right_layout.addWidget(preview_sub)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFrameShape(QFrame.NoFrame)
        preview_scroll.setStyleSheet("border: none;")

        preview_content = QFrame()
        preview_content.setStyleSheet(
            """
            QFrame {
                background-color: #0d1525;
                border: 1px solid #1e2d4a;
                border-radius: 14px;
                margin: 12px 20px;
                padding: 24px;
            }
            QLabel#msgText {
                font-size: 14px;
                color: #f1f5f9;
                background: transparent;
                line-height: 1.5;
            }
            QLabel#msgHeader {
                font-size: 15px;
                font-weight: 600;
                color: #f1f5f9;
                background: transparent;
                padding-bottom: 10px;
            }
            QLabel#msgFooter {
                font-size: 12px;
                color: #64748b;
                background: transparent;
                padding-top: 12px;
            }
            QLabel#categoryBadge {
                font-size: 10px;
                color: #f8891d;
                background: rgba(248, 137, 29, 0.15);
                border-radius: 4px;
                padding: 4px 8px;
            }
        """
        )
        preview_inner = QVBoxLayout(preview_content)
        preview_inner.setSpacing(12)

        self.preview_category = QLabel()
        self.preview_category.setObjectName("categoryBadge")
        preview_inner.addWidget(self.preview_category)

        self.preview_header = QLabel("")
        self.preview_header.setObjectName("msgHeader")
        self.preview_header.setVisible(False)
        preview_inner.addWidget(self.preview_header)

        self.preview_body = QLabel("Digite o corpo da mensagem\npara visualizar o preview.")
        self.preview_body.setObjectName("msgText")
        self.preview_body.setWordWrap(True)
        preview_inner.addWidget(self.preview_body)

        self.preview_footer = QLabel("")
        self.preview_footer.setObjectName("msgFooter")
        self.preview_footer.setVisible(False)
        preview_inner.addWidget(self.preview_footer)

        preview_inner.addStretch()

        preview_scroll.setWidget(preview_content)
        right_layout.addWidget(preview_scroll)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([600, 420])
        splitter.setHandleWidth(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def _on_content_type_change(self):
        content_type = self.content_type_combo.currentData()
        is_media = content_type in ("IMAGE", "VIDEO", "DOCUMENT")
        self.header_input.setPlaceholderText(
            "URL da mídia" if is_media else "Texto do cabeçalho ou URL da imagem/vídeo"
        )

    def _on_param_count_change(self):
        self._update_preview()

    def _update_preview(self):
        category = self.category_combo.currentData()
        category_text = self.category_combo.currentText()
        header = self.header_input.text().strip()
        body = self.body_input.toPlainText().strip()
        footer = self.footer_input.text().strip()

        if category and category_text:
            self.preview_category.setText(f"  {category_text}  ")
            self.preview_category.setVisible(True)
        else:
            self.preview_category.setVisible(False)

        if header:
            self.preview_header.setText(header)
            self.preview_header.setVisible(True)
        else:
            self.preview_header.setVisible(False)

        if body:
            self.preview_body.setText(body)
        else:
            self.preview_body.setText("Digite o corpo da mensagem\npara visualizar o preview.")

        if footer:
            self.preview_footer.setText(footer)
            self.preview_footer.setVisible(True)
        else:
            self.preview_footer.setVisible(False)

    def load_template(self, data: dict | None):
        self.editing_id = data["id"] if data else None
        if data:
            self.title.setText("Editar Template")
            self.name_input.setText(data.get("name", ""))
            self.body_input.setPlainText(data.get("body", ""))
            self.desc_input.setPlainText(data.get("description", "") or "")
            self.param_count_spin.setValue(data.get("parameter_count", 0))
            self.footer_input.setText(data.get("footer") or "")
            self.header_input.setText(data.get("header") or "")

            category = data.get("category", "")
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == category:
                    self.category_combo.setCurrentIndex(i)
                    break

            content_type = data.get("content_type", "")
            for i in range(self.content_type_combo.count()):
                if self.content_type_combo.itemData(i) == content_type:
                    self.content_type_combo.setCurrentIndex(i)
                    break
        else:
            self.title.setText("Novo Template")
            self.name_input.clear()
            self.body_input.clear()
            self.desc_input.clear()
            self.param_count_spin.setValue(0)
            self.footer_input.clear()
            self.header_input.clear()
            self.category_combo.setCurrentIndex(0)
            self.content_type_combo.setCurrentIndex(0)

        self._update_preview()

    def _save(self):
        name = self.name_input.text().strip()
        body = self.body_input.toPlainText().strip()

        if not name:
            show_error(self, "Erro", "Informe o nome do template.")
            return
        if not body:
            show_error(self, "Erro", "O corpo da mensagem é obrigatório.")
            return

        payload = {
            "name": name,
            "body": body,
            "category": self.category_combo.currentData() or None,
            "content_type": self.content_type_combo.currentData() or "TEXT",
            "header": self.header_input.text().strip() or None,
            "footer": self.footer_input.text().strip() or None,
            "description": self.desc_input.toPlainText().strip() or None,
            "parameter_count": self.param_count_spin.value(),
        }

        if self.editing_id:
            run_in_thread(
                template_api.update_template,
                lambda r: (
                    show_success(self, "OK", "Template atualizado!"),
                    self.saved.emit(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                self.editing_id,
                payload,
            )
        else:
            run_in_thread(
                template_api.create_template,
                lambda r: (
                    show_success(self, "OK", "Template criado!"),
                    self.saved.emit(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                payload,
            )