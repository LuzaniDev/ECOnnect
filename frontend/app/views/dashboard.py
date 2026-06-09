from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QProgressBar, QGridLayout,
)
from frontend.app.api.dashboard_api import get_dashboard_summary
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error


CARD_BG = """
    QFrame#card {{
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
    }}
"""
ACCENT_BLUE = "#58a6ff"
ACCENT_GREEN = "#3fb950"
ACCENT_YELLOW = "#d29922"
ACCENT_RED = "#f85149"
ACCENT_PURPLE = "#bc8cff"


class _MetricCard(QFrame):
    def __init__(self, title: str, value: str, accent: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(CARD_BG)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        accent_bar = QFrame()
        accent_bar.setFixedHeight(4)
        accent_bar.setStyleSheet(f"background: {accent}; border-radius: 4px 4px 0 0;")
        layout.addWidget(accent_bar)

        inner = QVBoxLayout()
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600;")
        inner.addWidget(lbl_title)

        lbl_value = QLabel(str(value))
        lbl_value.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {accent};")
        inner.addWidget(lbl_value)

        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet("font-size: 11px; color: #484f58;")
            inner.addWidget(lbl_sub)

        layout.addLayout(inner)


class _StatusBar(QFrame):
    def __init__(self, label: str, count: int, total: int, color: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet("font-size: 12px; color: #c9d1d9; font-weight: 600;")
        layout.addWidget(lbl)

        bar = QProgressBar()
        bar.setFixedHeight(20)
        bar.setMinimum(0)
        bar.setMaximum(max(total, 1))
        bar.setValue(count)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0d1117; border: none; border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color}; border-radius: 4px;
            }}
        """)
        layout.addWidget(bar, 1)

        pct = (count / max(total, 1)) * 100
        lbl_count = QLabel(f"{count} ({pct:.0f}%)")
        lbl_count.setFixedWidth(100)
        lbl_count.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 700;")
        layout.addWidget(lbl_count)


class _ActivityEntry(QFrame):
    def __init__(self, username: str, action: str, entity: str, created_at: str):
        super().__init__()
        self.setStyleSheet("""
            QFrame { background: transparent; border-bottom: 1px solid #21262d; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet("font-size: 8px; color: #58a6ff;")
        layout.addWidget(dot)

        text = QLabel(f"<b>{username}</b> {action} {entity or ''}")
        text.setTextFormat(Qt.RichText)
        text.setStyleSheet("font-size: 12px; color: #c9d1d9;")
        layout.addWidget(text, 1)

        if created_at:
            try:
                dt = datetime.fromisoformat(str(created_at).replace("Z", ""))
                time_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                time_str = str(created_at)[:16]
        else:
            time_str = ""
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet("font-size: 11px; color: #484f58;")
        layout.addWidget(lbl_time)


class _ScheduleCard(QFrame):
    def __init__(self, name: str, next_run: str):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        icon = QLabel("🕐")
        icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(icon)

        lbl_name = QLabel(name or "Sem nome")
        lbl_name.setStyleSheet("font-size: 12px; color: #c9d1d9; font-weight: 600;")
        layout.addWidget(lbl_name, 1)

        if next_run:
            try:
                dt = datetime.fromisoformat(str(next_run).replace("Z", ""))
                time_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                time_str = str(next_run)[:16]
        else:
            time_str = ""
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet("font-size: 12px; color: #d29922; font-weight: 600;")
        layout.addWidget(lbl_time)


class _PanelSection(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(CARD_BG)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_bar = QFrame()
        header_bar.setFixedHeight(3)
        header_bar.setStyleSheet(f"background: {ACCENT_PURPLE}; border-radius: 6px 6px 0 0;")
        layout.addWidget(header_bar)

        header = QLabel(title)
        header.setStyleSheet(
            "font-size: 12px; color: #8b949e; font-weight: 700; "
            "padding: 12px 14px 8px 14px; letter-spacing: 0.3px;"
        )
        layout.addWidget(header)

        self._content = QVBoxLayout()
        self._content.setContentsMargins(8, 0, 8, 8)
        self._content.setSpacing(2)
        layout.addLayout(self._content)
        layout.addStretch()

    def add_widget(self, widget: QWidget):
        self._content.addWidget(widget)

    def clear_widgets(self):
        while self._content.count():
            item = self._content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class DashboardView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._data = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #0d1117; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: #0d1117;")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)

        # ── Header ────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #c9d1d9;")
        header.addWidget(title)

        header.addStretch()

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background: #21262d; border: 1px solid #30363d; "
            "border-radius: 6px; color: #c9d1d9; padding: 8px 16px; "
            "font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #30363d; }"
        )
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        self._layout.addLayout(header)

        # ── Summary Cards ──────────────────────────────
        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        self._layout.addLayout(self._cards_grid)

        # ── Status Bars ────────────────────────────────
        status_section = QFrame()
        status_section.setObjectName("card")
        status_section.setStyleSheet(CARD_BG)
        status_layout = QVBoxLayout(status_section)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(8)

        status_title = QLabel("REQUESTS POR STATUS")
        status_title.setStyleSheet(
            "font-size: 11px; color: #8b949e; font-weight: 700; "
            "letter-spacing: 0.5px;"
        )
        status_layout.addWidget(status_title)

        self._status_container = QVBoxLayout()
        self._status_container.setSpacing(6)
        status_layout.addLayout(self._status_container)

        self._layout.addWidget(status_section)

        # ── Bottom Panels ──────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self._activity_panel = _PanelSection("ATIVIDADE RECENTE")
        bottom_row.addWidget(self._activity_panel, 1)

        self._schedules_panel = _PanelSection("PROXIMAS EXECUCOES")
        bottom_row.addWidget(self._schedules_panel, 1)

        self._layout.addLayout(bottom_row)
        self._layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def refresh(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Carregando...")
        run_in_thread(
            get_dashboard_summary,
            self._on_data,
            lambda e: (
                show_error(self, "Erro", str(e)),
                self.btn_refresh.setEnabled(True),
                self.btn_refresh.setText("Atualizar"),
            ),
        )

    def _on_data(self, data: dict):
        self._data = data
        self._render_cards(data)
        self._render_status_bars(data)
        self._render_activity(data.get("recent_activity", []))
        self._render_schedules(data.get("upcoming_schedules", []))

        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Atualizar")

    def _render_cards(self, data: dict):
        self._clear_grid()

        req = data.get("requests", {})
        integ = data.get("integrations", {})

        cards = [
            _MetricCard("Total Requests", req.get("total", 0), ACCENT_BLUE),
            _MetricCard("Pendentes", req.get("pending", 0), ACCENT_YELLOW,
                        f"{req.get('pending_today', 0)} hoje"),
            _MetricCard("Enviados Hoje", req.get("sent_today", 0), ACCENT_GREEN,
                        f"{req.get('sent', 0)} total"),
            _MetricCard("Integracoes Ativas", integ.get("active", 0), ACCENT_PURPLE,
                        f"{integ.get('total', 0)} total"),
        ]
        for i, card in enumerate(cards):
            self._cards_grid.addWidget(card, 0, i)

    def _render_status_bars(self, data: dict):
        self._clear_layout(self._status_container)

        req = data.get("requests", {})
        total = req.get("total", 0) or 1
        pending = req.get("pending", 0)
        sent = req.get("sent", 0)
        cancelled = req.get("cancelled", 0)

        self._status_container.addWidget(
            _StatusBar("Pendentes", pending, total, ACCENT_YELLOW)
        )
        self._status_container.addWidget(
            _StatusBar("Enviados", sent, total, ACCENT_GREEN)
        )
        self._status_container.addWidget(
            _StatusBar("Cancelados", cancelled, total, ACCENT_RED)
        )

    def _render_activity(self, activities: list):
        self._activity_panel.clear_widgets()
        if not activities:
            noop = QLabel("Nenhuma atividade recente.")
            noop.setStyleSheet("font-size: 12px; color: #484f58; padding: 8px;")
            self._activity_panel.add_widget(noop)
            return
        for entry in activities:
            self._activity_panel.add_widget(
                _ActivityEntry(
                    entry.get("username", ""),
                    entry.get("action", ""),
                    entry.get("entity", ""),
                    entry.get("created_at", ""),
                )
            )

    def _render_schedules(self, schedules: list):
        self._schedules_panel.clear_widgets()
        if not schedules:
            noop = QLabel("Nenhuma execucao agendada.")
            noop.setStyleSheet("font-size: 12px; color: #484f58; padding: 8px;")
            self._schedules_panel.add_widget(noop)
            return
        for sched in schedules:
            self._schedules_panel.add_widget(
                _ScheduleCard(
                    sched.get("name", ""),
                    sched.get("next_run_at", ""),
                )
            )

    def _clear_grid(self):
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
