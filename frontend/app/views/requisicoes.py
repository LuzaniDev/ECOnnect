import html
import json
import re
from datetime import datetime
import httpx
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QTextEdit, QTextBrowser, QCheckBox, QTabWidget,
    QDialog, QDialogButtonBox, QFormLayout, QTimeEdit, QListWidget,
    QListWidgetItem, QProgressBar, QScrollBar,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success, InputDialog
from frontend.app.widgets.autocomplete_textedit import AutoCompleteTextEdit
from frontend.app.widgets.sql_variable_dialogs import VariablePickerDialog, SqlVariableManagerDialog
from frontend.app.api import integration_api
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager, _hex_to_rgb


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
    ],
}


def _extract_variables(data) -> list[str]:
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
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, variables: list[str], parent=None, sql_variables: list[dict] = None, user: dict = None):
        super().__init__(parent)
        self._vars = variables
        self._sql_variables = sql_variables or []
        self._sql_map = {v["name"]: v["sql_query"] for v in self._sql_variables}
        self._sql_col_map = {v["name"]: v.get("value_column") for v in self._sql_variables}
        self.setWindowTitle("Preencher Variaveis")
        self.setMinimumWidth(480)
        t = self._t
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
            QLabel {{ color: {t.text}; }}
            QLineEdit {{
                background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; border-radius: 4px; padding: 6px;
            }}
            QComboBox {{
                background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; border-radius: 4px; padding: 6px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox::down-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {t.text_secondary}; margin-right: 4px;
            }}
        """)
        self._inputs = {}
        self._build()

    def _build(self):
        t = self._t
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel("Preencha os valores das variaveis")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        desc = QLabel("As variaveis abaixo foram encontradas na requisicao. Preencha os valores.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.text_secondary}; font-size: 12px;")
        layout.addWidget(desc)
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 8, 0, 8)
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
                combo.setStyleSheet("font-size: 12px;")
                lbl = QLabel(f"  {{${var}}}")
                lbl.setStyleSheet(f"font-size: 13px; color: {t.accent_blue}; font-weight: 600;")
                form.addRow(lbl, combo)
                self._inputs[var] = combo
            else:
                inp = QLineEdit()
                inp.setPlaceholderText(f"Valor para {var}")
                inp.setStyleSheet("font-size: 12px;")
                lbl = QLabel(f"  {{${var}}}")
                lbl.setStyleSheet(f"font-size: 13px; color: {t.accent_blue}; font-weight: 600;")
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


class AIResponseDialog(QDialog):
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, response_text: str, model: str = "", duration_secs: float = 0.0, parent=None):
        super().__init__(parent)
        self._response_text = response_text
        self._model = model
        self._duration_secs = duration_secs
        self._links = []
        self.setWindowTitle("Resposta da IA")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"QDialog {{ background-color: {self._t.bg}; color: {self._t.text}; }}")
        self._build()

    def _markdown_to_html(self, text: str) -> str:
        lines = text.split("\n")
        html_parts = []
        in_list = False
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("### "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped.startswith("## "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("# "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped == "---":
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append("<hr>")
            elif stripped.startswith("* ") or stripped.startswith("- "):
                content = stripped[2:]
                content = self._inline_html(content)
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"<li>{content}</li>")
            elif stripped.startswith("1. ") or stripped.startswith("2. ") or stripped.startswith("3. "):
                content = stripped[3:]
                content = self._inline_html(content)
                if not in_list:
                    html_parts.append("<ol>")
                    in_list = True
                html_parts.append(f"<li>{content}</li>")
            elif stripped == "":
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append("<br>")
            else:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                processed = self._inline_html(stripped)
                html_parts.append(f"<p>{processed}</p>")
            i += 1

        if in_list:
            html_parts.append("</ul>")

        return "\n".join(html_parts)

    def _inline_html(self, text: str) -> str:
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace('"', "&quot;")

        def replace_bold(m):
            return f"<b>{m.group(1)}</b>"

        def replace_link(m):
            link_text = m.group(1)
            url = m.group(2)
            self._links.append((link_text, url))
            return f'<a href="{url}" style="color: {self._t.accent_blue}; text-decoration: underline;">{link_text}</a>'

        text = re.sub(r'\*\*(.+?)\*\*', replace_bold, text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)

        url_pattern = re.compile(r'(https?://[^\s\)]+)')
        text = url_pattern.sub(r'<a href="\1" style="color: {0}; text-decoration: underline;">\1</a>'.format(self._t.accent_blue), text)

        return text

    def _build(self):
        t = self._t
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Resposta da IA")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {t.text};")
        layout.addWidget(title)

        html_content = self._markdown_to_html(self._response_text)
        html_doc = f"""<!DOCTYPE html>
