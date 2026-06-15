import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
    QTextEdit, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget,
)
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.core.theme import theme_manager


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


class VariablePickerDialog(QDialog):
    def __init__(self, variables: list[dict], parent=None):
        super().__init__(parent)
        self._variables = variables
        self.setWindowTitle("Auto-Completion via SQL")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.setStyleSheet("""
            QListWidget::item { padding: 8px 12px; }
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
            "no editor do JSON para ver os valores disponiveis."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px;")
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
            text = f"  {name}  |  {label}"
            item = QListWidgetItem(text)
            item.setToolTip(f"SQL: {v.get('sql_query', '')}")
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
            QTableWidget::item { padding: 6px; }
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
        desc.setStyleSheet("font-size: 12px;")
        layout.addWidget(desc)
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Nova Variavel")
        btn_add.setProperty("primary", True)
        btn_add.clicked.connect(self._add)
        toolbar.addWidget(btn_add)
        btn_refresh = QPushButton("Atualizar")
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
            btn_edit.clicked.connect(lambda checked, vid=v["id"], vd=v: self._edit(vid, vd))
            al.addWidget(btn_edit)
            btn_del = QPushButton("Excluir")
            btn_del.setProperty("danger", True)
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
        confirm = show_confirm(self, "Confirmar", f'Excluir variavel "{var_name}"?')
        if not confirm:
            return
        from frontend.app.api.sql_variable_api import delete_sql_variable
        try:
            delete_sql_variable(var_id)
            show_success(self, "OK", "Variavel excluida!")
            self._load()
        except Exception as e:
            show_error(self, "Erro", str(e))


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
            QPushButton#btnTestSql { font-size: 12px; font-weight: 600; min-width: 100px; }
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
        self.txt_sql.setPlaceholderText("SELECT CODIGO, NOME, TELEFONE FROM CLIENTES")
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
        self.status_label.setStyleSheet("font-size: 12px; padding: 2px 0;")
        form.addRow("", self.status_label)
        val_row = QHBoxLayout()
        self.column_combo = QComboBox()
        self.column_combo.setEnabled(False)
        self.column_combo.addItem("(teste o SQL primeiro)", None)
        val_row.addWidget(self.column_combo, 1)
        hint = QLabel("Colunas anteriores sao exibidas como identificacao no dropdown.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 11px; color: {theme_manager.current().warning};")
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
        t = theme_manager.current()
        self.status_label.setText("Testando...")
        self.status_label.setStyleSheet(f"color: {t.warning}; font-size: 12px; padding: 2px 0;")
        try:
            from frontend.app.core.firebird_client import fb
            col_names, rows = fb.query_with_columns(sql)
        except Exception as e:
            self.status_label.setText(f"Erro: {str(e)[:80]}")
            self.status_label.setStyleSheet(f"color: {t.danger}; font-size: 12px; padding: 2px 0;")
            return
        if not rows or len(rows) <= 1:
            self.status_label.setText("Deve retornar mais de 1 registro")
            self.status_label.setStyleSheet(f"color: {t.danger}; font-size: 12px; padding: 2px 0;")
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
        self.status_label.setStyleSheet(f"color: {t.success}; font-size: 12px; padding: 2px 0;")

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
