import json
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QComboBox, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QDialog, QTimeEdit, QDialogButtonBox, QTextEdit, QFormLayout,
    QListWidget, QListWidgetItem,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success, InputDialog
from frontend.app.widgets.autocomplete_textedit import AutoCompleteTextEdit
from frontend.app.api import integration_api
from frontend.app.core.logger import logger
from datetime import datetime


SCHEDULE_PRESETS = {
    "1h": "A cada 1 hora",
    "6h": "A cada 6 horas",
    "12h": "A cada 12 horas",
    "daily": "Diariamente",
    "weekly": "Semanalmente",
    "biweekly": "Quinzenalmente",
    "monthly": "Mensalmente",
}

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

DATABASE_VARIABLES = {
    "Cliente": [
        "cliente.nome", "cliente.fantasia", "cliente.cpfcnpj",
        "cliente.fone", "cliente.email", "cliente.endereco",
        "cliente.bairro", "cliente.cidade", "cliente.cep",
        "cliente.datanascimento", "cliente.sexo", "cliente.nomemae",
        "cliente.datafundacao", "cliente.capitalsocial",
    ],
    "Produto": [
        "produto.descricao", "produto.codigo", "produto.marca",
        "produto.fabricante", "produto.grupo", "produto.preco",
    ],
    "Pedido": [
        "pedido.numero", "pedido.data", "pedido.valor", "pedido.status",
    ],
    "Boleto": [
        "boleto.nossonumero", "boleto.valor", "boleto.vencimento",
        "boleto.parcela", "boleto.carteira", "boleto.situacao",
    ],
    "Parcela": [
        "parcela.valor", "parcela.valorpendente", "parcela.vencimento",
        "parcela.situacao", "parcela.jurosacumulado",
    ],
    "Empresa": [
        "empresa.nomefantasia", "empresa.razaosocial", "empresa.cpfcnpj",
        "empresa.telefone", "empresa.email",
    ],
}


def _extract_variables(data) -> list[str]:
    """Scan any JSON-serializable structure for {{var}} patterns and return unique names."""
    seen = set()
    def _scan(obj):
        if isinstance(obj, str):
            for m in re.findall(r"\{\{([\w.]+)\}\}", obj):
                seen.add(m)
        elif isinstance(obj, dict):
            for v in obj.values():
                _scan(v)
        elif isinstance(obj, list):
            for item in obj:
                _scan(item)
    _scan(data)
    return sorted(seen)


def _substitute_variables(data, values: dict[str, str]):
    """Replace {{var}} with values in any JSON-serializable structure."""
    if isinstance(data, str):
        result = data
        for var, val in values.items():
            result = result.replace("{{" + var + "}}", val)
        return result
    elif isinstance(data, dict):
        return {k: _substitute_variables(v, values) for k, v in data.items()}
    elif isinstance(data, list):
        return [_substitute_variables(item, values) for item in data]
    return data