<html>
<body style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: {t.text}; background-color: {t.bg}; line-height: 1.6;">
{html_content}
</body>
</html>"""

        browser = QTextBrowser()
        browser.setHtml(html_doc)
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(f"QTextBrowser {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 16px; color: {t.text}; }}")
        browser.setMinimumHeight(280)
        layout.addWidget(browser, 1)

        if self._links:
            ref_frame = QFrame()
            ref_frame.setStyleSheet(f"QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 12px; }}")
            ref_layout = QVBoxLayout(ref_frame)
            ref_layout.setContentsMargins(12, 10, 12, 10)
            ref_layout.setSpacing(6)
            ref_title = QLabel("Referências")
            ref_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {t.text};")
            ref_layout.addWidget(ref_title)
            for link_text, url in self._links:
                link_label = QLabel(f'<a href="{url}" style="color: {t.accent_blue}; font-size: 12px;">{link_text}</a>')
                link_label.setOpenExternalLinks(True)
                link_label.setWordWrap(True)
                ref_layout.addWidget(link_label)
            layout.addWidget(ref_frame)

        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        meta_parts = []
        if self._model:
            meta_parts.append(f"Modelo: {self._model}")
        if self._duration_secs > 0:
            meta_parts.append(f"Duração: {self._duration_secs:.1f}s")
        meta_text = " | ".join(meta_parts) if meta_parts else ""
        if meta_text:
            meta_label = QLabel(meta_text)
            meta_label.setStyleSheet(f"color: {t.text_secondary}; font-size: 11px;")
            footer_layout.addWidget(meta_label)
        footer_layout.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"QPushButton {{ background-color: {t.primary}; color: {t.selection_text}; border: none; border-radius: 4px; padding: 8px 20px; font-size: 13px; font-weight: 600; }} QPushButton:hover {{ background-color: {t.primary_hover}; }}")
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)
        layout.addWidget(footer)


class N8nResponseDialog(QDialog):
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._data = data
        self.setWindowTitle("Resposta n8n")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"QDialog {{ background-color: {self._t.bg}; color: {self._t.text}; }}")
        self._build()

    def _build(self):
        t = self._t
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Resposta do n8n")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {t.text};")
        layout.addWidget(title)

        base = self._data.get("base_conhecimento", [])
        uar = self._data.get("uar_solicitacoes", [])
        total_base = self._data.get("total_base", 0)
        total_uar = self._data.get("total_uar", 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        container.setStyleSheet(f"background: transparent;")
        sections = QVBoxLayout(container)
        sections.setSpacing(16)

        if base:
            base_frame = self._make_section(
                "Base de Conhecimento", base, total_base, t
            )
            sections.addWidget(base_frame)

        if uar:
            uar_frame = self._make_section(
                "UAR Solicitações", uar, total_uar, t
            )
            sections.addWidget(uar_frame)

        if not base and not uar:
            raw = json.dumps(self._data, indent=2, ensure_ascii=False)
            browser = QTextBrowser()
            browser.setPlainText(raw)
            browser.setStyleSheet(f"QTextBrowser {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 14px; font-size: 12px; color: {t.text}; font-family: 'Consolas', monospace; }}")
            browser.setMinimumHeight(200)
            sections.addWidget(browser)

        sections.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        if total_base or total_uar:
            info = QLabel(f"Total: {total_base} base(s) | {total_uar} UAR")
            info.setStyleSheet(f"color: {t.text_secondary}; font-size: 12px;")
            footer.addWidget(info)
        footer.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"QPushButton {{ background-color: {t.primary}; color: {t.selection_text}; border: none; border-radius: 4px; padding: 8px 20px; font-size: 13px; font-weight: 600; }} QPushButton:hover {{ background-color: {t.primary_hover}; }}")
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    def _make_section(self, section_title: str, items: list, total: int, t) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QLabel(f"{section_title} ({total})")
        header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {t.text};")
        layout.addWidget(header)

        for item in items:
            titulo = self._clean_text(item.get("titulo", ""))
            link = self._clean_text(item.get("link", ""))
            if not titulo:
                continue
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background-color: {t.bg}; border: 1px solid {t.surface_elevated}; border-radius: 4px; padding: 8px; }}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)

            lbl_titulo = QLabel(titulo)
            lbl_titulo.setWordWrap(True)
            lbl_titulo.setStyleSheet(f"font-size: 12px; color: {t.text}; font-weight: 600;")
            card_layout.addWidget(lbl_titulo)

            if link and link != "#" and not link.startswith("#"):
                lbl_link = QLabel(f'<a href="{link}" style="color: {t.accent_blue}; font-size: 11px;">{link}</a>')
                lbl_link.setOpenExternalLinks(True)
                lbl_link.setWordWrap(True)
                card_layout.addWidget(lbl_link)

            layout.addWidget(card)

        return frame


class N8nWorker(QObject):
    finished = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, config_id, overrides):
        super().__init__()
        self.config_id = config_id
        self.overrides = overrides
        self._aborted = False

    def abort(self):
        self._aborted = True

    def run(self):
        if self._aborted:
            return
        try:
            result = integration_api.trigger_integration(self.config_id, self.overrides)
            if not self._aborted:
                self.finished.emit(result)
        except Exception as e:
            if not self._aborted:
                self.error_occurred.emit(str(e))


class N8nLoadingDialog(QDialog):
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, config_id, overrides, parent=None):
        super().__init__(parent)
        self._config_id = config_id
        self._overrides = overrides
        self._result = None
        self.setWindowTitle("n8n - Aguardando resposta...")
        self.setMinimumSize(480, 200)
        t = self._t
        self.setStyleSheet(f"QDialog {{ background-color: {t.bg}; color: {t.text}; }}")
        self._build()
        self._start_worker()

    def _build(self):
        t = self._t
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Aguardando resposta do n8n...")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {t.text};")
        layout.addWidget(title)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(20)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background-color: {t.surface}; border: 1px solid {t.border};
                border-radius: 4px; text-align: center; font-size: 10px; color: {t.text_secondary}; }}
            QProgressBar::chunk {{ background-color: {t.primary}; border-radius: 3px; }}
        """)
        layout.addWidget(self._progress)

        btn_layout = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setCursor(Qt.PointingHandCursor)
        self._btn_cancel.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {t.danger}; border-radius: 4px; padding: 8px 18px; font-size: 12px; color: {t.danger}; }} QPushButton:hover {{ background-color: {t.danger}22; }}")
        self._btn_cancel.clicked.connect(self._cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_cancel)
        layout.addLayout(btn_layout)

    def _start_worker(self):
        self._worker = N8nWorker(self._config_id, self._overrides)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_finished(self, result):
        self._result = result
        self._thread.quit()
        self._worker.deleteLater()
        self.accept()

    def _on_error(self, error):
        self._thread.quit()
        self._worker.deleteLater()
        show_error(self, "Erro", error)
        self.reject()

    def _cancel(self):
        self._worker.abort()
        self._thread.quit()
        self._worker.deleteLater()
        self.reject()

    def get_result(self):
        return self._result


