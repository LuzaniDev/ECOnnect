from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QFrame,
    QCheckBox,
    QTabWidget,
)
from frontend.app.core.logger import logger
from frontend.app.widgets.worker import run_in_thread
from frontend.app.api import audit_api


LOG_VIEWER_STYLE = """
QDialog#logViewer {
    background-color: #070b14;
}
QFrame#logToolbar {
    background-color: #0a1220;
    border-bottom: 1px solid #1e2d4a;
    padding: 8px 16px;
}
QLabel#logTitle {
    font-size: 14px;
    font-weight: 700;
    color: #f1f5f9;
}
QLabel#logCount {
    font-size: 11px;
    color: #64748b;
}
QPushButton#logBtn {
    background-color: #141d32;
    color: #94a3b8;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#logBtn:hover {
    background-color: #1e2d4a;
    color: #f1f5f9;
}
QPushButton#logBtnDanger {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#logBtnDanger:hover {
    background-color: rgba(239, 68, 68, 0.3);
}
QComboBox#logFilter {
    background-color: #141d32;
    color: #94a3b8;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    min-width: 100px;
}
"""


class LogViewerWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logViewer")
        self.setWindowTitle("ECOnnect — Logs")
        self.setMinimumSize(900, 500)
        self.resize(1100, 600)
        self.setStyleSheet(LOG_VIEWER_STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._paused = False
        self._filter_level = "Todos"
        self._last_count = 0
        self._timer = None
        self._audit_logs = []
        self._audit_last_fetch = 0

        self._setup_ui()
        self._load_history()
        self._start_listener()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { background: #070b14; border: none; }
            QTabBar::tab {
                background: transparent; color: #8b949e; border: none;
                padding: 8px 20px; font-size: 12px; font-weight: 500;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
            QTabBar::tab:hover { color: #c9d1d9; }
        """)

        self._build_system_tab()
        self._build_audit_tab()
        layout.addWidget(self.tabs)

    def _build_system_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("logToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Logs do Sistema")
        title.setObjectName("logTitle")
        toolbar_layout.addWidget(title)

        self.count_label = QLabel("0 entradas")
        self.count_label.setObjectName("logCount")
        toolbar_layout.addWidget(self.count_label)

        toolbar_layout.addStretch()

        filter_label = QLabel("Filtrar:")
        filter_label.setStyleSheet("color: #64748b; font-size: 12px;")
        toolbar_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("logFilter")
        self.filter_combo.addItems(["Todos", "INFO", "WARN", "ERROR"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_change)
        toolbar_layout.addWidget(self.filter_combo)

        self.pause_btn = QPushButton("Pausar")
        self.pause_btn.setObjectName("logBtn")
        self.pause_btn.clicked.connect(self._toggle_pause)
        toolbar_layout.addWidget(self.pause_btn)

        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.setStyleSheet(
            "color: #94a3b8; font-size: 12px; spacing: 6px;"
        )
        toolbar_layout.addWidget(self.auto_scroll_check)

        clear_btn = QPushButton("Limpar")
        clear_btn.setObjectName("logBtnDanger")
        clear_btn.clicked.connect(self._clear_logs)
        toolbar_layout.addWidget(clear_btn)

        tab_layout.addWidget(toolbar)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        self.output.setStyleSheet(
            "QTextEdit {"
            "  background-color: #070b14;"
            "  color: #f1f5f9;"
            "  border: none;"
            "  padding: 12px 16px;"
            "  selection-background-color: #014998;"
            "}"
        )
        self.output.setLineWrapMode(QTextEdit.NoWrap)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_layout.addWidget(self.output)

        self.tabs.addTab(tab, "Sistema")

    def _build_audit_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("logToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Auditoria")
        title.setObjectName("logTitle")
        toolbar_layout.addWidget(title)

        self.audit_count = QLabel("0 registros")
        self.audit_count.setObjectName("logCount")
        toolbar_layout.addWidget(self.audit_count)

        toolbar_layout.addStretch()

        refresh_btn = QPushButton("Atualizar")
        refresh_btn.setObjectName("logBtn")
        refresh_btn.clicked.connect(self._fetch_audit_logs)
        toolbar_layout.addWidget(refresh_btn)

        tab_layout.addWidget(toolbar)

        self.audit_output = QTextEdit()
        self.audit_output.setReadOnly(True)
        self.audit_output.setFont(QFont("Consolas", 10))
        self.audit_output.setStyleSheet(
            "QTextEdit {"
            "  background-color: #070b14;"
            "  color: #f1f5f9;"
            "  border: none;"
            "  padding: 12px 16px;"
            "  selection-background-color: #014998;"
            "}"
        )
        self.audit_output.setLineWrapMode(QTextEdit.NoWrap)
        self.audit_output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_layout.addWidget(self.audit_output)

        self.tabs.addTab(tab, "Auditoria")

    def _load_history(self):
        for entry in logger.get_buffer():
            self._append_entry(entry)
        self._fetch_audit_logs()

    def _fetch_audit_logs(self):
        def on_logs(logs):
            self._audit_logs = logs
            self._render_audit()

        def on_error(err):
            self.audit_output.setPlainText(f"Erro ao carregar auditoria: {err}")

        run_in_thread(audit_api.list_logs, on_logs, on_error)

    def _render_audit(self):
        self.audit_output.clear()
        if not self._audit_logs:
            self.audit_output.setPlainText("Nenhum registro de auditoria encontrado.")
            self.audit_count.setText("0 registros")
            return

        lines = []
        for log in self._audit_logs:
            ts = log.get("created_at", "")[:19] if log.get("created_at") else ""
            user = log.get("username", "-")
            action = log.get("action", "-")
            entity = log.get("entity_type", "")
            eid = log.get("entity_id", "")[:12] if log.get("entity_id") else ""
            ip = log.get("ip_address", "")
            line = f"{ts}  [{user}]  {action}  {entity} {eid}  {ip}"
            lines.append(line)

        self.audit_output.setPlainText("\n".join(lines))
        self.audit_count.setText(f"{len(lines)} registros")

    def _start_listener(self):
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll_logs)
        self._timer.start()

    def _poll_logs(self):
        if self._paused:
            return
        current_count = len(logger.get_buffer())
        if current_count > self._last_count:
            new_entries = list(logger.get_buffer())[self._last_count:]
            for entry in new_entries:
                if self._matches_filter(entry):
                    self._append_entry(entry)
            self._last_count = current_count

    def _append_entry(self, entry: str):
        color = self._color_for_level(entry)
        html = f'<div style="color:{color}; font-family:Consolas; font-size:10pt; white-space:pre;">{self._escape(entry)}</div>'
        self.output.append("")
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)

        if self.auto_scroll_check.isChecked():
            scrollbar = self.output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        count = self.output.document().blockCount()
        self.count_label.setText(f"{count} entradas")

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _color_for_level(self, entry: str) -> str:
        if "[ERROR]" in entry:
            return "#ef4444"
        elif "[WARN" in entry:
            return "#f8891d"
        elif "[INFO" in entry:
            return "#22c55e"
        return "#94a3b8"

    def _matches_filter(self, entry: str) -> bool:
        if self._filter_level == "Todos":
            return True
        tag = f"[{self._filter_level}"
        return tag in entry

    def _on_filter_change(self, text: str):
        self._filter_level = text
        self._last_count = 0
        self.output.clear()
        for entry in logger.get_buffer():
            if self._matches_filter(entry):
                self._append_entry(entry)
        self._last_count = len(logger.get_buffer())

    def _toggle_pause(self):
        self._paused = not self._paused
        self.pause_btn.setText("Retomar" if self._paused else "Pausar")
        self.pause_btn.setStyleSheet(
            "QPushButton#logBtn { color: #f8891d; border-color: #f8891d; }"
            if self._paused
            else "QPushButton#logBtn { color: #94a3b8; border-color: #1e2d4a; }"
        )

    def _clear_logs(self):
        self.output.clear()
        self.count_label.setText("0 entradas")
        logger.clear_buffer()
        self._last_count = 0
