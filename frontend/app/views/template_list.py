from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
)
from frontend.app.widgets.table import StyledTable
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.api import template_api
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager


def _category_colors():
    t = theme_manager.current()
    return {
        "TRANSACTIONAL": t.success,
        "PROMOTION": t.warning,
        "AUTHENTICATION": t.info,
        "ISSUE": t.danger,
        "MARKETING": t.accent_purple,
    }

CATEGORY_LABELS = {
    "TRANSACTIONAL": "Transaccional",
    "PROMOTION": "Promoção",
    "AUTHENTICATION": "Autenticação",
    "ISSUE": "Problema",
    "MARKETING": "Marketing",
}


class TemplateListView(QWidget):
    navigate_to_form = Signal(object)

    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Templates")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        filter_label = QLabel("Categoria:")
        filter_label.setStyleSheet("font-size: 13px;")
        header.addWidget(filter_label)

        self.category_filter = QComboBox()
        self.category_filter.addItems([
            "Todas", "Transaccional", "Promoção", "Autenticação", "Problema", "Marketing"
        ])
        self.category_filter.currentTextChanged.connect(self._filter_changed)
        header.addWidget(self.category_filter)

        if self.user["role"] == "admin":
            self.btn_new = QPushButton("+ Novo Template")
            self.btn_new.setProperty("accent", True)
            self.btn_new.setStyleSheet("font-weight: 600; font-size: 14px; padding: 10px 20px;")
            self.btn_new.clicked.connect(lambda: self.navigate_to_form.emit(None))
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

        layout.addLayout(header)

        self.table = StyledTable(
            ["Nome", "Categoria", "Tipo", "Parâmetros", "Descrição", "Criado por", "Data"]
        )
        self.table.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self.table)

    def _load_templates(self, category: str = None):
        run_in_thread(
            template_api.list_templates,
            lambda templates: self._on_templates(templates, category),
            lambda e: show_error(self, "Erro", f"Não foi possível carregar templates: {e}"),
        )

    def _on_templates(self, templates: list, filter_category: str = None):
        theme = theme_manager.current()
        cat_colors = _category_colors()
        self.table.clear_all()
        for t in templates:
            category = t.get("category", "")
            if filter_category and filter_category != "Todas":
                filter_map = {
                    "Transaccional": "TRANSACTIONAL",
                    "Promoção": "PROMOTION",
                    "Autenticação": "AUTHENTICATION",
                    "Problema": "ISSUE",
                    "Marketing": "MARKETING",
                }
                if CATEGORY_LABELS.get(category) != filter_category:
                    continue

            content_type = t.get("content_type", "TEXT")
            param_count = t.get("parameter_count", 0)
            created_at = t.get("created_at", "")[:10] if t.get("created_at") else ""
            creator_name = t.get("creator_username", "")

            category_display = CATEGORY_LABELS.get(category, category or "—")

            row_data = {
                "data": t,
                "category_color": cat_colors.get(category, theme.text_secondary),
            }
            self.table.add_row(
                [
                    t["name"],
                    category_display,
                    content_type,
                    str(param_count),
                    t.get("description", "") or "",
                    creator_name,
                    created_at,
                ],
                row_data,
            )

    def _on_selection(self):
        has_selection = self.table.selected_data() is not None
        if hasattr(self, "btn_edit"):
            self.btn_edit.setVisible(has_selection)
            self.btn_delete.setVisible(has_selection)

    def _filter_changed(self, text: str):
        self._load_templates(text)

    def _edit_selected(self):
        data = self.table.selected_data()
        if data:
            self.navigate_to_form.emit(data)

    def _delete_selected(self):
        data = self.table.selected_data()
        if not data:
            return
        confirm = show_confirm(
            self, "Confirmar", f'Excluir template "{data["name"]}"?'
        )
        if confirm:
            run_in_thread(
                template_api.delete_template,
                lambda r: (
                    show_success(self, "OK", "Template excluído."),
                    self._load_templates(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                data["id"],
            )

    def refresh(self):
        self._load_templates()