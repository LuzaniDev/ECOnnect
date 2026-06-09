import re
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QTextEdit, QListWidget, QFrame, QVBoxLayout
from PySide6.QtGui import QTextCursor


class AutoCompleteTextEdit(QTextEdit):
    variable_chosen = Signal(str)

    def __init__(self, user: dict, variables: list[dict], parent=None):
        super().__init__(parent)
        self._user = user
        self._variables = variables
        self._build_maps(variables)
        self._popup = None
        self._popup_list = None
        self._popup_var_name = None
        self._popup_is_subfield = False
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_complete)
        self.textChanged.connect(self._on_text_changed)

    def _build_maps(self, variables):
        self._var_map = {}
        self._var_col_map = {}
        for v in variables:
            self._var_map[v["name"]] = v["sql_query"]
            self._var_col_map[v["name"]] = v.get("value_column")

    def set_variables(self, variables: list[dict]):
        self._variables = variables
        self._build_maps(variables)

    def _rows_to_items(self, rows, value_column=None):
        items = []
        for r in rows:
            if not r or not r[0]:
                continue
            if len(r) == 1:
                val = str(r[0]).strip()
                items.append((val, val))
            else:
                idx = (value_column - 1) if value_column else (len(r) - 1)
                idx = max(0, min(idx, len(r) - 1))
                value = str(r[idx]).strip()
                parts = [str(c).strip() for i, c in enumerate(r) if c is not None and i != idx]
                label = " | ".join(parts)
                items.append((f"{label} | {value}", value))
        return items

    def _on_text_changed(self):
        self._debounce.start(300)

    def _do_complete(self):
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()[:pos]

        m = re.search(r'([\w.]+)\.$', text)
        if not m:
            self._hide_popup()
            return

        var_name = m.group(1)

        matching_dotted = [k for k in self._var_map if k.startswith(var_name + ".")]
        if matching_dotted:
            subfields = sorted(set(k[len(var_name) + 1:] for k in matching_dotted))
            self._show_popup(var_name, subfields, is_subfield_mode=True, matching_dotted=matching_dotted)
            return

        if var_name in self._var_map:
            try:
                from frontend.app.core.firebird_client import fb
                rows = fb.query(self._var_map[var_name])
                value_column = self._var_col_map.get(var_name)
                items = self._rows_to_items(rows, value_column)
            except Exception:
                self._hide_popup()
                return

            if not items:
                self._hide_popup()
                return

            self._show_popup(var_name, items)
            return

        self._hide_popup()

    def _show_popup(self, var_name: str, values: list, is_subfield_mode: bool = False, matching_dotted: list[str] = None):
        self._hide_popup()
        self._popup_var_name = var_name
        self._popup_is_subfield = is_subfield_mode
        self._popup_matching_keys = matching_dotted or []

        self._popup = QFrame(self)
        self._popup.setWindowFlags(Qt.Popup)
        self._popup.setStyleSheet("""
            QFrame { background: #161b22; border: 1px solid #30363d;
                     border-radius: 6px; }
            QListWidget { background: transparent; color: #c9d1d9;
                          border: none; font-size: 12px; }
            QListWidget::item { padding: 6px 12px; }
            QListWidget::item:selected { background: #1f6feb; color: #fff; }
        """)

        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(0, 0, 0, 0)

        self._popup_list = QListWidget()
        for v in values:
            if isinstance(v, tuple):
                display, actual = v
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, actual)
            else:
                item = QListWidgetItem(v)
            self._popup_list.addItem(item)
        self._popup_list.setCurrentRow(0)
        self._popup_list.itemClicked.connect(self._pick_value)
        self._popup_list.itemActivated.connect(self._pick_value)
        layout.addWidget(self._popup_list)

        cursor_rect = self.cursorRect(self.textCursor())
        global_pos = self.viewport().mapToGlobal(cursor_rect.bottomLeft())
        self._popup.move(global_pos)
        self._popup.setFixedWidth(max(300, cursor_rect.width() * 3))
        self._popup.setFixedHeight(min(250, len(values) * 28 + 4))
        self._popup.show()
        self._popup.setFocus()

    def _hide_popup(self):
        if self._popup:
            self._popup.close()
            self._popup = None
            self._popup_list = None
            self._popup_var_name = None
            self._popup_is_subfield = False
            self._popup_matching_keys = []

    def _pick_value(self, item):
        if item and self._popup_var_name is not None:

            if self._popup_is_subfield:
                subfield = item.text()
                full_name = self._popup_var_name + "." + subfield
                sql = self._var_map.get(full_name, "")
                if sql:
                    try:
                        from frontend.app.core.firebird_client import fb
                        rows = fb.query(sql)
                        value_column = self._var_col_map.get(full_name)
                        items = self._rows_to_items(rows, value_column)
                    except Exception:
                        items = []
                    if items:
                        cursor = self.textCursor()
                        pos = cursor.position()
                        text = self.toPlainText()
                        start = pos - len(self._popup_var_name) - 1
                        if start >= 0:
                            new_text = text[:start] + full_name + "." + text[pos:]
                            self.blockSignals(True)
                            self.setPlainText(new_text)
                            cursor = self.textCursor()
                            cursor.setPosition(start + len(full_name) + 1)
                            self.setTextCursor(cursor)
                            self.blockSignals(False)
                            self._show_popup(full_name, items)
                            return
                self._hide_popup()
                return

            user_data = item.data(Qt.UserRole)
            value = str(user_data) if user_data is not None else item.text()

            cursor = self.textCursor()
            pos = cursor.position()
            text = self.toPlainText()
            start = pos - len(self._popup_var_name) - 1
            if start >= 0:
                new_text = text[:start] + value + text[pos:]
                self.blockSignals(True)
                self.setPlainText(new_text)
                cursor = self.textCursor()
                cursor.setPosition(start + len(value))
                self.setTextCursor(cursor)
                self.blockSignals(False)
                self.variable_chosen.emit(value)
        self._hide_popup()

    def keyPressEvent(self, event):
        if self._popup and self._popup.isVisible():
            key = event.key()
            if key == Qt.Key_Down:
                row = self._popup_list.currentRow()
                self._popup_list.setCurrentRow(min(row + 1, self._popup_list.count() - 1))
                return
            elif key == Qt.Key_Up:
                row = self._popup_list.currentRow()
                self._popup_list.setCurrentRow(max(row - 1, 0))
                return
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self._pick_value(self._popup_list.currentItem())
                return
            elif key == Qt.Key_Escape:
                self._hide_popup()
                return
        super().keyPressEvent(event)