class TriggerVariablesDialog(QDialog):
    def __init__(self, variables: list[str], parent=None, sql_variables: list[dict] = None, user: dict = None):
        super().__init__(parent)
        self._vars = variables
        self._sql_variables = sql_variables or []
        self._sql_map = {v["name"]: v["sql_query"] for v in self._sql_variables}
        self._sql_col_map = {v["name"]: v.get("value_column") for v in self._sql_variables}
        self.setWindowTitle("Preencher Variaveis")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QLineEdit {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 6px;
            }
            QComboBox {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 6px;
            }
            QComboBox::drop-down {
                border: none; width: 24px;
            }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #8b949e; margin-right: 4px;
            }
        """)
        self._inputs = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Preencha os valores das variaveis")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        has_sql = any(v in self._sql_map for v in self._vars)
        if has_sql:
            desc = QLabel(
                "Variaveis do banco de dados possuem uma lista "
                "para selecao. As demais devem ser preenchidas manualmente."
            )
        else:
            desc = QLabel(
                "As variaveis abaixo foram encontradas na requisicao. "
                "Preencha os valores e clique em OK para enviar."
            )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 8, 0, 8)

        INPUT_STYLE = "font-size: 12px;"

        for var in self._vars:
            if var in self._sql_map:
                combo = QComboBox()
                combo.addItem("")
                try:
                    from frontend.app.core.firebird_client import fb
                    rows = fb.query(self._sql_map[var])
                    value_column = self._sql_col_map.get(var)
                    for r in rows:
                        if not r or not r[0]:
                            continue
                        if len(r) == 1:
                            val = str(r[0]).strip()
                            combo.addItem(val, val)
                        else:
                            idx = (value_column - 1) if value_column else (len(r) - 1)
                            idx = max(0, min(idx, len(r) - 1))
                            value = str(r[idx]).strip()
                            parts = [str(c).strip() for i, c in enumerate(r) if c is not None and i != idx]
                            label = " | ".join(parts)
                            combo.addItem(f"{label} | {value}", value)
                except Exception:
                    pass
                combo.setStyleSheet(INPUT_STYLE)
                lbl = QLabel(f"  {{${var}}}")
                lbl.setStyleSheet("font-size: 13px; color: #58a6ff; font-weight: 600;")
                form.addRow(lbl, combo)
                self._inputs[var] = combo
            else:
                inp = QLineEdit()
                inp.setPlaceholderText(f"Valor para {var}")
                inp.setStyleSheet(INPUT_STYLE)
                lbl = QLabel(f"  {{${var}}}")
                lbl.setStyleSheet("font-size: 13px; color: #58a6ff; font-weight: 600;")
                form.addRow(lbl, inp)
                self._inputs[var] = inp

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict[str, str]:
        result = {}
        for var, widget in self._inputs.items():
            if isinstance(widget, QComboBox):
                data = widget.currentData()
                result[var] = str(data).strip() if data is not None else ""
            else:
                result[var] = widget.text().strip()
        return result


class VariablePickerDialog(QDialog):
    def __init__(self, variables: list[dict], parent=None):
        super().__init__(parent)
        self._variables = variables
        self.setWindowTitle("Auto-Completion via SQL")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QListWidget {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px;
                font-size: 12px;
            }
            QListWidget::item { padding: 8px 12px; }
            QListWidget::item:selected { background: #1f6feb; color: #fff; }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Variaveis disponiveis para auto-complete")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        desc = QLabel(
            "Digite o nome da variavel seguido de ponto (ex: empresa.) "
            "no editor do JSON para ver os valores disponiveis. "
            "Selecione um valor para inseri-lo diretamente no texto."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar variavel...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        for v in self._variables:
            name = v.get("name", "")
            label = v.get("label") or name
            sql = v.get("sql_query", "")
            text = f"  {name}  |  {label}"
            item = QListWidgetItem(text)
            item.setToolTip(f"SQL: {sql}")
            item.setData(Qt.UserRole, name)
            self.list_widget.addItem(item)

        if not self._variables:
            self.list_widget.addItem("  Nenhuma variavel cadastrada. Crie em 'Gerenciar'.")

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter(self, text: str):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower() and
                         text.lower() not in item.toolTip().lower())


class SqlVariableManagerDialog(QDialog):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Gerenciar Variaveis SQL")
        self.setMinimumSize(600, 450)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 8px; font-weight: 600; }
            QPushButton { border-radius: 4px; padding: 6px 14px;
                font-size: 12px; font-weight: 600; }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Variaveis SQL do Banco de Dados")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        desc = QLabel(
            "Cada variavel possui um nome (usado como {{nome}}) e uma consulta SQL "
            "que sera executada no Firebird no momento do disparo."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Nova Variavel")
        btn_add.setStyleSheet(
            "background: #1f6feb; color: #fff; border: none; padding: 8px 16px;"
        )
        btn_add.clicked.connect(self._add)
        toolbar.addWidget(btn_add)

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.setStyleSheet(
            "background: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
        )
        btn_refresh.clicked.connect(self._load)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nome", "Rotulo", "SQL", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(3, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        layout.addWidget(self.table)

        self._load()

    def _load(self):
        from frontend.app.api.sql_variable_api import list_sql_variables
        eco_empresa = self._user.get("eco_empresa")
        if not eco_empresa:
            return
        try:
            variables = list_sql_variables(company_code=eco_empresa)
        except Exception:
            variables = []
        self.table.setRowCount(0)
        for v in variables:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(v.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(v.get("label") or ""))
            self.table.setItem(row, 2, QTableWidgetItem(v.get("sql_query", "")))

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            btn_edit = QPushButton("Editar")
            btn_edit.setStyleSheet(
                "background: #21262d; border: 1px solid #30363d; color: #c9d1d9;"
            )
            btn_edit.clicked.connect(lambda checked, vid=v["id"], vd=v: self._edit(vid, vd))
            al.addWidget(btn_edit)

            btn_del = QPushButton("Excluir")
            btn_del.setStyleSheet(
                "background: transparent; border: 1px solid #f85149; color: #f85149;"
            )
            btn_del.clicked.connect(lambda checked, vid=v["id"], vn=v["name"]: self._delete(vid, vn))
            al.addWidget(btn_del)

            al.addStretch()
            self.table.setCellWidget(row, 3, actions)

    def _add(self):
        dlg = SqlVariableEditDialog(self._user, self)
        if dlg.exec() == QDialog.Accepted:
            self._load()

    def _edit(self, var_id: str, var_data: dict):
        dlg = SqlVariableEditDialog(self._user, self, var_data)
        if dlg.exec() == QDialog.Accepted:
            self._load()

    def _delete(self, var_id: str, var_name: str):
        confirm = show_confirm(self, "Confirmar",
            f'Excluir variavel "{var_name}"?')
        if not confirm:
            return
        from frontend.app.api.sql_variable_api import delete_sql_variable
        try:
            delete_sql_variable(var_id)
            show_success(self, "OK", "Variavel excluida!")
            self._load()
        except Exception as e:
            show_error(self, "Erro", str(e))


def _parse_column_names(sql: str) -> list[str]:
    cleaned = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = ' '.join(cleaned.split())

    m = re.search(r'SELECT\s+(.*?)\s+FROM\s', cleaned, re.IGNORECASE | re.DOTALL)
    if not m or m.group(1).strip() == '*':
        return []

    cols_part = m.group(1).strip()
    columns = []
    depth = 0
    buf = []
    for ch in cols_part:
        if ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            buf.append(ch)
        elif ch == ',' and depth == 0:
            columns.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        columns.append(''.join(buf).strip())

    result = []
    for col in columns:
        col = col.strip()
        alias_m = re.search(r'(?:AS|as)\s+["`]?(\w+)["`]?\s*$', col)
        if alias_m:
            result.append(alias_m.group(1))
        else:
            result.append(col.split('.')[-1].strip('"` '))
    return result


class SqlVariableEditDialog(QDialog):
    def __init__(self, user: dict, parent=None, var_data: dict = None):
        super().__init__(parent)
        self._user = user
        self._var_data = var_data
        self._tested_ok = False
        self._tested_columns = []
        is_edit = var_data is not None
        self.setWindowTitle("Editar Variavel" if is_edit else "Nova Variavel")
        self.setMinimumWidth(640)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QLineEdit, QTextEdit {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 8px;
            }
            QComboBox {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 6px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #8b949e; margin-right: 4px;
            }
            QPushButton#btnTestSql {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 4px; color: #58a6ff; padding: 8px 16px;
                font-size: 12px; font-weight: 600; min-width: 100px;
            }
            QPushButton#btnTestSql:hover { background: #30363d; }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Nova Variavel SQL" if not self._var_data else "Editar Variavel SQL")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: cliente.telefone")
        if self._var_data:
            self.txt_name.setText(self._var_data.get("name", ""))
        form.addRow("Nome:", self.txt_name)

        self.txt_label = QLineEdit()
        self.txt_label.setPlaceholderText("Ex: Telefone do cliente")
        if self._var_data:
            self.txt_label.setText(self._var_data.get("label", ""))
        form.addRow("Rotulo:", self.txt_label)

        sql_row = QHBoxLayout()
        self.txt_sql = QTextEdit()
        self.txt_sql.setPlaceholderText(
            "SELECT CODIGO, NOME, TELEFONE FROM CLIENTES"
        )
        self.txt_sql.setMinimumHeight(100)
        if self._var_data:
            self.txt_sql.setPlainText(self._var_data.get("sql_query", ""))
        sql_row.addWidget(self.txt_sql, 1)

        btn_test = QPushButton("Testar SQL")
        btn_test.setObjectName("btnTestSql")
        btn_test.setCursor(Qt.PointingHandCursor)
        btn_test.clicked.connect(self._test_sql)
        sql_row.addWidget(btn_test, alignment=Qt.AlignTop)
        form.addRow("SQL Query:", sql_row)

        self.status_label = QLabel("Clique em \"Testar SQL\" para validar a consulta.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #8b949e; font-size: 12px; padding: 2px 0;")
        form.addRow("", self.status_label)

        val_row = QHBoxLayout()
        self.column_combo = QComboBox()
        self.column_combo.setEnabled(False)
        self.column_combo.addItem("(teste o SQL primeiro)", None)
        val_row.addWidget(self.column_combo, 1)

        hint = QLabel(
            "Colunas anteriores sao exibidas como identificacao no dropdown."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #d29922; font-size: 11px;")
        val_row.addWidget(hint)
        form.addRow("Coluna de valor:", val_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _test_sql(self):
        sql = self.txt_sql.toPlainText().strip()
        if not sql:
            show_error(self, "Erro", "Digite a consulta SQL primeiro.")
            return

        self._tested_ok = False
        self.column_combo.setEnabled(False)
        self.column_combo.clear()
        self.status_label.setText("Testando...")
        self.status_label.setStyleSheet("color: #d29922; font-size: 12px; padding: 2px 0;")

        try:
            from frontend.app.core.firebird_client import fb
            col_names, rows = fb.query_with_columns(sql)
        except Exception as e:
            self.status_label.setText(f"Erro: {str(e)[:80]}")
            self.status_label.setStyleSheet("color: #f85149; font-size: 12px; padding: 2px 0;")
            return

        if not rows or len(rows) <= 1:
            self.status_label.setText("Deve retornar mais de 1 registro")
            self.status_label.setStyleSheet("color: #f85149; font-size: 12px; padding: 2px 0;")
            return

        self._tested_ok = True
        self._tested_columns = col_names or _parse_column_names(sql)

        self.column_combo.addItem("Ultima coluna (padrao)", None)
        for i, name in enumerate(self._tested_columns):
            self.column_combo.addItem(name, i + 1)

        current_val = self._var_data.get("value_column") if self._var_data else None
        if current_val:
            for idx in range(self.column_combo.count()):
                if self.column_combo.itemData(idx) == current_val:
                    self.column_combo.setCurrentIndex(idx)
                    break

        self.column_combo.setEnabled(True)
        status_parts = [f"OK — {len(rows)} registros encontrados"]
        if col_names:
            status_parts.append(f"Colunas: {', '.join(col_names)}")
        self.status_label.setText("  ".join(status_parts))
        self.status_label.setStyleSheet("color: #3fb950; font-size: 12px; padding: 2px 0;")

    def _save(self):
        if not self._tested_ok:
            show_error(self, "Erro", "Teste o SQL antes de salvar.")
            return

        name = self.txt_name.text().strip()
        sql = self.txt_sql.toPlainText().strip()
        if not name:
            show_error(self, "Erro", "O nome da variavel e obrigatorio.")
            return
        if not sql:
            show_error(self, "Erro", "A consulta SQL e obrigatoria.")
            return

        from frontend.app.api.sql_variable_api import create_sql_variable, update_sql_variable
        eco_empresa = self._user.get("eco_empresa")
        if not eco_empresa:
            show_error(self, "Erro", "Empresa nao identificada.")
            return

        data = {
            "name": name,
            "label": self.txt_label.text().strip() or name,
            "sql_query": sql,
            "value_column": self.column_combo.currentData(),
            "company_code": eco_empresa,
        }
        try:
            if self._var_data:
                update_sql_variable(self._var_data["id"], data)
            else:
                create_sql_variable(data)
            self.accept()
        except Exception as e:
            show_error(self, "Erro", str(e))


class InterfaceEditorDialog(QDialog):
    def __init__(self, parent=None, data: dict = None, is_active: bool = True, user: dict = None, sql_variables: list[dict] = None, integration_type: str = "normal"):
        super().__init__(parent)
        self._user = user or {}
        self._sql_variables = sql_variables or []
        self._integration_type = integration_type
        self.setWindowTitle("Editor de Requisicao")
        self.setMinimumSize(640, 560)
        self.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; }
            QTextEdit, QLineEdit, QComboBox {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px; padding: 6px;
            }
        """)
        self._data = data or {}
        self._is_active = is_active
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Editor de Requisicao")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        var_hint = QLabel(
            "Dica: use {{nome}}, {{telefone}}, {{email}} no body ou headers "
            "para criar parametros que serao preenchidos na hora da execucao."
        )
        var_hint.setWordWrap(True)
        var_hint.setStyleSheet(
            "color: #d29922; font-size: 11px; background: #161b22; "
            "border: 1px solid #30363d; border-radius: 4px; padding: 6px;"
        )
        layout.addWidget(var_hint)

        btn_vars = QPushButton("Inserir Variavel do Banco")
        btn_vars.setCursor(Qt.PointingHandCursor)
        btn_vars.setStyleSheet(
            "background: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #58a6ff; padding: 6px 14px; font-size: 12px;"
        )
        btn_vars.clicked.connect(self._insert_variable)
        layout.addWidget(btn_vars, alignment=Qt.AlignLeft)

        btn_import = QPushButton("Importar cURL")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setStyleSheet(
            "background: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; color: #c9d1d9; padding: 6px 14px; font-size: 12px;"
        )
        btn_import.clicked.connect(self._import_curl)
        layout.addWidget(btn_import, alignment=Qt.AlignLeft)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lbl = QLabel("Metodo:")
        lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600;")
        row1.addWidget(lbl)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["POST", "GET", "PUT", "DELETE", "PATCH"])
        self.method_combo.setCurrentText(self._data.get("method", "POST"))
        row1.addWidget(self.method_combo)

        lbl = QLabel("URL:")
        lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600;")
        row1.addWidget(lbl)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://exemplo.com/api/endpoint")
        self.url_input.setText(self._data.get("url", "https://app.mundodosbots.com.br/api/users"))
        row1.addWidget(self.url_input, 1)
        layout.addLayout(row1)

        lbl = QLabel("Headers (um por linha: Chave: Valor)")
        lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600; margin-top: 4px;")
        layout.addWidget(lbl)

        self.headers_input = AutoCompleteTextEdit(self._user, self._sql_variables)
        self.headers_input.setPlaceholderText(
            "Content-Type: application/json\naccept: application/json\nX-ACCESS-TOKEN: seu_token"
        )
        self.headers_input.setMaximumHeight(100)
        headers_raw = self._data.get("headers", {})
        headers_str = "\n".join(f"{k}: {v}" for k, v in headers_raw.items())
        self.headers_input.setPlainText(headers_str)
        layout.addWidget(self.headers_input)

        lbl = QLabel("Body (JSON)")
        lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600; margin-top: 4px;")
        layout.addWidget(lbl)

        self.body_input = AutoCompleteTextEdit(self._user, self._sql_variables)
        self.body_input.setPlaceholderText(
            '{\n  "phone": "5511999999999",\n  "first_name": "{{nome}}",\n'
            '  "actions": [{"action":"set_field_value","field_name":"nome","value":"{{nome}}"}]\n}'
        )
        self.body_input.setMinimumHeight(160)
        body = self._data.get("body", "")
        if body:
            self.body_input.setPlainText(body)
        layout.addWidget(self.body_input)

        layout.addSpacing(8)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet("font-size: 12px; color: #8b949e; font-weight: 600;")
        type_row.addWidget(type_label)
        self.edit_type = QComboBox()
        self.edit_type.addItems(["Normal", "Cobranca"])
        if self._integration_type == "cobranca":
            self.edit_type.setCurrentText("Cobranca")
        self.edit_type.setStyleSheet(
            "QComboBox { background-color: #0d1117; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 6px; font-size: 12px; "
            "color: #c9d1d9; min-width: 120px; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            "QComboBox::down-arrow { border-left: 4px solid transparent; "
            "border-right: 4px solid transparent; "
            "border-top: 5px solid #8b949e; margin-right: 4px; }"
        )
        type_row.addWidget(self.edit_type)
        type_row.addStretch()
        layout.addLayout(type_row)

        self.active_check = QCheckBox("Integracao ativa")
        self.active_check.setChecked(self._is_active)
        self.active_check.setStyleSheet("font-size: 12px; color: #c9d1d9;")
        layout.addWidget(self.active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _insert_variable(self):
        dlg = VariablePickerDialog(self._sql_variables, self)
        dlg.exec()

    def _import_curl(self):
        dlg = InputDialog(self, "Importar cURL",
            "Cole o comando curl abaixo:", "")
        if dlg.exec() == QDialog.Accepted:
            curl_text = dlg.get_text()
            parsed = self._parse_curl(curl_text)
            if parsed:
                self.method_combo.setCurrentText(parsed.get("method", "POST"))
                self.url_input.setText(parsed.get("url", ""))
                headers_str = "\n".join(
                    f"{k}: {v}" for k, v in parsed.get("headers", {}).items()
                )
                self.headers_input.setPlainText(headers_str)
                body = parsed.get("body", "")
                if body:
                    try:
                        parsed_body = json.loads(body) if isinstance(body, str) else body
                        self.body_input.setPlainText(
                            json.dumps(parsed_body, indent=2, ensure_ascii=False)
                        )
                    except json.JSONDecodeError:
                        self.body_input.setPlainText(body)
                show_success(self, "OK", "cURL importado com sucesso!")
            else:
                show_error(self, "Erro", "Nao foi possivel interpretar o comando cURL.")

    def _parse_curl(self, curl: str) -> dict:
        result = {"method": "GET", "url": "", "headers": {}, "body": None}
        parts = curl.strip().split()
        i = 0
        while i < len(parts):
            p = parts[i]
            if p == "curl":
                i += 1
                continue
            if p.startswith("-") or p.startswith("--"):
                flag = p.lstrip("-")
                i += 1
                if i >= len(parts):
                    break
                val = parts[i].strip("'\"")
                if flag in ("H", "header"):
                    if ":" in val:
                        k, v = val.split(":", 1)
                        result["headers"][k.strip()] = v.strip()
                elif flag in ("X", "request"):
                    result["method"] = val.upper()
                elif flag in ("d", "data", "data-raw"):
                    result["body"] = val
                elif flag in ("compressed", "s", "k", "L", "i", "v", "N"):
                    pass
                i += 1
            elif p.startswith("'") or p.startswith('"'):
                result["url"] = p.strip("'\"")
                i += 1
            elif not result["url"] and not p.startswith("-"):
                result["url"] = p.strip("'\"")
                i += 1
            else:
                i += 1
        return result

    def _validate(self):
        if not self.url_input.text().strip():
            show_error(self, "Erro", "URL e obrigatoria.")
            return
        self.accept()

    def get_data(self) -> dict:
        headers = {}
        for line in self.headers_input.toPlainText().strip().split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        body_raw = self.body_input.toPlainText().strip()
        body = body_raw if body_raw else None
        return {
            "method": self.method_combo.currentText(),
            "url": self.url_input.text().strip(),
            "headers": headers,
            "body": body,
            "is_active": self.active_check.isChecked(),
            "type": "cobranca" if self.edit_type.currentText() == "Cobranca" else "normal",
        }


class ScheduleWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.enabled = QCheckBox("Execucao automatica")
        self.enabled.toggled.connect(self._on_toggle)
        layout.addWidget(self.enabled)

        self.options_frame = QFrame()
        opt = QVBoxLayout(self.options_frame)
        opt.setContentsMargins(0, 0, 0, 0)
        opt.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lbl = QLabel("Repetir:")
        lbl.setStyleSheet("font-size: 12px; color: #8b949e;")
        row1.addWidget(lbl)

        self.preset_combo = QComboBox()
        for key, label in SCHEDULE_PRESETS.items():
            self.preset_combo.addItem(label, key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_change)
        row1.addWidget(self.preset_combo, 1)
        opt.addLayout(row1)

        self.days_frame = QFrame()
        self.days_frame.setVisible(False)
        days_layout = QHBoxLayout(self.days_frame)
        days_layout.setContentsMargins(0, 0, 0, 0)
        days_layout.setSpacing(4)
        lbl = QLabel("Dias:")
        lbl.setStyleSheet("font-size: 12px; color: #8b949e;")
        days_layout.addWidget(lbl)
        self.day_checks = {}
        for d in WEEKDAYS:
            cb = QCheckBox(d)
            cb.setStyleSheet("font-size: 11px;")
            self.day_checks[d] = cb
            days_layout.addWidget(cb)
        days_layout.addStretch()
        opt.addWidget(self.days_frame)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        lbl2 = QLabel("Horario:")
        lbl2.setStyleSheet("font-size: 12px; color: #8b949e;")
        row2.addWidget(lbl2)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(self.time_edit.time().fromString("09:00", "HH:mm"))
        row2.addWidget(self.time_edit)
        row2.addStretch()
        opt.addLayout(row2)

        self.next_run_label = QLabel()
        self.next_run_label.setStyleSheet(
            "font-size: 11px; color: #d29922; padding: 4px 0;"
        )
        opt.addWidget(self.next_run_label)

        self.options_frame.setVisible(False)
        layout.addWidget(self.options_frame)

    def _on_toggle(self, checked: bool):
        self.options_frame.setVisible(checked)
        if not checked:
            self.next_run_label.setText("")

    def _on_preset_change(self):
        preset = self.preset_combo.currentData()
        self.days_frame.setVisible(preset == "weekly")
        self._update_next_run()

    def _update_next_run(self):
        if not self.enabled.isChecked() or not self.preset_combo.currentData():
            self.next_run_label.setText("")
            return
        label = "Agendamento ativo"
        self.next_run_label.setText(label)

    def get_data(self) -> dict:
        if not self.enabled.isChecked():
            return {"schedule_enabled": False}
        days = []
        if self.preset_combo.currentData() == "weekly":
            for i, d in enumerate(WEEKDAYS):
                if self.day_checks[d].isChecked():
                    days.append(i)
        return {
            "schedule_enabled": True,
            "schedule_preset": self.preset_combo.currentData(),
            "schedule_days": days if days else None,
            "schedule_time": self.time_edit.time().toString("HH:mm"),
        }

    def set_data(self, data: dict):
        enabled = data.get("schedule_enabled", False)
        self.enabled.setChecked(enabled)
        if enabled:
            preset = data.get("schedule_preset", "daily")
            for i in range(self.preset_combo.count()):
                if self.preset_combo.itemData(i) == preset:
                    self.preset_combo.setCurrentIndex(i)
                    break
            days = data.get("schedule_days", [])
            for i, d in enumerate(WEEKDAYS):
                self.day_checks[d].setChecked(i in days)
            time_str = data.get("schedule_time", "09:00")
            self.time_edit.setTime(self.time_edit.time().fromString(time_str, "HH:mm"))


class MundoBotsView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._sql_variables = []
        self._setup_ui()
        self._load_sql_variables()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { background: #0d1117; border: none; }
            QTabBar::tab {
                background: transparent; color: #8b949e; border: none;
                padding: 10px 24px; font-size: 13px; font-weight: 500;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
            QTabBar::tab:hover { color: #c9d1d9; }
        """)

        self.tab_list = QWidget()
        self._build_tab_list()
        self.tabs.addTab(self.tab_list, "Integracoes")

        role = self.user.get("role", "")
        if role == "admin":
            self.tab_create = QWidget()
            self._build_tab_create()
            self.tabs.addTab(self.tab_create, "Criar Integracao")

        layout.addWidget(self.tabs)

    def _build_tab_list(self):
        layout = QVBoxLayout(self.tab_list)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Integracoes")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #c9d1d9;")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        desc = QLabel(
            "Gerencie as integracoes cadastradas. Cada integracao define "
            "uma requisicao HTTP que sera enviada para a Mundo dos Bots."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)

        role = self.user.get("role", "")
        self._is_admin = (role == "admin")

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Nome", "Status", "Tipo", "Frequencia",
            "Ultima Exec.", "Proxima Exec.", ""
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(6, 320)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)

    def _build_tab_create(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1f6feb, stop:1 #0d1117);
                border-radius: 8px; padding: 20px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(4)

        title = QLabel("Nova Integracao")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #fff;")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Configure uma requisicao HTTP para enviar mensagens "
            "atraves da API da Mundo dos Bots."
        )
        subtitle.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.7);")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        layout.addWidget(header_frame)

        main_card = QFrame()
        main_card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        main_layout = QVBoxLayout(main_card)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        section_conf = QFrame()
        section_conf.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        conf_layout = QVBoxLayout(section_conf)
        conf_layout.setContentsMargins(16, 14, 16, 14)
        conf_layout.setSpacing(10)

        conf_title = QLabel("Configuracao")
        conf_title.setStyleSheet(
            "font-size: 11px; color: #8b949e; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        conf_layout.addWidget(conf_title)

        self.create_name = QLineEdit()
        self.create_name.setPlaceholderText("Ex: Cobranca pos-compra")
        self.create_name.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 10px 14px; font-size: 13px; "
            "color: #c9d1d9; min-height: 18px;"
        )
        conf_layout.addWidget(self.create_name)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet("font-size: 12px; color: #8b949e; font-weight: 600;")
        type_row.addWidget(type_label)
        self.create_type = QComboBox()
        self.create_type.addItems(["Normal", "Cobranca"])
        self.create_type.setStyleSheet(
            "QComboBox { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 12px; font-size: 13px; "
            "color: #c9d1d9; min-height: 18px; min-width: 120px; }"
            "QComboBox::drop-down { border: none; width: 28px; }"
            "QComboBox::down-arrow { border-left: 4px solid transparent; "
            "border-right: 4px solid transparent; "
            "border-top: 5px solid #8b949e; margin-right: 6px; }"
        )
        type_row.addWidget(self.create_type)
        type_row.addStretch()
        conf_layout.addLayout(type_row)

        main_layout.addWidget(section_conf)

        section_req = QFrame()
        section_req.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        req_layout = QVBoxLayout(section_req)
        req_layout.setContentsMargins(16, 14, 16, 14)
        req_layout.setSpacing(10)

        req_title = QLabel("Requisicao HTTP")
        req_title.setStyleSheet(
            "font-size: 11px; color: #8b949e; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        req_layout.addWidget(req_title)

        var_hint = QLabel(
            "Use {{nome}}, {{telefone}} no body ou headers para parametros "
            "que serao preenchidos na execucao. Clique em \"Inserir Variavel\" "
            "para ver as variaveis disponiveis do banco."
        )
        var_hint.setWordWrap(True)
        var_hint.setStyleSheet(
            "color: #58a6ff; font-size: 11px; background: #0d1117; "
            "border-left: 3px solid #1f6feb; border-radius: 0; padding: 8px 12px;"
        )
        req_layout.addWidget(var_hint)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.create_method = QComboBox()
        self.create_method.addItems(["POST", "GET", "PUT", "DELETE", "PATCH"])
        self.create_method.setCurrentText("POST")
        self.create_method.setStyleSheet(
            "QComboBox { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 12px; font-size: 13px; "
            "color: #c9d1d9; min-height: 18px; min-width: 90px; }"
            "QComboBox::drop-down { border: none; width: 28px; }"
            "QComboBox::down-arrow { border-left: 4px solid transparent; "
            "border-right: 4px solid transparent; "
            "border-top: 5px solid #8b949e; margin-right: 6px; }"
        )
        url_row.addWidget(self.create_method)

        self.create_url = QLineEdit()
        self.create_url.setPlaceholderText("https://exemplo.com/api/endpoint")
        self.create_url.setText("https://app.mundodosbots.com.br/api/users")
        self.create_url.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 14px; font-size: 13px; "
            "color: #c9d1d9; min-height: 18px;"
        )
        url_row.addWidget(self.create_url, 1)

        btn_vars = QPushButton("Inserir Variavel")
        btn_vars.setCursor(Qt.PointingHandCursor)
        btn_vars.setStyleSheet(
            "QPushButton { background: #21262d; border: 1px solid #30363d; "
            "border-radius: 6px; color: #58a6ff; padding: 8px 14px; "
            "font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #30363d; }"
        )
        btn_vars.clicked.connect(self._insert_create_var)
        url_row.addWidget(btn_vars)

        btn_mgr = QPushButton("Gerenciar")
        btn_mgr.setCursor(Qt.PointingHandCursor)
        btn_mgr.setStyleSheet(
            "QPushButton { background: #21262d; border: 1px solid #30363d; "
            "border-radius: 6px; color: #c9d1d9; padding: 8px 14px; "
            "font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #30363d; }"
        )
        btn_mgr.clicked.connect(self._open_var_manager)
        url_row.addWidget(btn_mgr)

        req_layout.addLayout(url_row)

        headers_label = QLabel("HEADERS")
        headers_label.setStyleSheet(
            "font-size: 10px; color: #8b949e; font-weight: 700; "
            "letter-spacing: 0.5px; margin-top: 4px;"
        )
        req_layout.addWidget(headers_label)

        self.create_headers = AutoCompleteTextEdit(self.user, self._sql_variables)
        self.create_headers.setPlaceholderText(
            "Content-Type: application/json\naccept: application/json\nX-ACCESS-TOKEN: seu_token"
        )
        self.create_headers.setMaximumHeight(90)
        self.create_headers.setStyleSheet(
            "QTextEdit { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 10px; font-size: 12px; "
            "color: #c9d1d9; font-family: Consolas; }"
            "QTextEdit:focus { border: 1px solid #1f6feb; }"
        )
        req_layout.addWidget(self.create_headers)

        body_label = QLabel("BODY (JSON)")
        body_label.setStyleSheet(
            "font-size: 10px; color: #8b949e; font-weight: 700; "
            "letter-spacing: 0.5px; margin-top: 4px;"
        )
        req_layout.addWidget(body_label)

        self.create_body = AutoCompleteTextEdit(self.user, self._sql_variables)
        self.create_body.setPlaceholderText(
            '{\n  "phone": "5511999999999",\n  "first_name": "{{nome}}",\n'
            '  "actions": [{"action":"set_field_value","field_name":"nome","value":"{{nome}}"}]\n}'
        )
        self.create_body.setMinimumHeight(180)
        self.create_body.setStyleSheet(
            "QTextEdit { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 12px; font-size: 12px; "
            "color: #c9d1d9; font-family: Consolas; }"
            "QTextEdit:focus { border: 1px solid #1f6feb; }"
        )
        req_layout.addWidget(self.create_body)

        main_layout.addWidget(section_req)

        section_schedule = QFrame()
        section_schedule.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        sched_layout = QVBoxLayout(section_schedule)
        sched_layout.setContentsMargins(16, 14, 16, 14)
        sched_layout.setSpacing(10)

        sched_title = QLabel("Execucao Automatica")
        sched_title.setStyleSheet(
            "font-size: 11px; color: #8b949e; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        sched_layout.addWidget(sched_title)

        self.create_schedule = ScheduleWidget()
        sched_layout.addWidget(self.create_schedule)

        main_layout.addWidget(section_schedule)

        self.btn_save = QPushButton("Criar Integracao")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #1f6feb; color: #fff; border: none; "
            "border-radius: 6px; padding: 12px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #388bfd; }"
            "QPushButton:disabled { background-color: #21262d; color: #484f58; }"
        )
        self.btn_save.clicked.connect(self._create)
        main_layout.addWidget(self.btn_save)

        layout.addWidget(main_card)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout2 = QVBoxLayout(self.tab_create)
        main_layout2.setContentsMargins(0, 0, 0, 0)
        main_layout2.addWidget(scroll)

    def _open_var_manager(self):
        dlg = SqlVariableManagerDialog(self.user, self)
        dlg.exec()

    def _insert_create_var(self):
        dlg = VariablePickerDialog(self._sql_variables, self)
        dlg.exec()

    def _create(self):
        name = self.create_name.text().strip()
        if not name:
            show_error(self, "Erro", "Defina um nome para a integracao.")
            return

        body_raw = self.create_body.toPlainText().strip()
        if not body_raw:
            show_error(self, "Erro", "Defina o corpo da requisicao.")
            return

        body = body_raw

        headers = {}
        for line in self.create_headers.toPlainText().strip().split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()

        url = self.create_url.text().strip()
        method = self.create_method.currentText()

        integ_type = "cobranca" if self.create_type.currentText() == "Cobranca" else "normal"

        payload = {
            "name": name,
            "template_id": None,
            "api_token": headers.get("X-ACCESS-TOKEN", ""),
            "flow_id": "",
            "field_mapping": {},
            "first_name_field": "1",
            "type": integ_type,
            "api_url": url,
            "manual_payload": body,
            "manual_headers": headers if headers else None,
        }
        payload.update(self.create_schedule.get_data())

        self.btn_save.setEnabled(False)
        self.btn_save.setText("Salvando...")

        run_in_thread(
            integration_api.create_integration,
            self._on_created,
            self._on_create_error,
            payload,
        )

    def _on_created(self, result: dict):
        self.btn_save.setEnabled(True)
        self.btn_save.setText("Criar Integracao")
        show_success(self, "OK", "Integracao criada com sucesso!")
        self.create_name.clear()
        self.create_url.setText("https://app.mundodosbots.com.br/api/users")
        self.create_method.setCurrentText("POST")
        self.create_headers.clear()
        self.create_body.clear()
        self.create_schedule.enabled.setChecked(False)
        self.create_schedule.options_frame.setVisible(False)
        self.create_schedule.next_run_label.setText("")
        self.tabs.setCurrentIndex(0)
        self.refresh()

    def _on_create_error(self, error: str):
        self.btn_save.setEnabled(True)
        self.btn_save.setText("Criar Integracao")
        show_error(self, "Erro", error)

    def _load_sql_variables(self):
        try:
            from frontend.app.api.sql_variable_api import list_sql_variables
            eco_empresa = self.user.get("eco_empresa")
            if eco_empresa:
                self._sql_variables = list_sql_variables(company_code=eco_empresa)
            else:
                self._sql_variables = []
        except Exception:
            self._sql_variables = []
        for attr in ('create_headers', 'create_body'):
            editor = getattr(self, attr, None)
            if editor and hasattr(editor, 'set_variables'):
                editor.set_variables(self._sql_variables)

    def refresh(self):
        self._load_sql_variables()
        run_in_thread(
            integration_api.list_integrations,
            self._on_data,
            lambda e: show_error(self, "Erro", str(e)),
        )

    def _on_data(self, integs: list):
        self._populate_table(integs)

    def _populate_table(self, integs: list):
        self.table.setRowCount(0)
        for cfg in integs:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name = cfg.get("name") or cfg.get("template_name") or "Manual"
            self.table.setItem(row, 0, QTableWidgetItem(name))

            active = cfg.get("is_active", False)
            active_item = QTableWidgetItem("Ativo" if active else "Inativo")
            active_item.setForeground(Qt.green if active else Qt.red)
            self.table.setItem(row, 1, active_item)

            integ_type = cfg.get("type", "normal")
            type_label = "Cobranca" if integ_type == "cobranca" else "Normal"
            type_item = QTableWidgetItem(type_label)
            if integ_type == "cobranca":
                type_item.setForeground(QColor("#d29922"))
            self.table.setItem(row, 2, type_item)

            preset = cfg.get("schedule_preset")
            if cfg.get("schedule_enabled") and preset:
                freq = SCHEDULE_PRESETS.get(preset, preset)
                time_str = cfg.get("schedule_time", "09:00")
                if preset in ("weekly",):
                    days = cfg.get("schedule_days", [])
                    if days:
                        day_names = ", ".join(WEEKDAYS[d] for d in days if d < len(WEEKDAYS))
                        freq = f"{freq} ({day_names})"
                freq = f"{freq} as {time_str}"
            else:
                freq = "Nao agendado"
            self.table.setItem(row, 3, QTableWidgetItem(freq))

            last_run = cfg.get("last_run_at")
            if last_run:
                try:
                    dt = datetime.fromisoformat(str(last_run).replace("Z", ""))
                    last_str = dt.strftime("%d/%m %H:%M")
                except Exception:
                    last_str = str(last_run)[:16]
            else:
                last_str = "Nunca"
            self.table.setItem(row, 4, QTableWidgetItem(last_str))

            next_run = cfg.get("next_run_at")
            if next_run and cfg.get("schedule_enabled"):
                try:
                    dt = datetime.fromisoformat(str(next_run).replace("Z", ""))
                    next_str = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    next_str = str(next_run)[:16]
            else:
                next_str = "-"
            self.table.setItem(row, 5, QTableWidgetItem(next_str))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            if self._is_admin:
                btn_rename = QPushButton("Renomear")
                btn_rename.setStyleSheet(
                    "font-size: 12px; padding: 4px 12px; background: transparent; "
                    "border: 1px solid #30363d; border-radius: 4px; color: #8b949e; font-weight: 600;"
                )
                btn_rename.clicked.connect(lambda checked, c=cfg: self._rename(c))
                actions_layout.addWidget(btn_rename)

                btn_edit = QPushButton("Editar")
                btn_edit.setStyleSheet(
                    "font-size: 12px; padding: 4px 12px; background: #21262d; "
                    "border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-weight: 600;"
                )
                btn_edit.clicked.connect(lambda checked, c=cfg: self._edit(c))
                actions_layout.addWidget(btn_edit)

            btn_trigger = QPushButton("Executar")
            btn_trigger.setStyleSheet(
                "font-size: 12px; padding: 4px 12px; background: #1f6feb; "
                "border: none; border-radius: 4px; color: #fff; font-weight: 600;"
            )
            btn_trigger.clicked.connect(lambda checked, c=cfg: self._trigger(c))
            actions_layout.addWidget(btn_trigger)

            if self._is_admin:
                btn_delete = QPushButton("Excluir")
                btn_delete.setStyleSheet(
                    "font-size: 12px; padding: 4px 12px; background: transparent; "
                    "border: 1px solid #f85149; border-radius: 4px; color: #f85149; font-weight: 600;"
                )
                btn_delete.clicked.connect(lambda checked, c=cfg: self._delete(c))
                actions_layout.addWidget(btn_delete)

            actions_layout.addStretch()
            self.table.setCellWidget(row, 6, actions)

    def _edit(self, cfg: dict):
        manual_data = {
            "url": cfg.get("api_url", "https://app.mundodosbots.com.br/api/users"),
            "method": "POST",
            "headers": cfg.get("manual_headers", {}) or {},
            "body": cfg.get("manual_payload", "") or "",
        }
        is_active = cfg.get("is_active", True)
        integ_type = cfg.get("type", "normal")
        dlg = InterfaceEditorDialog(self, manual_data, is_active=is_active, user=self.user, sql_variables=self._sql_variables, integration_type=integ_type)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            headers = data.get("headers", {})
            headers.setdefault("X-ACCESS-TOKEN", cfg.get("api_token", ""))
            payload = {
                "api_url": data.get("url", "https://app.mundodosbots.com.br/api/users"),
                "manual_payload": data.get("body", ""),
                "manual_headers": headers if headers else None,
                "is_active": data.get("is_active", True),
                "type": data.get("type", "normal"),
            }
            run_in_thread(
                integration_api.update_integration,
                lambda r: (
                    show_success(self, "OK", "Integracao atualizada!"),
                    self.refresh(),
                ),
                lambda e: show_error(self, "Erro", str(e)),
                cfg["id"],
                payload,
            )

    def _rename(self, cfg: dict):
        from frontend.app.widgets.dialogs import InputDialog
        current_name = cfg.get("name") or "Manual"
        dlg = InputDialog(self, "Renomear Integracao",
            "Novo nome para a integracao:", current_name)
        if dlg.exec() == QDialog.Accepted:
            new_name = dlg.get_text().strip()
            if new_name and new_name != current_name:
                run_in_thread(
                    integration_api.update_integration,
                    lambda r: (
                        show_success(self, "OK", "Integracao renomeada!"),
                        self.refresh(),
                    ),
                    lambda e: show_error(self, "Erro", str(e)),
                    cfg["id"],
                    {"name": new_name},
                )

    def _trigger(self, cfg: dict):
        payload = cfg.get("manual_payload", "") or ""
        headers = cfg.get("manual_headers", {}) or {}
        url = cfg.get("api_url", "")

        all_data = {"body": payload, "headers": headers, "url": url}
        variables = _extract_variables(all_data)

        if variables:
            dlg = TriggerVariablesDialog(variables, self, sql_variables=self._sql_variables, user=self.user)
            if dlg.exec() != QDialog.Accepted:
                return
            values = dlg.get_values()
            substituted_payload = _substitute_variables(payload, values)
            substituted_headers = _substitute_variables(headers, values)
            try:
                json.loads(substituted_payload)
            except json.JSONDecodeError:
                show_error(self, "JSON Invalido",
                    "O JSON do corpo da requisicao esta invalido apos "
                    "substituir as variaveis. Verifique se todas as "
                    "chaves e valores estao formatados corretamente "
                    '(ex: use "{{var}}" em vez de {{var}}).')
                return
            overrides = {
                "override_payload": substituted_payload,
                "override_headers": substituted_headers,
            }
        else:
            try:
                json.loads(payload)
            except json.JSONDecodeError:
                show_error(self, "JSON Invalido",
                    "O JSON do corpo da requisicao esta invalido. "
                    "Verifique a formatacao antes de executar.")
                return
            overrides = {}

        run_in_thread(
            integration_api.trigger_integration,
            lambda r: (
                show_success(
                    self, "Executado",
                    f'{r.get("sent", 0)} de {r.get("total", 0)} '
                    f'requisicoes enviadas para a API.'
                ),
                self.refresh(),
            ),
            lambda e: show_error(self, "Erro", str(e)),
            cfg["id"],
            overrides,
        )

    def _delete(self, cfg: dict):
        name = cfg.get("template_name", "") or "Manual"
        confirm = show_confirm(
            self, "Confirmar",
            f'Excluir integracao "{name}"?'
        )
        if not confirm:
            return
        run_in_thread(
            integration_api.delete_integration,
            lambda r: (
                show_success(self, "OK", "Integracao excluida!"),
                self.refresh(),
            ),
            lambda e: show_error(self, "Erro", str(e)),
            cfg["id"],
        )
