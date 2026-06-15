from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QMargins
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QCheckBox, QComboBox,
)
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QAreaSeries, QPieSeries,
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
    QHorizontalBarSeries, QStackedBarSeries,
)
from frontend.app.api.dashboard_api import get_dashboard_summary
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager


def _card_qss():
    t = theme_manager.current()
    return f"QFrame#card {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}"


def _chart_card_qss():
    t = theme_manager.current()
    return f"QFrame#chartCard {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}"


def _accent_colors():
    t = theme_manager.current()
    return [t.accent_blue, t.accent_green, t.accent_yellow, t.accent_red,
            t.accent_purple, t.accent_cyan, t.accent_pink, t.accent_sky, t.accent_coral, t.accent_emerald]





class _MetricCard(QFrame):
    def __init__(self, title: str, value: str, accent: str, subtitle: str = ""):
        super().__init__()
        t = theme_manager.current()
        self.setObjectName("card")
        self.setStyleSheet(_card_qss())
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: {accent}; border-radius: 4px 4px 0 0;")
        layout.addWidget(bar)

        inner = QVBoxLayout()
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600;")
        inner.addWidget(t_lbl)

        v = QLabel(str(value))
        v.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {accent};")
        inner.addWidget(v)

        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-size: 11px; color: {t.text_muted};")
            inner.addWidget(s)

        layout.addLayout(inner)


class _ChartCard(QFrame):
    def __init__(self, title: str, chart_view: QChartView, styles: list[str] | None = None):
        super().__init__()
        t = theme_manager.current()
        self.setObjectName("chartCard")
        self.setStyleSheet(_chart_card_qss())
        self.setMinimumHeight(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px;")
        header_row.addWidget(t_lbl)

        header_row.addStretch()

        self.style_combo = QComboBox()
        if styles:
            for s in styles:
                self.style_combo.addItem(s)
            self.style_combo.setStyleSheet(f"""
            QComboBox {{ background: {t.bg}; border: 1px solid {t.border};
            border-radius: 3px; padding: 2px 6px; color: {t.text};
            font-size: 10px; min-width: 80px; }}
            QComboBox::drop-down {{ border: none; width: 16px; }}
            QComboBox QAbstractItemView {{ background: {t.surface}; color: {t.text};
            border: 1px solid {t.border}; selection-background-color: {t.selection}; }}
            """)
        header_row.addWidget(self.style_combo)

        layout.addLayout(header_row)

        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(chart_view, 1)


class _ActivityEntry(QFrame):
    def __init__(self, username: str, action: str, entity: str, created_at: str):
        super().__init__()
        t = theme_manager.current()
        self.setStyleSheet(f"QFrame {{ background: transparent; border-bottom: 1px solid {t.border}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 8px; color: {t.accent_blue};")
        layout.addWidget(dot)

        text = QLabel(f"<b>{username}</b> {action} {entity or ''}")
        text.setTextFormat(Qt.RichText)
        text.setStyleSheet(f"font-size: 12px; color: {t.text};")
        layout.addWidget(text, 1)

        if created_at:
            try:
                dt = datetime.fromisoformat(str(created_at).replace("Z", ""))
                time_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                time_str = str(created_at)[:16]
        else:
            time_str = ""
        lbl = QLabel(time_str)
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_muted};")
        layout.addWidget(lbl)


class _RunEntry(QFrame):
    def __init__(self, name: str, last_run: str):
        super().__init__()
        t = theme_manager.current()
        self.setStyleSheet(f"QFrame {{ background: transparent; border-bottom: 1px solid {t.border}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon = QLabel("⚡")
        icon.setStyleSheet(f"font-size: 12px; color: {t.warning};")
        layout.addWidget(icon)

        n = QLabel(name or "Sem nome")
        n.setStyleSheet(f"font-size: 12px; color: {t.text}; font-weight: 600;")
        layout.addWidget(n, 1)

        if last_run:
            try:
                dt = datetime.fromisoformat(str(last_run).replace("Z", ""))
                time_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                time_str = str(last_run)[:16]
        else:
            time_str = ""
        lbl = QLabel(time_str)
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_muted};")
        layout.addWidget(lbl)