class StreamWorker(QObject):
    token_received = Signal(str)
    finished = Signal(str, str, float)
    error_occurred = Signal(str)

    def __init__(self, config_id, overrides):
        super().__init__()
        self.config_id = config_id
        self.overrides = overrides
        self._aborted = False

    def abort(self):
        self._aborted = True

    def run(self):
        try:
            from frontend.app.api.client import client as api_client

            url = f"{api_client.base_url}/api/integrations/{self.config_id}/trigger-stream"
            headers = {"Content-Type": "application/json"}
            if api_client._token:
                headers["Authorization"] = f"Bearer {api_client._token}"

            with httpx.Client(timeout=600) as http:
                with http.stream("POST", url, json=self.overrides, headers=headers) as resp:
                    resp.raise_for_status()
                    full_text = ""
                    model = ""
                    duration = 0

                    for line in resp.iter_lines():
                        if self._aborted:
                            return
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data.get("done"):
                                full_text = data.get("full_response", full_text)
                                model = data.get("model", model)
                                duration = data.get("total_duration", duration)
                                self.finished.emit(full_text, model, duration / 1_000_000_000.0)
                                return
                            if "error" in data:
                                self.error_occurred.emit(data["error"])
                                return
                            token = data.get("token", "")
                            full_text += token
                            self.token_received.emit(token)
        except Exception as e:
            self.error_occurred.emit(str(e))