class _PanelSection(QFrame):
    def __init__(self, title: str):
        super().__init__()
        t = theme_manager.current()
        self.setObjectName("card")
        self.setStyleSheet(_card_qss())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hbar = QFrame()
        hbar.setFixedHeight(3)
        hbar.setStyleSheet(f"background: {t.accent_purple}; border-radius: 6px 6px 0 0;")
        layout.addWidget(hbar)

        h = QLabel(title)
        h.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; font-weight: 700; padding: 12px 14px 8px 14px;")
        layout.addWidget(h)

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
            w = item.widget()
            if w:
                w.deleteLater()


class DashboardView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._data = None
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self.refresh)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        t = theme_manager.current()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("Dashboard")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.text};")
        header.addWidget(title)

        header.addStretch()

        self.chk_auto = QCheckBox("Auto-atualizar")
        self.chk_auto.setStyleSheet(
            f"QCheckBox {{ color: {t.text_secondary}; font-size: 12px; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; }}"
        )
        self.chk_auto.stateChanged.connect(self._toggle_auto)
        header.addWidget(self.chk_auto)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            f"QPushButton {{ background: {t.surface}; border: 1px solid {t.border}; "
            f"border-radius: 6px; color: {t.text}; padding: 8px 16px; "
            f"font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {t.border}; }}"
        )
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        self._layout.addLayout(header)

        # ── Summary Cards ──────────────────────────────
        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        self._layout.addLayout(self._cards_grid)

        # ── Charts Row 1 (Line/Area + Pie/Bar) ─────────
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._time_chart_view = QChartView()
        self._time_card = _ChartCard(
            "REQUESTS NOS ULTIMOS 14 DIAS", self._time_chart_view,
            styles=["Linha", "Area", "Barras"],
        )
        self._time_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_time_chart(self._data) if self._data else None
        )
        row1.addWidget(self._time_card, 3)

        self._status_chart_view = QChartView()
        self._status_card = _ChartCard(
            "DISTRIBUICAO POR STATUS", self._status_chart_view,
            styles=["Donut", "Pizza", "Barras"],
        )
        self._status_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_status_chart(self._data) if self._data else None
        )
        row1.addWidget(self._status_card, 2)
        self._layout.addLayout(row1)

        # ── Charts Row 2 (Template Bar + Weekly Comparison) ──
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self._template_chart_view = QChartView()
        self._template_card = _ChartCard(
            "TEMPLATES MAIS USADOS", self._template_chart_view,
            styles=["Barras Horizontais", "Barras Verticais", "Pizza"],
        )
        self._template_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_template_chart(self._data) if self._data else None
        )
        row2.addWidget(self._template_card, 1)

        self._weekly_chart_view = QChartView()
        self._weekly_card = _ChartCard(
            "COMPARATIVO SEMANAL", self._weekly_chart_view,
            styles=["Barras Agrupadas", "Barras Empilhadas"],
        )
        self._weekly_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_weekly_chart(self._data) if self._data else None
        )
        row2.addWidget(self._weekly_card, 1)
        self._layout.addLayout(row2)

        # ── Charts Row 3 (User bar + Integration pie) ──
        row3 = QHBoxLayout()
        row3.setSpacing(12)
        self._user_chart_view = QChartView()
        self._user_card = _ChartCard(
            "REQUESTS POR USUARIO (TOP 5)", self._user_chart_view,
            styles=["Barras", "Pizza"],
        )
        self._user_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_user_chart(self._data) if self._data else None
        )
        row3.addWidget(self._user_card, 1)

        self._integ_chart_view = QChartView()
        self._integ_card = _ChartCard(
            "INTEGRACOES POR TIPO", self._integ_chart_view,
            styles=["Pizza", "Donut", "Barras"],
        )
        self._integ_card.style_combo.currentIndexChanged.connect(
            lambda i: self._render_integ_chart(self._data) if self._data else None
        )
        row3.addWidget(self._integ_card, 1)
        self._layout.addLayout(row3)

        # ── Bottom Panels ──────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self._activity_panel = _PanelSection("ATIVIDADE RECENTE")
        bottom_row.addWidget(self._activity_panel, 1)

        self._runs_panel = _PanelSection("EXECUCOES RECENTES")
        bottom_row.addWidget(self._runs_panel, 1)

        self._layout.addLayout(bottom_row)
        self._layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _toggle_auto(self, state):
        if state:
            self._auto_timer.start(120000)
        else:
            self._auto_timer.stop()

    # ── Refresh ────────────────────────────────────────

    def refresh(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Carregando...")
        run_in_thread(
            get_dashboard_summary,
            self._on_data,
            self._on_error,
        )

    def _on_error(self, e):
        show_error(self, "Erro", str(e))
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Atualizar")

    def _on_data(self, data: dict):
        self._data = data
        try:
            self._render_cards(data)
            logger.info("DASHBOARD", "Cards OK")
            self._render_time_chart(data)
            logger.info("DASHBOARD", "Time chart OK")
            self._render_status_chart(data)
            logger.info("DASHBOARD", "Status chart OK")
            self._render_template_chart(data)
            logger.info("DASHBOARD", "Template chart OK")
            self._render_weekly_chart(data)
            logger.info("DASHBOARD", "Weekly chart OK")
            self._render_user_chart(data)
            logger.info("DASHBOARD", "User chart OK")
            self._render_integ_chart(data)
            logger.info("DASHBOARD", "Integ chart OK")
            self._render_activity(data.get("recent_activity", []))
            self._render_runs(data.get("recent_runs", []))
        except Exception as e:
            logger.error("DASHBOARD", f"Erro ao renderizar: {e}")
            import traceback
            logger.error("DASHBOARD", traceback.format_exc())
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Atualizar")

    # ── Cards ──────────────────────────────────────────

    def _render_cards(self, data: dict):
        t = theme_manager.current()
        self._clear_grid()
        req = data.get("requests", {})
        integ = data.get("integrations", {})

        cards = [
            _MetricCard("Total Requests", req.get("total", 0), t.accent_blue),
            _MetricCard("Pendentes", req.get("pending", 0), t.accent_yellow,
                f"{req.get('pending_today', 0)} hoje"),
            _MetricCard("Enviados Hoje", req.get("sent_today", 0), t.accent_green,
                f"{req.get('sent', 0)} total"),
            _MetricCard("Integracoes Ativas", integ.get("active", 0), t.accent_purple,
                f"{integ.get('total', 0)} total"),
        ]
        for i, card in enumerate(cards):
            self._cards_grid.addWidget(card, 0, i)

    # ── Time Chart (Line) ──────────────────────────────

    def _render_time_chart(self, data: dict):
        t = theme_manager.current()
        points = data.get("requests_over_time", [])
        if not points:
            points = [{"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}]

        style = self._time_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.setBackgroundBrush(QColor(t.surface))
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        max_val = max((p.get("count", 0) for p in points), default=1)
        n = len(points)

        if style == 0:
            s = QLineSeries()
            s.setColor(QColor(t.accent_blue))
            s.setPen(QPen(QColor(t.accent_blue), 2))
            for i, p in enumerate(points):
                s.append(float(i), float(p.get("count", 0)))
            chart.addSeries(s)
            ax_x = QValueAxis()
            ax_x.setRange(-0.3, max(n - 0.7, 0.3))
            ax_x.setLabelsVisible(False); ax_x.setLineVisible(False); ax_x.setGridLineVisible(False)
            chart.addAxis(ax_x, Qt.AlignBottom); s.attachAxis(ax_x)
        elif style == 1:
            line = QLineSeries()
            line.setPen(QPen(QColor(t.accent_blue), 2))
            for i, p in enumerate(points):
                line.append(float(i), float(p.get("count", 0)))
            zero = QLineSeries()
            for i in range(n):
                zero.append(float(i), 0.0)
            area = QAreaSeries(line, zero)
            c = QColor(t.accent_blue); c.setAlpha(60)
            area.setColor(c)
            area.setBorderColor(QColor(t.accent_blue))
            chart.addSeries(area)
            ax_x = QValueAxis()
            ax_x.setRange(-0.3, max(n - 0.7, 0.3))
            ax_x.setLabelsVisible(False); ax_x.setLineVisible(False); ax_x.setGridLineVisible(False)
            chart.addAxis(ax_x, Qt.AlignBottom); area.attachAxis(ax_x)
        else:
            bs = QBarSet("")
            bs.setColor(QColor(t.accent_blue))
            for p in points:
                bs.append(p.get("count", 0))
            bs_series = QBarSeries()
            bs_series.append(bs)
            bs_series.setBarWidth(0.6)
            chart.addSeries(bs_series)
            cats = [p.get("date", "")[-5:] for p in points]
            ax_cat = QBarCategoryAxis()
            ax_cat.append(cats)
            ax_cat.setLabelsColor(QColor(t.text_secondary))
            ax_cat.setGridLineColor(QColor(t.border))
            ax_cat.setLineVisible(False)
            chart.addAxis(ax_cat, Qt.AlignBottom); bs_series.attachAxis(ax_cat)

        ax_y = QValueAxis()
        ax_y.setLabelsColor(QColor(t.text_secondary))
        ax_y.setGridLineColor(QColor(t.border))
        ax_y.setLineVisible(False)
        ax_y.setRange(0, max_val * 1.2 or 5)
        ax_y.setLabelFormat("%d")
        chart.addAxis(ax_y, Qt.AlignLeft)
        for s in chart.series():
            s.attachAxis(ax_y)

        self._time_chart_view.setChart(chart)
        self._time_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── Status Pie ─────────────────────────────────────

    def _render_status_chart(self, data: dict):
        t = theme_manager.current()
        req = data.get("requests", {})
        style = self._status_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.setBackgroundBrush(QColor(t.surface))
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        entries = [
            ("Pendentes", req.get("pending", 0), t.accent_yellow),
            ("Enviados", req.get("sent", 0), t.accent_green),
            ("Cancelados", req.get("cancelled", 0), t.accent_red),
        ]

        if style <= 1:
            ps = QPieSeries()
            if style == 0:
                ps.setHoleSize(0.4)
            has_data = False
            for label, val, color in entries:
                if val > 0:
                    sl = ps.append(f"{label} ({val})", val)
                    sl.setColor(QColor(color))
                    sl.setLabelVisible(True)
                    sl.setLabelColor(QColor(t.text))
                    has_data = True
            if not has_data:
                ps.append("Sem dados", 1)
                ps.slices()[0].setColor(QColor(t.border))
            chart.addSeries(ps)
        else:
            bs = QBarSet("")
            for _, val, _ in entries:
                bs.append(val)
            total = sum(v for _, v, _ in entries) or 1
            bs.setColor(QColor(t.accent_blue))
            s = QBarSeries()
            s.append(bs)
            chart.addSeries(s)
            cat = QBarCategoryAxis()
            cat.append([e[0] for e in entries])
            cat.setLabelsColor(QColor(t.text_secondary))
            cat.setGridLineColor(QColor(t.border))
            cat.setLineVisible(False)
            chart.addAxis(cat, Qt.AlignBottom); s.attachAxis(cat)
            vy = QValueAxis()
            vy.setLabelsColor(QColor(t.text_secondary))
            vy.setGridLineColor(QColor(t.border))
            vy.setLineVisible(False)
            vy.setRange(0, total)
            vy.setLabelFormat("%d")
            chart.addAxis(vy, Qt.AlignLeft); s.attachAxis(vy)

        self._status_chart_view.setChart(chart)
        self._status_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── Template Bar ───────────────────────────────────

    def _render_template_chart(self, data: dict):
        t = theme_manager.current()
        items = data.get("requests_by_template", [])
        if not items:
            items = [{"name": "Nenhum dado", "count": 0}]
        names = [it.get("name", "?")[:20] for it in items[:8]]

        style = self._template_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.setBackgroundBrush(QColor(t.surface))
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        if style == 2:
            ps = QPieSeries()
            for it in items[:8]:
                c = it.get("count", 0)
                if c > 0:
                    sl = ps.append(f"{it.get('name', '?')[:15]} ({c})", c)
                    sl.setLabelVisible(True)
                    sl.setLabelColor(QColor(t.text))
            if not ps.count():
                ps.append("Sem dados", 1)
                ps.slices()[0].setColor(QColor(t.border))
            chart.addSeries(ps)
        else:
            bs = QBarSet("")
            bs.setColor(QColor(t.accent_blue))
            for it in items[:8]:
                bs.append(it.get("count", 0))
            if style == 0:
                s = QHorizontalBarSeries()
            else:
                s = QBarSeries()
            s.append(bs)
            s.setBarWidth(0.6)
            chart.addSeries(s)
            cat = QBarCategoryAxis()
            cat.append(names)
            cat.setLabelsColor(QColor(t.text_secondary))
            cat.setGridLineColor(QColor(t.border))
            cat.setLineVisible(False)
            if style == 0:
                chart.addAxis(cat, Qt.AlignLeft); s.attachAxis(cat)
                vx = QValueAxis()
                vx.setLabelsColor(QColor(t.text_secondary))
                vx.setGridLineColor(QColor(t.border))
                vx.setLineVisible(False)
                vx.setLabelFormat("%d")
                chart.addAxis(vx, Qt.AlignBottom); s.attachAxis(vx)
            else:
                chart.addAxis(cat, Qt.AlignBottom); s.attachAxis(cat)
                vy = QValueAxis()
                vy.setLabelsColor(QColor(t.text_secondary))
                vy.setGridLineColor(QColor(t.border))
                vy.setLineVisible(False)
                vy.setLabelFormat("%d")
                chart.addAxis(vy, Qt.AlignLeft); s.attachAxis(vy)

        self._template_chart_view.setChart(chart)
        self._template_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── Weekly Comparison ──────────────────────────────

    def _render_weekly_chart(self, data: dict):
        t = theme_manager.current()
        items = data.get("weekly_comparison", [])
        if not items:
            return

        style = self._weekly_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor(t.text_secondary))
        chart.legend().setFont(QFont("Segoe UI", 10))
        chart.setBackgroundBrush(QColor(t.surface))
        chart.setMargins(QMargins(0, 0, 0, 0))

        weeks = [it.get("week", "") for it in items]
        cat_axis = QBarCategoryAxis()
        cat_axis.append(weeks)
        cat_axis.setLabelsColor(QColor(t.text_secondary))
        cat_axis.setGridLineColor(QColor(t.border))
        cat_axis.setLineVisible(False)
        chart.addAxis(cat_axis, Qt.AlignBottom)

        statuses = [
            ("sent", "Enviados", t.accent_green),
            ("pending", "Pendentes", t.accent_yellow),
            ("cancelled", "Cancelados", t.accent_red),
        ]

        if style == 0:
            SeriesClass = QBarSeries
        else:
            SeriesClass = QStackedBarSeries

        for status, label, color in statuses:
            bs = QBarSet(label)
            bs.setColor(QColor(color))
            for it in items:
                bs.append(it.get(status, 0))
            series = SeriesClass()
            series.append(bs)
            chart.addSeries(series)
            series.attachAxis(cat_axis)

        vy = QValueAxis()
        vy.setLabelsColor(QColor(t.text_secondary))
        vy.setGridLineColor(QColor(t.border))
        vy.setLineVisible(False)
        vy.setLabelFormat("%d")
        chart.addAxis(vy, Qt.AlignLeft)
        for s in chart.series():
            s.attachAxis(vy)

        self._weekly_chart_view.setChart(chart)
        self._weekly_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── User Chart ─────────────────────────────────────

    def _render_user_chart(self, data: dict):
        t = theme_manager.current()
        items = data.get("requests_by_user", [])

        style = self._user_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.setBackgroundBrush(QColor(t.surface))
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        names = [it.get("username", "?") for it in items]

        if style == 1:
            ps = QPieSeries()
            for it in items:
                c = it.get("count", 0)
                if c > 0:
                    sl = ps.append(f"{it.get('username', '?')} ({c})", c)
                    sl.setLabelVisible(True)
                    sl.setLabelColor(QColor(t.text))
            if not ps.count():
                ps.append("Sem dados", 1)
                ps.slices()[0].setColor(QColor(t.border))
            chart.addSeries(ps)
        else:
            bs = QBarSet("")
            bs.setColor(QColor(t.accent_purple))
            if items:
                for it in items:
                    bs.append(it.get("count", 0))
                s = QBarSeries()
                s.append(bs)
                s.setBarWidth(0.5)
                chart.addSeries(s)
                cat = QBarCategoryAxis()
                cat.append(names)
                cat.setLabelsColor(QColor(t.text_secondary))
                cat.setGridLineColor(QColor(t.border))
                cat.setLineVisible(False)
                chart.addAxis(cat, Qt.AlignBottom); s.attachAxis(cat)
                vy = QValueAxis()
                vy.setLabelsColor(QColor(t.text_secondary))
                vy.setGridLineColor(QColor(t.border))
                vy.setLineVisible(False)
                vy.setLabelFormat("%d")
                chart.addAxis(vy, Qt.AlignLeft); s.attachAxis(vy)

        self._user_chart_view.setChart(chart)
        self._user_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── Integration Type Pie ───────────────────────────

    def _render_integ_chart(self, data: dict):
        t = theme_manager.current()
        items = data.get("integration_types", [])
        if not items:
            return

        style = self._integ_card.style_combo.currentIndex()
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark)
        chart.setBackgroundBrush(QColor(t.surface))
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))

        palette = [t.accent_blue, t.accent_green, t.accent_yellow, t.accent_red, t.accent_purple, t.accent_cyan]

        if style <= 1:
            ps = QPieSeries()
            if style == 1:
                ps.setHoleSize(0.4)
            for i, it in enumerate(items):
                sl = ps.append(f"{it.get('type', '?')} ({it.get('count', 0)})", it.get("count", 0))
                sl.setColor(QColor(palette[i % len(palette)]))
                sl.setLabelVisible(True)
                sl.setLabelColor(QColor(t.text))
            chart.addSeries(ps)
        else:
            bs = QBarSet("")
            names = []
            for it in items:
                bs.append(it.get("count", 0))
                names.append(it.get("type", "?"))
            bs.setColor(QColor(t.accent_cyan))
            s = QBarSeries()
            s.append(bs)
            chart.addSeries(s)
            cat = QBarCategoryAxis()
            cat.append(names)
            cat.setLabelsColor(QColor(t.text_secondary))
            cat.setGridLineColor(QColor(t.border))
            cat.setLineVisible(False)
            chart.addAxis(cat, Qt.AlignBottom); s.attachAxis(cat)
            vy = QValueAxis()
            vy.setLabelsColor(QColor(t.text_secondary))
            vy.setGridLineColor(QColor(t.border))
            vy.setLineVisible(False)
            vy.setLabelFormat("%d")
            chart.addAxis(vy, Qt.AlignLeft); s.attachAxis(vy)

        self._integ_chart_view.setChart(chart)
        self._integ_chart_view.setRenderHint(QPainter.Antialiasing)

    # ── Activity & Runs ────────────────────────────────

    def _render_activity(self, activities: list):
        self._activity_panel.clear_widgets()
        if not activities:
            noop = QLabel("Nenhuma atividade recente.")
            noop.setStyleSheet(f"font-size: 12px; color: {t.text_muted}; padding: 8px;")
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

    def _render_runs(self, runs: list):
        self._runs_panel.clear_widgets()
        if not runs:
            noop = QLabel("Nenhuma execucao recente.")
            noop.setStyleSheet(f"font-size: 12px; color: {t.text_muted}; padding: 8px;")
            self._runs_panel.add_widget(noop)
            return
        for entry in runs:
            self._runs_panel.add_widget(
                _RunEntry(
                    entry.get("name", ""),
                    entry.get("last_run_at", ""),
                )
            )

    def _clear_grid(self):
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