class StreamDialog(QDialog):
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, config_id, overrides, parent=None):
        super().__init__(parent)
        self._config_id = config_id
        self._overrides = overrides
        self._result = None
        self.setWindowTitle("IA - Gerando Resposta...")
        self.setMinimumSize(620, 420)
        t = self._t
        self.setStyleSheet(f"QDialog {{ background-color: {t.bg}; color: {t.text}; }}")
        self._build()
        self._start_stream()

    def _build(self):
        t = self._t
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Gerando resposta com IA...")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {t.text};")
        header.addWidget(title)
        header.addStretch()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(160)
        self._progress.setFixedHeight(20)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 4px; text-align: center; font-size: 10px; color: {t.text_secondary}; }}
            QProgressBar::chunk {{ background-color: {t.primary}; border-radius: 3px; }}
        """)
        header.addWidget(self._progress)
        layout.addLayout(header)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t.surface}; border: 1px solid {t.border};
                border-radius: 6px; padding: 14px; font-size: 13px;
                color: {t.text}; font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)
        self._text_edit.setMinimumHeight(280)
        layout.addWidget(self._text_edit, 1)

        btn_layout = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setCursor(Qt.PointingHandCursor)
        self._btn_cancel.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {t.danger}; border-radius: 4px; color: {t.danger}; padding: 8px 20px; font-size: 13px; font-weight: 600; }} QPushButton:hover {{ background: {t.danger}; color: {t.selection_text}; }}")
        self._btn_cancel.clicked.connect(self._cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_cancel)
        layout.addLayout(btn_layout)

    def _start_stream(self):
        self._worker = StreamWorker(self._config_id, self._overrides)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._worker.token_received.connect(self._on_token)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_token(self, token):
        self._text_edit.insertPlainText(token)
        sb = self._text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, full_text, model, duration):
        self._result = (full_text, model, duration)
        self._thread.quit()
        self._worker.deleteLater()
        self.accept()

    def _on_error(self, error):
        self._thread.quit()
        self._worker.deleteLater()
        show_error(self, "Erro", error)
        self.reject()

    def _cancel(self):
        self._worker.abort()
        self._thread.quit()
        self._worker.deleteLater()
        self.reject()

    def get_result(self):
        return self._result


class InterfaceEditorDialog(QDialog):
    @property
    def _t(self):
        return theme_manager.current()

    def __init__(self, parent=None, data: dict = None, is_active: bool = True, user: dict = None, sql_variables: list[dict] = None, integration_type: str = "normal"):
        super().__init__(parent)
        self._user = user or {}
        self._sql_variables = sql_variables or []
        self._integration_type = integration_type
        self.setWindowTitle("Editor de Requisicao")
        self.setMinimumSize(640, 560)
        t = self._t
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
            QLabel {{ color: {t.text}; }}
            QTextEdit, QLineEdit, QComboBox {{
                background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; border-radius: 4px; padding: 6px;
            }}
        """)
        self._data = data or {}
        self._is_active = is_active
        self._build()

    def _build(self):
        t = self._t
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
        var_hint.setStyleSheet(f"color: {t.warning}; font-size: 11px; background: {t.surface}; border: 1px solid {t.border}; border-radius: 4px; padding: 6px;")
        layout.addWidget(var_hint)
        btn_vars = QPushButton("Inserir Variavel do Banco")
        btn_vars.setCursor(Qt.PointingHandCursor)
        btn_vars.setStyleSheet(f"background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 4px; color: {t.accent_blue}; padding: 6px 14px; font-size: 12px;")
        btn_vars.clicked.connect(self._insert_variable)
        layout.addWidget(btn_vars, alignment=Qt.AlignLeft)
        btn_import = QPushButton("Importar cURL")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setStyleSheet(f"background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 4px; color: {t.text}; padding: 6px 14px; font-size: 12px;")
        btn_import.clicked.connect(self._import_curl)
        layout.addWidget(btn_import, alignment=Qt.AlignLeft)
        row1 = QHBoxLayout()
        lbl = QLabel("Metodo:")
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600;")
        row1.addWidget(lbl)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["POST", "GET", "PUT", "DELETE", "PATCH"])
        self.method_combo.setCurrentText(self._data.get("method", "POST"))
        row1.addWidget(self.method_combo)
        lbl = QLabel("URL:")
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600;")
        row1.addWidget(lbl)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://exemplo.com/api/endpoint")
        self.url_input.setText(self._data.get("url", "https://app.mundodosbots.com.br/api/users"))
        row1.addWidget(self.url_input, 1)
        layout.addLayout(row1)
        lbl = QLabel("Headers (um por linha: Chave: Valor)")
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600; margin-top: 4px;")
        layout.addWidget(lbl)
        self.headers_input = AutoCompleteTextEdit(self._user, self._sql_variables)
        self.headers_input.setPlaceholderText("Content-Type: application/json\naccept: application/json\nX-ACCESS-TOKEN: seu_token")
        self.headers_input.setMaximumHeight(100)
        headers_raw = self._data.get("headers", {})
        headers_str = "\n".join(f"{k}: {v}" for k, v in headers_raw.items())
        self.headers_input.setPlainText(headers_str)
        layout.addWidget(self.headers_input)
        lbl = QLabel("Body (JSON)")
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600; margin-top: 4px;")
        layout.addWidget(lbl)
        self.body_input = AutoCompleteTextEdit(self._user, self._sql_variables)
        self.body_input.setPlaceholderText('{\n  "phone": "5511999999999",\n  "first_name": "{{nome}}"\n}')
        self.body_input.setMinimumHeight(160)
        body = self._data.get("body", "")
        if body:
            self.body_input.setPlainText(body)
        layout.addWidget(self.body_input)
        layout.addSpacing(8)
        type_row = QHBoxLayout()
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; font-weight: 600;")
        type_row.addWidget(type_label)
        self.edit_type = QComboBox()
        self.edit_type.addItems(["Normal", "Cobranca", "IA", "n8n"])
        if self._integration_type == "cobranca":
            self.edit_type.setCurrentText("Cobranca")
        elif self._integration_type == "ia":
            self.edit_type.setCurrentText("IA")
        elif self._integration_type == "n8n":
            self.edit_type.setCurrentText("n8n")
        self.edit_type.setStyleSheet(f"QComboBox {{ background-color: {t.bg}; border: 1px solid {t.border}; border-radius: 4px; padding: 6px; font-size: 12px; color: {t.text}; min-width: 120px; }} QComboBox::drop-down {{ border: none; width: 24px; }} QComboBox::down-arrow {{ border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {t.text_secondary}; margin-right: 4px; }}")
        type_row.addWidget(self.edit_type)
        type_row.addStretch()
        layout.addLayout(type_row)
        self.active_check = QCheckBox("Integracao ativa")
        self.active_check.setChecked(self._is_active)
        self.active_check.setStyleSheet(f"font-size: 12px; color: {t.text};")
        layout.addWidget(self.active_check)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _insert_variable(self):
        dlg = VariablePickerDialog(self._sql_variables, self)
        dlg.exec()

    def _import_curl(self):
        dlg = InputDialog(self, "Importar cURL", "Cole o comando curl abaixo:", "")
        if dlg.exec() == QDialog.Accepted:
            curl_text = dlg.get_text()
            parsed = self._parse_curl(curl_text)
            if parsed:
                self.method_combo.setCurrentText(parsed.get("method", "POST"))
                self.url_input.setText(parsed.get("url", ""))
                headers_str = "\n".join(f"{k}: {v}" for k, v in parsed.get("headers", {}).items())
                self.headers_input.setPlainText(headers_str)
                body = parsed.get("body", "")
                if body:
                    try:
                        parsed_body = json.loads(body) if isinstance(body, str) else body
                        self.body_input.setPlainText(json.dumps(parsed_body, indent=2, ensure_ascii=False))
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
        return {
            "method": self.method_combo.currentText(),
            "url": self.url_input.text().strip(),
            "headers": headers,
            "body": body_raw if body_raw else None,
            "is_active": self.active_check.isChecked(),
            "type": "ia" if self.edit_type.currentText() == "IA" else ("n8n" if self.edit_type.currentText() == "n8n" else ("cobranca" if self.edit_type.currentText() == "Cobranca" else "normal")),
        }


class ScheduleWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        t = theme_manager.current()
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
        lbl = QLabel("Repetir:")
        lbl.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")
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
        lbl.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")
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
        lbl2 = QLabel("Horario:")
        lbl2.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")
        row2.addWidget(lbl2)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(self.time_edit.time().fromString("09:00", "HH:mm"))
        row2.addWidget(self.time_edit)
        row2.addStretch()
        opt.addLayout(row2)
        self.next_run_label = QLabel()
        self.next_run_label.setStyleSheet(f"font-size: 11px; color: {t.warning}; padding: 4px 0;")
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


class RequisicoesView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._sql_variables = []
        self._setup_ui()
        self._load_sql_variables()

    def _setup_ui(self):
        t = theme_manager.current()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: {t.bg}; border: none; }}
            QTabBar::tab {{
                background: transparent; color: {t.text_secondary}; border: none;
                padding: 10px 24px; font-size: 13px; font-weight: 500;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{ color: {t.accent_blue}; border-bottom: 2px solid {t.accent_blue}; }}
            QTabBar::tab:hover {{ color: {t.text}; }}
        """)
        self.tab_list = QWidget()
        self._build_tab_list()
        self.tabs.addTab(self.tab_list, "Requisições")
        role = self.user.get("role", "")
        if role == "admin":
            self.tab_create = QWidget()
            self._build_tab_create()
            self.tabs.addTab(self.tab_create, "Criar Requisição")
        layout.addWidget(self.tabs)

    def _build_tab_list(self):
        t = theme_manager.current()
        layout = QVBoxLayout(self.tab_list)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel("Requisições")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {t.text};")
        header.addWidget(title)
        header.addStretch()
        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)
        desc = QLabel("Gerencie as requisicoes HTTP cadastradas para envio de mensagens.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.text_secondary}; font-size: 12px;")
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
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)

    def _build_tab_create(self):
        t = theme_manager.current()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        header_frame = QFrame()
        header_frame.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t.primary}, stop:1 {t.bg}); border-radius: 8px; padding: 20px;")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(4)
        title = QLabel("Nova Requisição")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.selection_text};")
        header_layout.addWidget(title)
        subtitle = QLabel("Configure uma requisicao HTTP para enviar mensagens atraves de provedores de API.")
        subtitle.setStyleSheet(f"font-size: 12px; color: rgba({_hex_to_rgb(t.selection_text)},0.7);")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_frame)
        main_card = QFrame()
        main_card.setStyleSheet(f"QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}")
        main_layout = QVBoxLayout(main_card)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        section_conf = QFrame()
        section_conf.setStyleSheet(f"QFrame {{ background-color: {t.bg}; border: 1px solid {t.surface_elevated}; border-radius: 6px; }}")
        conf_layout = QVBoxLayout(section_conf)
        conf_layout.setContentsMargins(16, 14, 16, 14)
        conf_layout.setSpacing(10)
        conf_title = QLabel("Configuracao")
        conf_title.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
        conf_layout.addWidget(conf_title)
        self.create_name = QLineEdit()
        self.create_name.setPlaceholderText("Ex: Cobranca pos-compra")
        self.create_name.setStyleSheet(f"background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 10px 14px; font-size: 13px; color: {t.text}; min-height: 18px;")
        conf_layout.addWidget(self.create_name)
        type_row = QHBoxLayout()
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; font-weight: 600;")
        type_row.addWidget(type_label)
        self.create_type = QComboBox()
        self.create_type.addItems(["Normal", "Cobranca", "IA", "n8n"])
        self.create_type.setStyleSheet(f"QComboBox {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 8px 12px; font-size: 13px; color: {t.text}; min-height: 18px; min-width: 120px; }} QComboBox::drop-down {{ border: none; width: 28px; }} QComboBox::down-arrow {{ border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {t.text_secondary}; margin-right: 6px; }}")
        type_row.addWidget(self.create_type)
        type_row.addStretch()
        conf_layout.addLayout(type_row)
        self.create_type.currentTextChanged.connect(self._on_create_type_changed)
        main_layout.addWidget(section_conf)
        section_req = QFrame()
        section_req.setStyleSheet(f"QFrame {{ background-color: {t.bg}; border: 1px solid {t.surface_elevated}; border-radius: 6px; }}")
        req_layout = QVBoxLayout(section_req)
        req_layout.setContentsMargins(16, 14, 16, 14)
        req_layout.setSpacing(10)
        req_title = QLabel("Requisicao HTTP")
        req_title.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
        req_layout.addWidget(req_title)
        var_hint = QLabel("Use {{nome}}, {{telefone}} no body ou headers. Clique em \"Inserir Variavel\" para ver as variaveis disponiveis do banco.")
        var_hint.setWordWrap(True)
        var_hint.setStyleSheet(f"color: {t.accent_blue}; font-size: 11px; background: {t.bg}; border-left: 3px solid {t.primary}; border-radius: 0; padding: 8px 12px;")
        req_layout.addWidget(var_hint)
        url_row = QHBoxLayout()
        self.create_method = QComboBox()
        self.create_method.addItems(["POST", "GET", "PUT", "DELETE", "PATCH"])
        self.create_method.setCurrentText("POST")
        self.create_method.setStyleSheet(f"QComboBox {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 8px 12px; font-size: 13px; color: {t.text}; min-height: 18px; min-width: 90px; }} QComboBox::drop-down {{ border: none; width: 28px; }} QComboBox::down-arrow {{ border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {t.text_secondary}; margin-right: 6px; }}")
        url_row.addWidget(self.create_method)
        self.create_url = QLineEdit()
        self.create_url.setPlaceholderText("https://exemplo.com/api/endpoint")
        self.create_url.setText("https://app.mundodosbots.com.br/api/users")
        self.create_url.setStyleSheet(f"background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 8px 14px; font-size: 13px; color: {t.text}; min-height: 18px;")
        url_row.addWidget(self.create_url, 1)
        btn_vars = QPushButton("Inserir Variavel")
        btn_vars.setCursor(Qt.PointingHandCursor)
        btn_vars.setStyleSheet(f"QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 6px; color: {t.accent_blue}; padding: 8px 14px; font-size: 12px; font-weight: 600; }} QPushButton:hover {{ background: {t.border}; }}")
        btn_vars.clicked.connect(self._insert_create_var)
        url_row.addWidget(btn_vars)
        btn_mgr = QPushButton("Gerenciar")
        btn_mgr.setCursor(Qt.PointingHandCursor)
        btn_mgr.setStyleSheet(f"QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 6px; color: {t.text}; padding: 8px 14px; font-size: 12px; font-weight: 600; }} QPushButton:hover {{ background: {t.border}; }}")
        btn_mgr.clicked.connect(self._open_var_manager)
        url_row.addWidget(btn_mgr)
        req_layout.addLayout(url_row)
        headers_label = QLabel("HEADERS")
        headers_label.setStyleSheet(f"font-size: 10px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px; margin-top: 4px;")
        req_layout.addWidget(headers_label)
        self.create_headers = AutoCompleteTextEdit(self.user, self._sql_variables)
        self.create_headers.setPlaceholderText("Content-Type: application/json\naccept: application/json\nX-ACCESS-TOKEN: seu_token")
        self.create_headers.setMaximumHeight(90)
        self.create_headers.setStyleSheet(f"QTextEdit {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 10px; font-size: 12px; color: {t.text}; font-family: Consolas; }} QTextEdit:focus {{ border: 1px solid {t.primary}; }}")
        req_layout.addWidget(self.create_headers)
        body_label = QLabel("BODY (JSON)")
        body_label.setStyleSheet(f"font-size: 10px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px; margin-top: 4px;")
        req_layout.addWidget(body_label)
        self.create_body = AutoCompleteTextEdit(self.user, self._sql_variables)
        self.create_body.setPlaceholderText('{\n  "phone": "5511999999999",\n  "first_name": "{{nome}}"\n}')
        self.create_body.setMinimumHeight(180)
        self.create_body.setStyleSheet(f"QTextEdit {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 6px; padding: 12px; font-size: 12px; color: {t.text}; font-family: Consolas; }} QTextEdit:focus {{ border: 1px solid {t.primary}; }}")
        req_layout.addWidget(self.create_body)
        main_layout.addWidget(section_req)
        section_schedule = QFrame()
        section_schedule.setStyleSheet(f"QFrame {{ background-color: {t.bg}; border: 1px solid {t.surface_elevated}; border-radius: 6px; }}")
        sched_layout = QVBoxLayout(section_schedule)
        sched_layout.setContentsMargins(16, 14, 16, 14)
        sched_layout.setSpacing(10)
        sched_title = QLabel("Execucao Automatica")
        sched_title.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
        sched_layout.addWidget(sched_title)
        self.create_schedule = ScheduleWidget()
        sched_layout.addWidget(self.create_schedule)
        main_layout.addWidget(section_schedule)
        self.btn_save = QPushButton("Criar Requisição")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"QPushButton {{ background-color: {t.primary}; color: {t.selection_text}; border: none; border-radius: 6px; padding: 12px; font-size: 14px; font-weight: 700; }} QPushButton:hover {{ background-color: {t.primary_hover}; }} QPushButton:disabled {{ background-color: {t.surface_elevated}; color: {t.text_muted}; }}")
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
            show_error(self, "Erro", "Defina um nome para a requisicao.")
            return
        body_raw = self.create_body.toPlainText().strip()
        if not body_raw:
            show_error(self, "Erro", "Defina o corpo da requisicao.")
            return
        headers = {}
        for line in self.create_headers.toPlainText().strip().split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        url = self.create_url.text().strip()
        integ_type = "ia" if self.create_type.currentText() == "IA" else ("n8n" if self.create_type.currentText() == "n8n" else ("cobranca" if self.create_type.currentText() == "Cobranca" else "normal"))
        payload = {
            "name": name,
            "template_id": None,
            "api_token": headers.get("X-ACCESS-TOKEN", ""),
            "flow_id": "",
            "field_mapping": {},
            "first_name_field": "1",
            "type": integ_type,
            "api_url": url,
            "manual_payload": body_raw,
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
        self.btn_save.setText("Criar Requisição")
        show_success(self, "OK", "Requisição criada com sucesso!")
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
        self.btn_save.setText("Criar Requisição")
        show_error(self, "Erro", error)

    def _on_create_type_changed(self, text: str):
        if text == "IA":
            self.create_url.setText("http://192.168.1.94:11434/api/generate")
        elif text == "n8n":
            self.create_url.setText("http://seu-n8n.com/webhook/")

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
        t = theme_manager.current()
        self.table.setRowCount(0)
        for cfg in integs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = cfg.get("name") or cfg.get("template_name") or "Manual"
            self.table.setItem(row, 0, QTableWidgetItem(name))
            active = cfg.get("is_active", False)
            active_item = QTableWidgetItem("Ativo" if active else "Inativo")
            active_item.setForeground(QColor(t.success) if active else QColor(t.danger))
            self.table.setItem(row, 1, active_item)
            integ_type = cfg.get("type", "normal")
            if integ_type == "ia":
                type_label = "IA"
            elif integ_type == "n8n":
                type_label = "n8n"
            elif integ_type == "cobranca":
                type_label = "Cobranca"
            else:
                type_label = "Normal"
            type_item = QTableWidgetItem(type_label)
            if integ_type == "cobranca":
                type_item.setForeground(QColor(t.warning))
            elif integ_type == "ia" or integ_type == "n8n":
                type_item.setForeground(QColor(t.accent_blue))
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
                btn_rename.setStyleSheet(f"font-size: 12px; padding: 4px 12px; background: transparent; border: 1px solid {t.border}; border-radius: 4px; color: {t.text_secondary}; font-weight: 600;")
                btn_rename.clicked.connect(lambda checked, c=cfg: self._rename(c))
                actions_layout.addWidget(btn_rename)
                btn_edit = QPushButton("Editar")
                btn_edit.setStyleSheet(f"font-size: 12px; padding: 4px 12px; background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 4px; color: {t.text}; font-weight: 600;")
                btn_edit.clicked.connect(lambda checked, c=cfg: self._edit(c))
                actions_layout.addWidget(btn_edit)
            btn_trigger = QPushButton("Executar")
            btn_trigger.setStyleSheet(f"font-size: 12px; padding: 4px 12px; background: {t.primary}; border: none; border-radius: 4px; color: {t.selection_text}; font-weight: 600;")
            btn_trigger.clicked.connect(lambda checked, c=cfg: self._trigger(c))
            actions_layout.addWidget(btn_trigger)
            if self._is_admin:
                btn_delete = QPushButton("Excluir")
                btn_delete.setStyleSheet(f"font-size: 12px; padding: 4px 12px; background: transparent; border: 1px solid {t.danger}; border-radius: 4px; color: {t.danger}; font-weight: 600;")
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
                lambda r: (show_success(self, "OK", "Requisição atualizada!"), self.refresh()),
                lambda e: show_error(self, "Erro", str(e)),
                cfg["id"],
                payload,
            )

    def _rename(self, cfg: dict):
        current_name = cfg.get("name") or "Manual"
        dlg = InputDialog(self, "Renomear", "Novo nome:", current_name)
        if dlg.exec() == QDialog.Accepted:
            new_name = dlg.get_text().strip()
            if new_name and new_name != current_name:
                run_in_thread(
                    integration_api.update_integration,
                    lambda r: (show_success(self, "OK", "Renomeada!"), self.refresh()),
                    lambda e: show_error(self, "Erro", str(e)),
                    cfg["id"],
                    {"name": new_name},
                )

    def _trigger(self, cfg: dict):
        payload = cfg.get("manual_payload", "") or ""
        headers = cfg.get("manual_headers", {}) or {}
        url = cfg.get("api_url", "")
        integ_type = cfg.get("type", "normal")
        if integ_type == "ia":
            all_data = {"body": payload, "url": url}
        else:
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
                show_error(self, "JSON Invalido", "O JSON do corpo esta invalido apos substituir as variaveis.")
                return
            overrides = {"override_payload": substituted_payload, "override_headers": substituted_headers}
        else:
            try:
                json.loads(payload)
            except json.JSONDecodeError:
                show_error(self, "JSON Invalido", "O JSON do corpo esta invalido.")
                return
            overrides = {"override_payload": payload, "override_headers": headers}
        if integ_type == "ia":
            try:
                parsed = json.loads(overrides.get("override_payload", payload))
                use_stream = parsed.get("stream", False)
            except (json.JSONDecodeError, TypeError):
                use_stream = False
        else:
            use_stream = False

        if use_stream:
            self._trigger_stream(cfg["id"], overrides)
        elif integ_type == "n8n":
            dlg = N8nLoadingDialog(cfg["id"], overrides, self)
            if dlg.exec() == QDialog.Accepted:
                r = dlg.get_result()
                if r:
                    self._show_n8n_response(r)
            self.refresh()
        else:
            if integ_type == "ia":
                callback = lambda r: (
                    self._show_ai_response(r),
                    self.refresh(),
                )
            else:
                callback = lambda r: (
                    show_success(self, "Executado", f'{r.get("sent", 0)} de {r.get("total", 0)} requisicoes enviadas.'),
                    self.refresh(),
                )
            run_in_thread(
                integration_api.trigger_integration,
                callback,
                lambda e: show_error(self, "Erro", str(e)),
                cfg["id"],
                overrides,
            )

    def _trigger_stream(self, config_id, overrides):
        dlg = StreamDialog(config_id, overrides, self)
        if dlg.exec() == QDialog.Accepted:
            result = dlg.get_result()
            if result:
                full_text, model, duration = result
                dlg2 = AIResponseDialog(full_text, model=model, duration_secs=duration, parent=self)
                dlg2.exec()
        self.refresh()

    def _show_ai_response(self, r: dict):
        ai_text = r.get("ai_response", "")
        if not ai_text:
            show_success(self, "Executado", "Resposta recebida, mas nenhum texto de IA encontrado.")
            return
        model = r.get("model", "")
        duration = r.get("total_duration", 0)
        dlg = AIResponseDialog(ai_text, model=model, duration_secs=duration / 1_000_000_000.0, parent=self)
        dlg.exec()

    def _show_n8n_response(self, r: dict):
        resp = r.get("response")
        if not resp or not isinstance(resp, dict):
            show_success(self, "Executado", "Resposta recebida, mas sem dados estruturados.")
            return
        dlg = N8nResponseDialog(resp, parent=self)
        dlg.exec()

    def _delete(self, cfg: dict):
        name = cfg.get("template_name", "") or "Manual"
        confirm = show_confirm(self, "Confirmar", f'Excluir requisicao "{name}"?')
        if not confirm:
            return
        run_in_thread(
            integration_api.delete_integration,
            lambda r: (show_success(self, "OK", "Requisição excluida!"), self.refresh()),
            lambda e: show_error(self, "Erro", str(e)),
            cfg["id"],
        )
