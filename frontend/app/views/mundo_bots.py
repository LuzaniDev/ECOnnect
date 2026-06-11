import json
import os
import httpx
import uuid
import time
import concurrent.futures
from datetime import datetime, date, timedelta
from PySide6.QtCore import Qt, QDate, QTimer, QDateTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QTextEdit, QLineEdit, QTabWidget,
    QDialog, QDateTimeEdit, QDialogButtonBox, QRadioButton,
    QAbstractItemView,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb


COBRANCA_SQL = """
WITH
TReceber AS (
      SELECT Par.Empresa,
             Emp.NomeFantasia,
             Clg.Codigo                                          AS Cliente,
             Clg.Nome,
             Clg.CpfCnpj,
             COALESCE(Clg.Fone, Clg.FoneCelular)                 AS Fone,
             Clg.Endereco,
             Clg.NumeroEndereco,
             Clg.Bairro,
             Clg.Regiao,
             Clg.Cidade,
             COALESCE(Cli.DiasCarenciaJuros, 0)                  AS DiasCarenciaJuros,
             Doc.IdDocumento,
             Par.Documento||'/'||Par.Parcela                     AS Documento,
             Tpd.Abreviatura,
             CURRENT_DATE -
         IIF(Par.Vencimento < Par.UltimoRecebimento,
             Par.UltimoRecebimento, Par.Vencimento)               AS Atrazo,
             Doc.Emissao,
             Par.Vencimento,
             Par.Valor,
             (Par.Valor - Par.ValorPendente)                     AS CapitalRecebido,
             Par.ValorPendente,
             Pmt.Multa,
             COALESCE(NULLIF(Cli.JurosAtraso, 0), Pmt.Juros)     AS Juros,
             Pmt.TipoJuro
        FROM TRecDocumento          Doc
       INNER JOIN TRecParcela       Par
          ON Par.Empresa   = Doc.Empresa
         AND Par.Cliente   = Doc.Cliente
         AND Par.Tipo      = Doc.Tipo
         AND Par.Documento = Doc.Documento
       INNER JOIN TRecTipoDocumento Tpd
          ON Tpd.Codigo    = Par.Tipo
         AND COALESCE(Tpd.Cartao, 'N') = 'N'
       INNER JOIN TRecCliente       Cli
          ON Cli.Empresa   = Par.Empresa
         AND Cli.Codigo    = Par.Cliente
       INNER JOIN TRecClienteGeral  Clg
          ON Clg.Codigo    = Cli.Codigo
       INNER JOIN TGerEmpresa       Emp
          ON Emp.Codigo    = Par.Empresa
        LEFT JOIN TRecParametro     Pmt
          ON Pmt.Empresa   = Emp.Codigo
       WHERE Par.Empresa          = ?
         AND Par.Vencimento BETWEEN ? AND ?
         AND Par.ValorPendente    > 0
         AND Par.IdRenegociacao  IS NULL
         AND Par.Situacao        <> 'A'
         {tipo_filter}
)

SELECT Rec.*,
   IIF(Rec.Atrazo > Rec.DiasCarenciaJuros,
  CASE Rec.TipoJuro
  WHEN 'S' THEN Rec.ValorPendente * (Rec.Juros / 100) * Rec.Atrazo
  WHEN 'C' THEN Rec.ValorPendente * (POWER(1 + (Rec.Juros / 100), Rec.Atrazo) - 1)
   END, 0)                                   AS ValorJuros,
       Rec.ValorPendente * (Rec.Multa / 100) AS ValorMulta
  FROM TReceber Rec
"""

VARS_INFO = [
    ("phone / celular",     "{phone}",      5,  "Fone (COALESCE)",   "Telefone do cliente (Fone ou Celular)"),
    ("nome / nome_cliente", "{nome}",        3,  "Nome",              "Nome do cliente"),
    ("cliente / codigo",    "{cliente}",     2,  "Cliente (Codigo)",  "Código do cliente"),
    ("cpf_cnpj",            "{cpf_cnpj}",    4,  "CpfCnpj",           "CPF/CNPJ do cliente"),
    ("empresa",             "{empresa}",     0,  "Empresa",           "Código da empresa"),
    ("nome_fantasia",       "{nome_fantasia}", 1, "NomeFantasia",     "Nome fantasia da empresa"),
    ("valor_cobranca",      "{valor_cobranca}", 20, "ValorPendente",  "Valor pendente (R$)"),
    ("valor_total",         "{valor_total}", 18, "Valor",             "Valor original do documento (R$)"),
    ("capital_recebido",    "{capital_recebido}", 19, "CapitalRecebido","Capital já recebido (R$)"),
    ("valor_juros",         "{valor_juros}", 24, "ValorJuros (calc)","Juros calculado sobre atraso (R$)"),
    ("valor_multa",         "{valor_multa}", 25, "ValorMulta (calc)","Multa calculada sobre pendente (R$)"),
    ("juros_taxa",          "{juros_taxa}",  22, "Juros (taxa %)",   "Taxa de juros (%)"),
    ("vencimento",          "{vencimento}",  17, "Vencimento",        "Data de vencimento"),
    ("emissao",             "{emissao}",     16, "Emissao",           "Data de emissão do documento"),
    ("atraso",              "{atraso}",      15, "Atrazo (calc)",     "Dias em atraso"),
    ("dias_carencia",       "{dias_carencia}", 11, "DiasCarenciaJuros","Dias de carência para juros"),
    ("documento",           "{documento}",   13, "Documento",         "Nº doc / parcela (ex: 123/01)"),
    ("id_documento",        "{id_documento}", 12, "IdDocumento",      "ID interno do documento"),
    ("abreviatura",         "{abreviatura}", 14, "Abreviatura",       "Tipo do documento (DUP/CHQ/etc)"),
    ("tipo_juro",           "{tipo_juro}",   23, "TipoJuro",          "Tipo de juros (S=simples, C=composto)"),
    ("multa_taxa",          "{multa_taxa}",  21, "Multa (%)",         "Taxa de multa (%)"),
    ("endereco",            "{endereco}",     6,  "Endereco",          "Endereço do cliente"),
    ("numero",              "{numero}",       7,  "NumeroEndereco",    "Número do endereço"),
    ("bairro",              "{bairro}",       8,  "Bairro",            "Bairro do cliente"),
    ("cidade",              "{cidade}",      10,  "Cidade",            "Cidade do cliente"),
    ("regiao",              "{regiao}",       9,  "Regiao",            "Região do cliente"),
]

PLACEHOLDER_MAP = {}
for label, _, col, _, _ in VARS_INFO:
    for alias in label.split(" / "):
        PLACEHOLDER_MAP[alias.strip()] = col
PLACEHOLDER_MAP["celular"] = 5
PLACEHOLDER_MAP["nome_cliente"] = 3
PLACEHOLDER_MAP["first_name"] = 3
PLACEHOLDER_MAP["codigo_cliente"] = 2
PLACEHOLDER_MAP["data_vencimento"] = 17
PLACEHOLDER_MAP["dias_atraso"] = 15

DEFAULT_BODY_TEMPLATE = """{
  "phone": "{phone}",
  "first_name": "{nome_cliente}",
  "actions": [
    {
      "action": "set_field_value",
      "field_name": "nome_cliente",
      "value": "{nome_cliente}"
    },
    {
      "action": "set_field_value",
      "field_name": "valor_cobranca",
      "value": "{valor_cobranca}"
    },
    {
      "action": "set_field_value",
      "field_name": "data_vencimento",
      "value": "{data_vencimento}"
    },
    {
      "action": "set_field_value",
      "field_name": "numero_boleto",
      "value": "{numero_boleto}"
    },
    {
      "action": "set_field_value",
      "field_name": "status_cobranca",
      "value": "{status_cobranca}"
    },
    {
      "action": "send_flow",
      "flow_id": 0
    }
  ]
}"""

DEFAULT_HEADERS = [
    ("accept", "application/json"),
    ("X-ACCESS-TOKEN", ""),
    ("Content-Type", "application/json"),
]

DATA_DIR = os.path.join(os.path.expanduser("~"), ".econnect")
TEMPLATES_FILE = os.path.join(DATA_DIR, "mundo_bots_templates.json")
JOBS_FILE = os.path.join(DATA_DIR, "mundo_bots_jobs.json")
TAG_COOLDOWN_FILE = os.path.join(DATA_DIR, "tag_cooldown_config.json")
SENT_HISTORY_FILE = os.path.join(DATA_DIR, "sent_history.json")
os.makedirs(DATA_DIR, exist_ok=True)

TAB_STYLE = """
QTabWidget::pane {
    background: transparent; border: none;
}
QTabBar::tab {
    background: transparent; color: #8b949e;
    padding: 8px 20px; font-size: 13px; font-weight: 600;
    border: none; border-bottom: 2px solid transparent;
    margin: 0 2px;
}
QTabBar::tab:selected {
    color: #f1f5f9; border-bottom: 2px solid #1f6feb;
}
QTabBar::tab:hover {
    color: #c9d1d9;
}
"""


class MundoBotsView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user

        self._results_data = []
        self._hidden_clients_data = []
        self._selected_rows = set()
        self._sent_check_cache = {}
        self._configured_set = set()
        self._page = 0
        self._page_size = 200
        self._has_more = False
        self._all_count = 0

        self._load_configured_set()
        self._setup_ui()
        self._start_timer()

    def _load_configured_set(self):
        self._configured_set.clear()
        jobs = self._load_jobs()
        for j in jobs:
            if j["status"] in ("pending",):
                for c in j.get("clients", []):
                    if len(c) > 15:
                        key = (str(c[0]), str(c[2]))
                    else:
                        key = (str(c[0]), str(c[1]))
                    self._configured_set.add(key)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_cobranca_tab(), "Cobrança em Lote")
        self.tabs.addTab(self._build_clientes_tab(), "Clientes Configurados")
        self.tabs.addTab(self._build_template_tab(), "Criar Template")

    # ================== COBRANCA TAB ==================

    def _build_cobranca_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #0d1117; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: #0d1117;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Filters ──
        filter_card = QFrame()
        filter_card.setStyleSheet("""
            QFrame { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
        """)
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(20, 16, 20, 16)
        filter_layout.setSpacing(12)

        filter_title = QLabel("FILTROS")
        filter_title.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 700; letter-spacing: 0.5px;")
        filter_layout.addWidget(filter_title)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        date_row.addWidget(QLabel("Vencimento inicial:"))
        self.dt_ini = QDateEdit()
        self.dt_ini.setCalendarPopup(True)
        self.dt_ini.setDate(QDate.currentDate().addMonths(-1))
        self.dt_ini.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 6px; color: #c9d1d9;")
        date_row.addWidget(self.dt_ini)
        date_row.addWidget(QLabel("Vencimento final:"))
        self.dt_fim = QDateEdit()
        self.dt_fim.setCalendarPopup(True)
        self.dt_fim.setDate(QDate.currentDate())
        self.dt_fim.setStyleSheet(self.dt_ini.styleSheet())
        date_row.addWidget(self.dt_fim)
        date_row.addStretch()
        filter_layout.addLayout(date_row)

        self.btn_filtrar = QPushButton("Filtrar")
        self.btn_filtrar.setCursor(Qt.PointingHandCursor)
        self.btn_filtrar.setStyleSheet("""
            QPushButton { background: #1f6feb; color: #fff; border: none;
                border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: 700; }
            QPushButton:hover { background: #388bfd; }
        """)
        self.btn_filtrar.clicked.connect(self._filtrar)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_filtrar)
        filter_layout.addLayout(btn_row)

        # Pagination row
        page_row = QHBoxLayout()
        self.lbl_loading = QLabel("Nenhum")
        self.lbl_loading.setStyleSheet("font-size: 12px; color: #8b949e; font-weight: 600;")
        page_row.addWidget(self.lbl_loading)

        self.lbl_configured_hidden = QLabel("0 clientes ocultos")
        self.lbl_configured_hidden.setStyleSheet("font-size: 12px; color: #8b949e;")
        self.lbl_configured_hidden.setCursor(Qt.PointingHandCursor)
        self.lbl_configured_hidden.mousePressEvent = lambda e: self._show_hidden_clients_dialog()
        page_row.addWidget(self.lbl_configured_hidden)

        page_row.addStretch()

        self.btn_prev = QPushButton("< Anterior")
        self.btn_prev.setEnabled(False)
        self.btn_prev.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d;
                border-radius: 4px; color: #c9d1d9; padding: 6px 16px;
                font-size: 12px; font-weight: 600; }
            QPushButton:hover { background: #30363d; }
            QPushButton:disabled { color: #484f58; }
        """)
        self.btn_prev.clicked.connect(self._pag_prev)
        page_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Próximo >")
        self.btn_next.setEnabled(False)
        self.btn_next.setStyleSheet(self.btn_prev.styleSheet())
        self.btn_next.clicked.connect(self._pag_next)
        page_row.addWidget(self.btn_next)

        filter_layout.addLayout(page_row)
        layout.addWidget(filter_card)

        # ── Results Table ──
        results_label = QLabel("RESULTADOS")
        results_label.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 700; letter-spacing: 0.5px;")
        layout.addWidget(results_label)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(["", "Cód. Cliente", "Cliente", "Celular", "Valor Total", "Vencimento", "Dias Atraso", "Já Enviado", "Tempo Restante"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setMinimumHeight(200)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; font-size: 12px; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background-color: rgba(31,111,235,0.3); }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 8px; font-weight: 600; font-size: 11px; }
        """)
        layout.addWidget(self.table, 1)
        self.table.itemChanged.connect(self._on_check_changed)

        # ── Preview ──
        preview_card = QFrame()
        preview_card.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(20, 12, 20, 12)
        preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_title = QLabel("PRÉVIA DO ENVIO")
        preview_title.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 700; letter-spacing: 0.5px;")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()
        preview_layout.addLayout(preview_header)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(80)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("""
            QTextEdit { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 8px; color: #c9d1d9;
                font-size: 11px; font-family: Consolas, monospace; }
        """)
        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_card)

        # ── Selected + Actions ──
        actions_card = QFrame()
        actions_card.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(20, 16, 20, 16)
        actions_layout.setSpacing(10)

        sel_header = QHBoxLayout()
        sel_title = QLabel("SELECIONADOS PARA ENVIO")
        sel_title.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 700; letter-spacing: 0.5px;")
        sel_header.addWidget(sel_title)
        self.lbl_selected_count = QLabel("0 clientes")
        self.lbl_selected_count.setStyleSheet("font-size: 12px; color: #58a6ff; font-weight: 600;")
        sel_header.addWidget(self.lbl_selected_count)
        sel_header.addStretch()
        actions_layout.addLayout(sel_header)

        template_row = QHBoxLayout()
        template_row.setSpacing(8)
        template_row.addWidget(QLabel("Template:"))
        self.cmb_template = QComboBox()
        self.cmb_template.setMinimumWidth(250)
        self.cmb_template.setStyleSheet("""
            QComboBox { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        self.cmb_template.currentIndexChanged.connect(self._update_preview)
        template_row.addWidget(self.cmb_template)
        template_row.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #f85149;
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; color: #f85149; }
            QPushButton:hover { background: rgba(248,81,73,0.1); }
        """)
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar_selecao)
        template_row.addWidget(self.btn_cancelar)

        self.btn_configurar = QPushButton("Configurar")
        self.btn_configurar.setCursor(Qt.PointingHandCursor)
        self.btn_configurar.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #d29922;
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; color: #d29922; }
            QPushButton:hover { background: rgba(210,153,34,0.1); }
            QPushButton:disabled { border-color: #30363d; color: #484f58; }
        """)
        self.btn_configurar.setEnabled(False)
        self.btn_configurar.clicked.connect(self._configurar)
        template_row.addWidget(self.btn_configurar)

        self.btn_enviar = QPushButton("Enviar Agora")
        self.btn_enviar.setCursor(Qt.PointingHandCursor)
        self.btn_enviar.setStyleSheet("""
            QPushButton { background: #3fb950; color: #fff; border: none;
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; }
            QPushButton:hover { background: #4cda64; }
            QPushButton:disabled { background: #21262d; color: #484f58; }
        """)
        self.btn_enviar.setEnabled(False)
        self.btn_enviar.clicked.connect(self._enviar)
        template_row.addWidget(self.btn_enviar)

        actions_layout.addLayout(template_row)
        layout.addWidget(actions_card)

        scroll.setWidget(container)
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(scroll)
        return wrapper

    # ================== CLIENTES CONFIGURADOS TAB ==================

    def _build_clientes_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Clientes Configurados")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #c9d1d9;")
        header.addWidget(title)
        header.addStretch()

        btn_refresh_jobs = QPushButton("Atualizar")
        btn_refresh_jobs.setCursor(Qt.PointingHandCursor)
        btn_refresh_jobs.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; color: #c9d1d9; padding: 8px 16px;
                font-size: 12px; font-weight: 600; }
            QPushButton:hover { background: #30363d; }
        """)
        btn_refresh_jobs.clicked.connect(self._refresh_clientes_tab)
        header.addWidget(btn_refresh_jobs)
        layout.addLayout(header)

        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(7)
        self.jobs_table.setHorizontalHeaderLabels(["Nome", "Clientes", "Template", "Tag", "Agendado Para", "Status", "Ações"])
        self.jobs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.jobs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.jobs_table.horizontalHeader().resizeSection(6, 200)
        self.jobs_table.horizontalHeader().setStretchLastSection(False)
        self.jobs_table.setAlternatingRowColors(True)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jobs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.verticalHeader().setDefaultSectionSize(40)
        self.jobs_table.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; font-size: 12px; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 8px; font-weight: 600; font-size: 11px; }
        """)
        layout.addWidget(self.jobs_table, 1)

        self._refresh_clientes_tab()
        return container

    def _refresh_clientes_tab(self):
        jobs = self._load_jobs()
        self.jobs_table.setRowCount(0)
        for j in jobs:
            row = self.jobs_table.rowCount()
            self.jobs_table.insertRow(row)
            self.jobs_table.setItem(row, 0, QTableWidgetItem(j.get("name", "")))
            self.jobs_table.setItem(row, 1, QTableWidgetItem(str(len(j.get("clients", [])))))
            self.jobs_table.setItem(row, 2, QTableWidgetItem(j.get("template_name", "")))
            tag = j.get("tag", "")
            self.jobs_table.setItem(row, 3, QTableWidgetItem(tag if tag else "-"))
            sched = j.get("scheduled_for", "")
            if sched:
                try:
                    dt = datetime.fromisoformat(sched)
                    sched = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass
            self.jobs_table.setItem(row, 4, QTableWidgetItem(sched))
            status = j.get("status", "pending")
            status_item = QTableWidgetItem(status.upper())
            if status == "pending":
                status_item.setForeground(QColor("#d29922"))
            elif status in ("sent",):
                status_item.setForeground(Qt.green)
            elif status in ("partial",):
                status_item.setForeground(QColor("#f8891d"))
            elif status == "error":
                status_item.setForeground(Qt.red)
            self.jobs_table.setItem(row, 5, status_item)

            btn_ver = QPushButton("Ver")
            btn_ver.setStyleSheet("""
                QPushButton { background: transparent; border: 1px solid #58a6ff;
                    border-radius: 4px; color: #58a6ff; padding: 4px 12px;
                    font-size: 11px; font-weight: 600; }
                QPushButton:hover { background: rgba(88,166,255,0.1); }
            """)
            btn_ver.clicked.connect(lambda checked, jid=j["id"]: self._show_job_clients_dialog(jid))

            if status == "pending":
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(6, 3, 6, 3)
                actions_layout.setSpacing(6)
                actions_layout.addWidget(btn_ver)

                btn_cancel = QPushButton("Cancelar")
                btn_cancel.setMinimumWidth(75)
                btn_cancel.setStyleSheet("""
                    QPushButton { background: transparent; border: 1px solid #f85149;
                        border-radius: 4px; color: #f85149; padding: 4px 10px;
                        font-size: 11px; font-weight: 600; }
                    QPushButton:hover { background: rgba(248,81,73,0.1); }
                """)
                btn_cancel.clicked.connect(lambda checked, jid=j["id"]: self._cancelar_job(jid))
                actions_layout.addWidget(btn_cancel)
                self.jobs_table.setCellWidget(row, 6, actions_widget)
            else:
                nfo = j.get("result", {})
                result_text = f"OK {nfo.get('success', 0)}/{nfo.get('total', 0)}"
                if nfo.get("errors"):
                    result_text += f" · {nfo['errors']} erros"

                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(6, 3, 6, 3)
                actions_layout.setSpacing(6)
                actions_layout.addWidget(btn_ver)

                lbl_result = QLabel(result_text)
                lbl_result.setStyleSheet("font-size: 11px; color: #8b949e;")
                actions_layout.addWidget(lbl_result)
                self.jobs_table.setCellWidget(row, 6, actions_widget)

        self.jobs_table.setRowCount(len(jobs))

    def _show_job_clients_dialog(self, job_id: str):
        jobs = self._load_jobs()
        job = None
        for j in jobs:
            if j["id"] == job_id:
                job = j
                break
        if not job:
            return

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Clientes - {job.get('name', '')}")
        dlg.resize(600, 400)
        dlg.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; font-size: 13px; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"{job.get('name', '')} — {len(job.get('clients', []))} cliente(s)")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #f1f5f9;")
        layout.addWidget(title)

        info = QLabel(f"Template: {job.get('template_name', '')} · Tag: {job.get('tag', '-')} · Status: {job.get('status', 'pending').upper()}")
        info.setStyleSheet("font-size: 12px; color: #8b949e;")
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Código", "Nome", "Celular", "Valor"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; font-size: 12px; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 6px; font-weight: 600; font-size: 11px; }
        """)

        for c in job.get("clients", []):
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(str(c[2]) if len(c) > 2 and c[2] is not None else "-"))
            nome = str(c[3]) if len(c) > 3 and c[3] else "-"
            table.setItem(r, 1, QTableWidgetItem(nome))
            cel = str(c[5]).strip() if len(c) > 5 and c[5] else "-"
            table.setItem(r, 2, QTableWidgetItem(cel))
            valor = self._format_valor(c[20]) if len(c) > 20 else "-"
            table.setItem(r, 3, QTableWidgetItem(valor))

        layout.addWidget(table, 1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; color: #c9d1d9; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }
            QPushButton:hover { background: #30363d; }
        """)
        btn_fechar.clicked.connect(dlg.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_fechar)
        layout.addLayout(btn_layout)

        dlg.exec()

    # ================== TEMPLATE TAB ==================

    def _build_template_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #0d1117; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: #0d1117;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Criar Template")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #c9d1d9;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Template name + load/save/delete
        manage_row = QHBoxLayout()
        manage_row.setSpacing(8)
        manage_row.addWidget(QLabel("Template:"))
        self.cmb_saved_templates = QComboBox()
        self.cmb_saved_templates.setMinimumWidth(250)
        self.cmb_saved_templates.setStyleSheet("""
            QComboBox { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        self.cmb_saved_templates.currentIndexChanged.connect(self._load_selected_template)
        manage_row.addWidget(self.cmb_saved_templates)

        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Nome do template...")
        self.template_name_input.setStyleSheet("""
            QLineEdit { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        manage_row.addWidget(self.template_name_input, 1)

        btn_save_template = QPushButton("Salvar")
        btn_save_template.setStyleSheet("""
            QPushButton { background: #238636; color: #fff; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; font-weight: 600; }
            QPushButton:hover { background: #2ea043; }
        """)
        btn_save_template.clicked.connect(self._save_template)
        manage_row.addWidget(btn_save_template)

        btn_delete_template = QPushButton("Excluir")
        btn_delete_template.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #f85149;
                border-radius: 4px; color: #f85149; padding: 6px 16px;
                font-size: 12px; font-weight: 600; }
            QPushButton:hover { background: rgba(248,81,73,0.1); }
        """)
        btn_delete_template.clicked.connect(self._delete_template)
        manage_row.addWidget(btn_delete_template)

        layout.addLayout(manage_row)

        # Tag
        tag_row = QHBoxLayout()
        tag_row.setSpacing(8)
        tag_row.addWidget(QLabel("Tag:"))
        self.tmpl_tag = QLineEdit()
        self.tmpl_tag.setPlaceholderText("cobrança, promoção, aviso...")
        self.tmpl_tag.setStyleSheet("""
            QLineEdit { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        tag_row.addWidget(self.tmpl_tag, 1)
        layout.addLayout(tag_row)

        # Method + URL
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.tmpl_method = QComboBox()
        self.tmpl_method.addItems(["POST", "GET", "PUT", "PATCH", "DELETE"])
        self.tmpl_method.setCurrentText("POST")
        self.tmpl_method.setFixedWidth(90)
        self.tmpl_method.setStyleSheet("""
            QComboBox { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        url_row.addWidget(self.tmpl_method)
        self.tmpl_url = QLineEdit()
        self.tmpl_url.setPlaceholderText("https://app.mundodosbots.com.br/api/users")
        self.tmpl_url.setStyleSheet("""
            QLineEdit { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px; color: #c9d1d9; font-size: 12px; }
        """)
        url_row.addWidget(self.tmpl_url, 1)
        btn_paste = QPushButton("Colar")
        btn_paste.setFixedWidth(60)
        btn_paste.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d;
                border-radius: 4px; color: #c9d1d9; padding: 6px;
                font-size: 11px; font-weight: 600; }
            QPushButton:hover { background: #30363d; }
        """)
        btn_paste.clicked.connect(self._import_curl_template)
        url_row.addWidget(btn_paste)
        layout.addLayout(url_row)

        # Headers
        headers_label = QLabel("HEADERS")
        headers_label.setStyleSheet("font-size: 10px; color: #8b949e; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(headers_label)

        self.tmpl_headers = QTableWidget()
        self.tmpl_headers.setColumnCount(3)
        self.tmpl_headers.setHorizontalHeaderLabels(["Chave", "Valor", ""])
        self.tmpl_headers.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tmpl_headers.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tmpl_headers.horizontalHeader().resizeSection(2, 40)
        self.tmpl_headers.verticalHeader().setVisible(False)
        self.tmpl_headers.verticalHeader().setDefaultSectionSize(30)
        self.tmpl_headers.setEditTriggers(QTableWidget.DoubleClicked)
        self.tmpl_headers.setMinimumHeight(100)
        self.tmpl_headers.setMaximumHeight(140)
        self.tmpl_headers.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; font-size: 11px; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 4px; font-weight: 600; font-size: 10px; }
        """)
        for key, val in DEFAULT_HEADERS:
            self._add_tmpl_header_row(key, val)
        layout.addWidget(self.tmpl_headers)

        btn_add_hdr = QPushButton("+ Adicionar header")
        btn_add_hdr.setStyleSheet("""
            QPushButton { background: transparent; border: 1px dashed #30363d;
                border-radius: 4px; color: #8b949e; padding: 6px;
                font-size: 11px; font-weight: 600; }
            QPushButton:hover { border-color: #58a6ff; color: #58a6ff; }
        """)
        btn_add_hdr.clicked.connect(lambda: self._add_tmpl_header_row())
        layout.addWidget(btn_add_hdr)

        # Body
        body_label = QLabel("BODY TEMPLATE")
        body_label.setStyleSheet("font-size: 10px; color: #8b949e; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(body_label)

        self.tmpl_body = QTextEdit()
        self.tmpl_body.setPlainText(DEFAULT_BODY_TEMPLATE)
        self.tmpl_body.setMinimumHeight(160)
        self.tmpl_body.setMaximumHeight(240)
        self.tmpl_body.setStyleSheet("""
            QTextEdit { background: #0d1117; border: 1px solid #30363d;
                border-radius: 4px; padding: 8px; color: #c9d1d9;
                font-size: 11px; font-family: Consolas, monospace; }
        """)
        layout.addWidget(self.tmpl_body)

        # ── Variable Reference ──
        vars_label = QLabel("VARIÁVEIS DISPONÍVEIS")
        vars_label.setStyleSheet("font-size: 10px; color: #8b949e; font-weight: 600; letter-spacing: 0.5px; margin-top: 8px;")
        layout.addWidget(vars_label)

        vars_container = QFrame()
        vars_container.setStyleSheet("""
            QFrame { background-color: #161b22; border: 1px solid #30363d;
                     border-radius: 6px; }
        """)
        vars_inner = QVBoxLayout(vars_container)
        vars_inner.setContentsMargins(12, 10, 12, 10)
        vars_inner.setSpacing(6)

        var_desc = QLabel("Use <b>{placeholder}</b> no Body Template e Headers. Eles serão substituídos pelos dados de cada cliente.")
        var_desc.setWordWrap(True)
        var_desc.setStyleSheet("font-size: 11px; color: #8b949e; border: none;")
        vars_inner.addWidget(var_desc)

        var_table = QTableWidget()
        var_table.setColumnCount(3)
        var_table.setHorizontalHeaderLabels(["Placeholder", "Campo SQL", "Descrição"])
        var_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        var_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        var_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        var_table.verticalHeader().setVisible(False)
        var_table.verticalHeader().setDefaultSectionSize(22)
        var_table.setEditTriggers(QTableWidget.NoEditTriggers)
        var_table.setSelectionMode(QTableWidget.NoSelection)
        var_table.setFocusPolicy(Qt.NoFocus)
        var_table.setMaximumHeight(200)
        var_table.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #21262d; gridline-color: #21262d;
                font-size: 11px; font-family: Consolas, monospace; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: none; border-bottom: 1px solid #30363d;
                padding: 4px; font-weight: 600; font-size: 10px; }
            QTableWidget::item { padding: 2px 8px; }
        """)
        for _, placeholder, col, sql_field, desc in VARS_INFO:
            r = var_table.rowCount()
            var_table.insertRow(r)
            var_table.setItem(r, 0, QTableWidgetItem(placeholder))
            var_table.setItem(r, 1, QTableWidgetItem(f"[{col}] {sql_field}"))
            var_table.setItem(r, 2, QTableWidgetItem(desc))
        vars_inner.addWidget(var_table)
        layout.addWidget(vars_container)

        layout.addStretch()

        scroll.setWidget(container)
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(scroll)

        self._refresh_template_combo()
        return wrapper

    # ================== DATA HELPERS ==================

    def _load_templates(self) -> list:
        try:
            if os.path.exists(TEMPLATES_FILE):
                with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_templates_to_disk(self, templates: list):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            show_error(self, "Erro", f"Não foi possível salvar templates:\n{e}")

    def _load_tag_cooldown_config(self) -> dict:
        try:
            if os.path.exists(TAG_COOLDOWN_FILE):
                with open(TAG_COOLDOWN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_tag_cooldown_config(self, config: dict):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(TAG_COOLDOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            show_error(self, "Erro", f"Não foi possível salvar configuração de cooldown:\n{e}")

    def _load_sent_history(self) -> list:
        try:
            if os.path.exists(SENT_HISTORY_FILE):
                with open(SENT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_sent_history(self, history: list):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SENT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            show_error(self, "Erro", f"Não foi possível salvar histórico de envios:\n{e}")

    def _check_tag_cooldown(self, phone: str, tag: str) -> dict:
        if not tag:
            return {"blocked": False, "remaining_hours": 0}
        cooldown_config = self._load_tag_cooldown_config()
        hours_block = cooldown_config.get(tag, 0)
        if hours_block <= 0:
            return {"blocked": False, "remaining_hours": 0}
        history = self._load_sent_history()
        now = datetime.now()
        for entry in reversed(history):
            if entry.get("phone") == phone and entry.get("tag") == tag:
                sent_at = datetime.fromisoformat(entry["sent_at"])
                elapsed = (now - sent_at).total_seconds() / 3600
                if elapsed < hours_block:
                    return {"blocked": True, "remaining_hours": round(hours_block - elapsed, 1)}
                break
        return {"blocked": False, "remaining_hours": 0}

    def _record_sent(self, phone: str, tag: str):
        if not tag:
            return
        history = self._load_sent_history()
        history.append({
            "phone": phone,
            "tag": tag,
            "sent_at": datetime.now().isoformat(),
        })
        self._save_sent_history(history)

    def _load_jobs(self) -> list:
        try:
            if os.path.exists(JOBS_FILE):
                with open(JOBS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_jobs_to_disk(self, jobs: list):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            show_error(self, "Erro", f"Não foi possível salvar jobs:\n{e}")

    def _refresh_template_combo(self):
        current = self.cmb_template.currentData()
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        templates = self._load_templates()
        for t in templates:
            tag = t.get("tag", "")
            label = f"{t.get('name', 'Sem nome')}  [{tag}]" if tag else t.get("name", "Sem nome")
            self.cmb_template.addItem(label, t)
        self.cmb_template.blockSignals(False)
        if current:
            for i in range(self.cmb_template.count()):
                if self.cmb_template.itemData(i).get("name") == current.get("name"):
                    self.cmb_template.setCurrentIndex(i)
                    break

        # Also refresh the template editor combo
        self.cmb_saved_templates.blockSignals(True)
        current_edit_name = self.cmb_saved_templates.currentText()
        self.cmb_saved_templates.clear()
        self.cmb_saved_templates.addItem("--- Novo Template ---", None)
        for t in templates:
            tag = t.get("tag", "")
            label = f"{t.get('name', 'Sem nome')}  [{tag}]" if tag else t.get("name", "Sem nome")
            self.cmb_saved_templates.addItem(label, t)
        if current_edit_name:
            idx = self.cmb_saved_templates.findText(current_edit_name)
            if idx >= 0:
                self.cmb_saved_templates.setCurrentIndex(idx)
        self.cmb_saved_templates.blockSignals(False)

    # ================== TEMPLATE CRUD ==================

    def _save_template(self):
        name = self.template_name_input.text().strip()
        if not name:
            show_error(self, "Erro", "Informe o nome do template.")
            return
        config = self._get_template_config_from_editor()
        templates = self._load_templates()
        found = False
        for i, t in enumerate(templates):
            if t["name"] == name:
                templates[i] = {"name": name, **config}
                found = True
                break
        if not found:
            templates.append({"name": name, **config})
        self._save_templates_to_disk(templates)
        show_success(self, "OK", f'Template "{name}" salvo!')
        self._refresh_template_combo()

    def _delete_template(self):
        name = self.template_name_input.text().strip()
        if not name:
            return
        if not show_confirm(self, "Confirmar", f'Excluir template "{name}"?'):
            return
        templates = self._load_templates()
        templates = [t for t in templates if t.get("name") != name]
        self._save_templates_to_disk(templates)
        show_success(self, "OK", "Template excluído.")
        self.template_name_input.clear()
        self._refresh_template_combo()

    def _load_selected_template(self):
        data = self.cmb_saved_templates.currentData()
        if not data:
            return
        self.template_name_input.setText(data.get("name", ""))
        self.tmpl_method.setCurrentText(data.get("method", "POST"))
        self.tmpl_url.setText(data.get("url", ""))
        self.tmpl_headers.setRowCount(0)
        for h in data.get("headers", DEFAULT_HEADERS):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                self._add_tmpl_header_row(str(h[0]), str(h[1]))
        self.tmpl_body.setPlainText(data.get("body", DEFAULT_BODY_TEMPLATE))
        self.tmpl_tag.setText(data.get("tag", ""))

    def _get_template_config_from_editor(self) -> dict:
        headers = []
        for row in range(self.tmpl_headers.rowCount()):
            k = self.tmpl_headers.item(row, 0)
            v = self.tmpl_headers.item(row, 1)
            if k and k.text().strip():
                headers.append([k.text().strip(), v.text().strip() if v else ""])
        return {
            "method": self.tmpl_method.currentText(),
            "url": self.tmpl_url.text().strip(),
            "headers": headers,
            "body": self.tmpl_body.toPlainText(),
            "tag": self.tmpl_tag.text().strip(),
        }

    def _add_tmpl_header_row(self, key: str = "", val: str = ""):
        row = self.tmpl_headers.rowCount()
        self.tmpl_headers.insertRow(row)
        self.tmpl_headers.setItem(row, 0, QTableWidgetItem(key))
        self.tmpl_headers.setItem(row, 1, QTableWidgetItem(val))
        btn_del = QPushButton("×")
        btn_del.setStyleSheet("""
            QPushButton { background: transparent; border: none;
                color: #f85149; font-size: 16px; font-weight: 700; }
            QPushButton:hover { color: #ff6b6b; }
        """)
        btn_del.clicked.connect(lambda: self.tmpl_headers.removeRow(row))
        self.tmpl_headers.setCellWidget(row, 2, btn_del)

    def _import_curl_template(self):
        from PySide6.QtWidgets import QDialog as QDlg, QTextEdit as QTE, QVBoxLayout as QVL, QDialogButtonBox as QDB

        dlg = QDlg(self)
        dlg.setWindowTitle("Importar cURL")
        dlg.resize(500, 300)
        dlg.setStyleSheet("QDialog { background-color: #0d1117; color: #c9d1d9; }")
        lay = QVL(dlg)
        lay.addWidget(QLabel("Cole o comando cURL:"))
        editor = QTE()
        editor.setPlaceholderText("curl -X POST https://api.exemplo.com ...")
        editor.setStyleSheet("background: #0d1117; color: #c9d1d9; border: 1px solid #30363d;")
        lay.addWidget(editor)
        btns = QDB(QDB.Ok | QDB.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec():
            text = editor.toPlainText().strip()
            if text:
                self._apply_curl_to_editor(text)

    def _apply_curl_to_editor(self, curl_text: str):
        text = curl_text.strip()
        if text.startswith("curl "):
            text = text[5:]
        parts = []
        current = ""
        in_quote = False
        for ch in text:
            if ch in ("'", '"'):
                in_quote = not in_quote
                current += ch
            elif ch in (" ", "\n", "\\") and not in_quote:
                if current.strip():
                    parts.append(current.strip().strip("\\"))
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current.strip().strip("\\"))

        method = "POST"
        url = ""
        headers = {}
        body = ""
        i = 0
        while i < len(parts):
            p = parts[i]
            if p == "-X" and i + 1 < len(parts):
                method = parts[i + 1].upper()
                i += 2
            elif p in ("-H", "--header") and i + 1 < len(parts):
                h = parts[i + 1].strip("'\"")
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()
                i += 2
            elif p in ("-d", "--data", "--data-raw") and i + 1 < len(parts):
                body = parts[i + 1].strip("'\"")
                i += 2
            elif p.startswith("http"):
                url = p.strip("'\"")
                i += 1
            else:
                i += 1
        if not url:
            for p in parts:
                if p.startswith("http"):
                    url = p.strip("'\"")
                    break

        if url:
            self.tmpl_url.setText(url)
        self.tmpl_method.setCurrentText(method)
        self.tmpl_headers.setRowCount(0)
        for k, v in headers.items():
            self._add_tmpl_header_row(k, v)
        if not headers:
            for k, v in DEFAULT_HEADERS:
                self._add_tmpl_header_row(k, v)
        if body:
            try:
                parsed = json.loads(body)
                self.tmpl_body.setPlainText(json.dumps(parsed, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                self.tmpl_body.setPlainText(body)

    # ================== JOB CRUD ==================

    def _configurar(self):
        if not self._selected_rows:
            return
        template_data = self.cmb_template.currentData()
        if not template_data:
            show_error(self, "Erro", "Selecione um template primeiro.")
            return

        selected = sorted(self._selected_rows)
        clients = []
        for idx in selected:
            if idx < len(self._results_data):
                r = self._results_data[idx]
                clients.append(self._serialize_row(r))

        from frontend.app.widgets.schedule_dialog import ScheduleDialog

        dlg = ScheduleDialog(self, len(clients), template_data.get("name", ""))
        if not dlg.exec():
            return

        schedule = dlg.get_schedule()
        job_name = f"Cobrança {datetime.now().strftime('%d/%m/%Y %H:%M')}"

        job = {
            "id": str(uuid.uuid4())[:8],
            "name": job_name,
            "created_at": datetime.now().isoformat(),
            "scheduled_for": schedule.get("datetime") if schedule.get("mode") == "scheduled" else "",
            "template_name": template_data.get("name", ""),
            "tag": template_data.get("tag", ""),
            "config": {
                "method": template_data.get("method", "POST"),
                "url": template_data.get("url", ""),
                "headers": template_data.get("headers", DEFAULT_HEADERS),
                "body": template_data.get("body", DEFAULT_BODY_TEMPLATE),
            },
            "clients": clients,
            "status": "pending",
            "result": {},
        }

        jobs = self._load_jobs()
        jobs.append(job)
        self._save_jobs_to_disk(jobs)

        for c in clients:
            self._configured_set.add((str(c[0]), str(c[2])))

        show_success(self, "OK", f"Agendamento criado para {len(clients)} cliente(s).")

        self._cancelar_selecao()
        self._filtrar(keep_page=True)
        self._refresh_clientes_tab()

    def _cancelar_job(self, job_id: str):
        if not show_confirm(self, "Confirmar", "Cancelar este agendamento?"):
            return
        jobs = self._load_jobs()
        jobs = [j for j in jobs if j["id"] != job_id]
        self._save_jobs_to_disk(jobs)
        self._load_configured_set()
        self._refresh_clientes_tab()
        self._filtrar(keep_page=True)

    # ================== TIMER ==================

    def _start_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_scheduled_jobs)
        self._timer.start(30000)

    def _check_scheduled_jobs(self):
        jobs = self._load_jobs()
        now = datetime.now()
        changed = False
        for job in jobs:
            if job["status"] == "pending" and job.get("scheduled_for"):
                try:
                    sched = datetime.fromisoformat(job["scheduled_for"])
                    if sched <= now:
                        self._execute_job_async(job)
                        changed = True
                except Exception:
                    pass
        if changed:
            self._save_jobs_to_disk(jobs)

    def _execute_job_async(self, job):
        job["status"] = "sending"
        job_tag = job.get("tag", "")

        def _do():
            config = job.get("config", {})
            url = config.get("url", "")
            method = config.get("method", "POST")
            headers_list = config.get("headers", [])
            headers = {}
            for h in headers_list:
                if isinstance(h, (list, tuple)) and len(h) >= 2 and h[0]:
                    headers[str(h[0])] = str(h[1])
            body_template = config.get("body", "")
            clients = job.get("clients", [])
            results = {"success": 0, "errors": 0, "blocked": 0, "total": len(clients), "details": []}
            with httpx.Client(timeout=30.0) as client:
                for c in clients:
                    phone = str(c[5]).strip() if len(c) > 5 and c[5] else ""

                    cooldown = self._check_tag_cooldown(phone, job_tag)
                    if cooldown["blocked"]:
                        results["blocked"] += 1
                        continue

                    body = self._substitute_placeholders(body_template, tuple(c))
                    try:
                        if method == "GET":
                            resp = client.get(url, headers=headers)
                        elif method == "PUT":
                            resp = client.put(url, headers=headers, content=body)
                        elif method == "PATCH":
                            resp = client.patch(url, headers=headers, content=body)
                        elif method == "DELETE":
                            resp = client.delete(url, headers=headers, content=body)
                        else:
                            resp = client.post(url, headers=headers, content=body)
                        if resp.status_code < 300:
                            results["success"] += 1
                            self._record_sent(phone, job_tag)
                        else:
                            results["errors"] += 1
                    except Exception:
                        results["errors"] += 1
            return results, job["id"]

        def _on_done(results_and_id):
            results, job_id = results_and_id
            jobs = self._load_jobs()
            for j in jobs:
                if j["id"] == job_id:
                    if results["errors"] == 0 and results["blocked"] == 0:
                        j["status"] = "sent"
                    elif results["success"] > 0:
                        j["status"] = "partial"
                    else:
                        j["status"] = "error"
                    j["result"] = results
                    break
            self._save_jobs_to_disk(jobs)
            self._load_configured_set()
            self._refresh_clientes_tab()

        def _on_error(e):
            jobs = self._load_jobs()
            for j in jobs:
                if j["id"] == job["id"]:
                    j["status"] = "error"
                    j["result"] = {"error": str(e)}
                    break
            self._save_jobs_to_disk(jobs)
            self._refresh_clientes_tab()

        run_in_thread(_do, _on_done, _on_error)

    # ================== FILTER / PAGINATION ==================

    def _filtrar(self, keep_page: bool = False):
        if not keep_page:
            self._page = 0

        data_ini = self.dt_ini.date().toString("yyyy-MM-dd")
        data_fim = self.dt_fim.date().toString("yyyy-MM-dd")
        empresa = self.user.get("eco_empresa", "01")

        sql = COBRANCA_SQL.format(
            tipo_filter="",
        )

        self.btn_filtrar.setEnabled(False)
        self.btn_filtrar.setText("Filtrando...")
        self.lbl_loading.setText("Carregando...")
        self.table.setRowCount(0)

        def _do_query():
            logger.info("QUERY", "Iniciando consulta Firebird...",
                        data_ini=data_ini, data_fim=data_fim)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                params = (empresa, data_ini, data_fim)
                futuro = executor.submit(fb.query, sql, params)
                rows = futuro.result(timeout=120)
                logger.info("QUERY", f"Consulta concluida: {len(rows)} linhas")
                return rows
            except concurrent.futures.TimeoutError:
                logger.error("QUERY", "Consulta excedeu 120s de timeout")
                raise TimeoutError("A consulta excedeu o tempo limite de 120 segundos. Tente reduzir o periodo de datas.")
            except Exception as e:
                logger.error("QUERY", f"Erro na consulta: {e}")
                raise e
            finally:
                executor.shutdown(wait=False)

        def _on_result(rows):
            logger.info("QUERY", f"_on_result chamado com {len(rows)} linhas")
            try:
                self.btn_filtrar.setEnabled(True)
                self.btn_filtrar.setText("Filtrar")
                self.lbl_loading.setText("Carregado")
                self.lbl_loading.setStyleSheet("font-size: 12px; color: #3fb950; font-weight: 600;")

                filtered = []
                self._hidden_clients_data = []
                hidden_count = 0
                for r in rows:
                    key = (str(r[0]), str(r[2]))
                    if key in self._configured_set:
                        hidden_count += 1
                        self._hidden_clients_data.append(r)
                    else:
                        filtered.append(r)

                self._results_data = filtered
                self._selected_rows.clear()
                self._update_selected_count()
                self._has_more = False

                self._update_hidden_label(hidden_count)
                self._update_page_info()

                if not filtered:
                    if hidden_count:
                        show_error(self, "Sem Resultados", "Todos os resultados desta página já foram configurados. Avance para a próxima página ou ajuste os filtros.")
                    else:
                        show_error(self, "Sem Resultados", "Nenhum cliente encontrado com os filtros atuais.")
                    self.table.setRowCount(0)
                    return

                phones = [str(r[5]).strip() if r[5] else "" for r in filtered]
                self._check_sent_status(phones, filtered)
            except Exception as e:
                logger.error("QUERY", f"Erro em _on_result: {e}")
                import traceback
                logger.error("QUERY", traceback.format_exc())
                self.btn_filtrar.setEnabled(True)
                self.btn_filtrar.setText("Filtrar")
                self.lbl_loading.setText("Nenhum")
                self.lbl_loading.setStyleSheet("font-size: 12px; color: #f85149; font-weight: 600;")
                show_error(self, "Erro", f"Erro ao processar resultados:\n{e}")

        def _on_error(e):
            self.btn_filtrar.setEnabled(True)
            self.btn_filtrar.setText("Filtrar")
            self.lbl_loading.setText("Nenhum")
            self.lbl_loading.setStyleSheet("font-size: 12px; color: #f85149; font-weight: 600;")
            show_error(self, "Erro", f"Falha ao executar consulta:\n{e}")

        run_in_thread(_do_query, _on_result, _on_error)

    def _pag_next(self):
        self._page += 1
        self._filtrar(keep_page=True)

    def _pag_prev(self):
        if self._page > 0:
            self._page -= 1
            self._filtrar(keep_page=True)

    def _update_hidden_label(self, count: int):
        self.lbl_configured_hidden.setText(f"{count} cliente(s) oculto(s)")
        if count > 0:
            self.lbl_configured_hidden.setStyleSheet("font-size: 12px; color: #58a6ff; text-decoration: underline;")
        else:
            self.lbl_configured_hidden.setStyleSheet("font-size: 12px; color: #8b949e;")

    def _update_page_info(self):
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

    def _show_hidden_clients_dialog(self):
        if not self._hidden_clients_data:
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("Clientes Ocultos")
        dlg.resize(600, 400)
        dlg.setStyleSheet("""
            QDialog { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #c9d1d9; font-size: 13px; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"Clientes ocultos ({len(self._hidden_clients_data)})")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #f1f5f9;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Código", "Nome", "Celular", ""])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.horizontalHeader().resizeSection(3, 150)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setStyleSheet("""
            QTableWidget { background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; gridline-color: #21262d; font-size: 12px; }
            QHeaderView::section { background: #161b22; color: #8b949e;
                border: 1px solid #30363d; padding: 6px; font-weight: 600; font-size: 11px; }
        """)

        for i, r in enumerate(self._hidden_clients_data):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(r[2]) if r[2] is not None else "-"))
            table.setItem(row, 1, QTableWidgetItem(str(r[3]) if r[3] else "-"))
            cel = str(r[5]).strip() if r[5] else "-"
            table.setItem(row, 2, QTableWidgetItem(cel))

            container_w = QWidget()
            container_l = QHBoxLayout(container_w)
            container_l.setContentsMargins(4, 2, 4, 2)
            btn_remover = QPushButton("Remover")
            btn_remover.setMinimumWidth(80)
            btn_remover.setStyleSheet("""
                QPushButton { background: transparent; border: 1px solid #f85149;
                    border-radius: 4px; color: #f85149; padding: 4px 8px;
                    font-size: 11px; font-weight: 600; }
                QPushButton:hover { background: rgba(248,81,73,0.1); }
            """)
            btn_remover.clicked.connect(lambda checked, idx=i: self._remove_hidden_client(idx, dlg, table))
            container_l.addWidget(btn_remover)
            table.setCellWidget(row, 3, container_w)

        layout.addWidget(table, 1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; color: #c9d1d9; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }
            QPushButton:hover { background: #30363d; }
        """)
        btn_fechar.clicked.connect(dlg.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_fechar)
        layout.addLayout(btn_layout)

        dlg.exec()

    def _remove_hidden_client(self, idx: int, dlg, table):
        if idx >= len(self._hidden_clients_data):
            return
        r = self._hidden_clients_data[idx]
        key = (str(r[0]), str(r[2]))

        jobs = self._load_jobs()
        changed = False
        for job in jobs:
            if job["status"] != "pending":
                continue
            job["clients"] = [c for c in job["clients"] if not (str(c[0]) == key[0] and str(c[2]) == key[1])]
            if not job["clients"]:
                job["status"] = "cancelled"
            changed = True
        if changed:
            self._save_jobs_to_disk(jobs)

        self._configured_set.discard(key)
        self._hidden_clients_data.pop(idx)
        self._load_configured_set()

        dlg.reject()
        self._show_hidden_clients_dialog()
        self._filtrar(keep_page=True)

    # ================== SENT STATUS ==================

    def _check_sent_status(self, phones: list, rows: list):
        uniq = list(set(p for p in phones if p))

        def _do_check():
            from frontend.app.api.client import client as api_client
            try:
                resp = api_client.post("/api/cobranca/check-sent", {"phones": uniq})
                if resp.status_code == 200:
                    return resp.json().get("results", {})
            except Exception:
                pass
            return {}

        def _on_checked(results: dict):
            self._sent_check_cache = results
            self._populate_table(rows, results)

        def _on_error(e):
            self._populate_table(rows, {})

        if uniq:
            run_in_thread(_do_check, _on_checked, _on_error)
        else:
            self._populate_table(rows, {})

    # ================== TABLE ==================

    def _populate_table(self, rows: list, sent_status: dict):
        try:
            self.table.setRowCount(0)
            self.table.blockSignals(True)
            try:
                for idx, r in enumerate(rows):
                    row = self.table.rowCount()
                    self.table.insertRow(row)

                    check_item = QTableWidgetItem("")
                    check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    check_item.setCheckState(Qt.Unchecked)
                    check_item.setData(Qt.UserRole, idx)
                    self.table.setItem(row, 0, check_item)

                    cod_cliente = str(r[2]) if r[2] is not None else "-"
                    self.table.setItem(row, 1, QTableWidgetItem(cod_cliente))
                    cliente = str(r[3]) if r[3] else f"Código {r[2]}"
                    self.table.setItem(row, 2, QTableWidgetItem(cliente))
                    celular = str(r[5]).strip() if r[5] else "-"
                    self.table.setItem(row, 3, QTableWidgetItem(celular))
                    self.table.setItem(row, 4, QTableWidgetItem(self._format_valor(r[20])))
                    venc = self._format_date(r[17])
                    self.table.setItem(row, 5, QTableWidgetItem(venc))
                    atraso = str(r[15]) if r[15] is not None else "0"
                    self.table.setItem(row, 6, QTableWidgetItem(f"{atraso} dias"))

                    phone = celular
                    sent_info = sent_status.get(phone, {})
                    ja_enviado = sent_info.get("sent", False)
                    remaining = sent_info.get("remaining_hours", 0)

                    env_item = QTableWidgetItem("Sim" if ja_enviado else "Não")
                    env_item.setForeground(Qt.red if ja_enviado else Qt.green)
                    self.table.setItem(row, 7, env_item)

                    if ja_enviado and remaining > 0:
                        resto = f"{remaining:.0f}h restantes"
                        resto_item = QTableWidgetItem(resto)
                        resto_item.setForeground(QColor("#d29922"))
                    elif ja_enviado:
                        resto_item = QTableWidgetItem("Disponível")
                        resto_item.setForeground(Qt.green)
                    else:
                        resto_item = QTableWidgetItem("-")
                    self.table.setItem(row, 8, resto_item)
            finally:
                self.table.blockSignals(False)
            logger.info("TABLE", f"Tabela populada com {len(rows)} linhas")
        except Exception as e:
            logger.error("TABLE", f"Erro ao popular tabela: {e}")
            import traceback
            logger.error("TABLE", traceback.format_exc())
            self.btn_filtrar.setEnabled(True)
            self.btn_filtrar.setText("Filtrar")
            self.lbl_loading.setText("Nenhum")
            self.lbl_loading.setStyleSheet("font-size: 12px; color: #f85149; font-weight: 600;")
            show_error(self, "Erro", f"Erro ao popular tabela:\n{e}")

    def _on_check_changed(self, item):
        if item.column() != 0:
            return
        idx = item.data(Qt.UserRole)
        if idx is None:
            return
        if item.checkState() == Qt.Checked:
            self._selected_rows.add(idx)
        else:
            self._selected_rows.discard(idx)
        self._update_selected_count()
        self._update_preview()

    def _update_selected_count(self):
        count = len(self._selected_rows)
        self.lbl_selected_count.setText(f"{count} cliente{'s' if count != 1 else ''}")
        self.btn_enviar.setEnabled(count > 0 and self.cmb_template.currentData() is not None)
        self.btn_configurar.setEnabled(count > 0 and self.cmb_template.currentData() is not None)
        self.btn_cancelar.setEnabled(count > 0)

    def _cancelar_selecao(self):
        self._selected_rows.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._update_selected_count()
        self._update_preview()

    # ================== PREVIEW ==================

    def _update_preview(self):
        template_data = self.cmb_template.currentData()
        if not template_data or not self._selected_rows:
            self.preview_text.clear()
            return

        first_idx = min(self._selected_rows)
        if first_idx >= len(self._results_data):
            self.preview_text.clear()
            return

        row = self._results_data[first_idx]
        body = template_data.get("body", "")
        substituted = self._substitute_placeholders(body, row)
        self.preview_text.setPlainText(substituted)

    # ================== SEND ==================

    def _enviar(self):
        if not self._selected_rows:
            return

        template_data = self.cmb_template.currentData()
        if not template_data:
            show_error(self, "Erro", "Selecione um template.")
            return

        url = template_data.get("url", "").strip()
        if not url:
            show_error(self, "Erro", "O template não possui URL configurada.")
            return

        method = template_data.get("method", "POST")
        body_template = template_data.get("body", "")
        headers_list = template_data.get("headers", [])
        headers = {}
        for h in headers_list:
            if isinstance(h, (list, tuple)) and len(h) >= 2 and h[0]:
                headers[str(h[0])] = str(h[1])

        tag = template_data.get("tag", "")

        selected = sorted(self._selected_rows)
        if not selected:
            return

        self.btn_enviar.setEnabled(False)
        self.btn_enviar.setText("Enviando...")

        def _do_send():
            results = {"success": 0, "errors": 0, "blocked": 0, "total": len(selected), "details": []}
            with httpx.Client(timeout=30.0) as client:
                for idx in selected:
                    row = self._results_data[idx]
                    phone = str(row[5]).strip() if row[5] else ""

                    cooldown = self._check_tag_cooldown(phone, tag)
                    if cooldown["blocked"]:
                        results["blocked"] += 1
                        results["details"].append({"idx": idx, "ok": False, "blocked": True, "remaining": cooldown["remaining_hours"]})
                        continue

                    body = self._substitute_placeholders(body_template, row)
                    try:
                        if method == "GET":
                            resp = client.get(url, headers=headers)
                        elif method == "PUT":
                            resp = client.put(url, headers=headers, content=body)
                        elif method == "PATCH":
                            resp = client.patch(url, headers=headers, content=body)
                        elif method == "DELETE":
                            resp = client.delete(url, headers=headers, content=body)
                        else:
                            resp = client.post(url, headers=headers, content=body)
                        if resp.status_code < 300:
                            results["success"] += 1
                            self._record_sent(phone, tag)
                            results["details"].append({"idx": idx, "ok": True, "status": resp.status_code})
                        else:
                            results["errors"] += 1
                            results["details"].append({"idx": idx, "ok": False, "status": resp.status_code, "body": resp.text[:200]})
                    except Exception as e:
                        results["errors"] += 1
                        results["details"].append({"idx": idx, "ok": False, "error": str(e)})
            return results

        def _on_sent(results: dict):
            self.btn_enviar.setEnabled(True)
            self.btn_enviar.setText("Enviar Agora")
            parts = [f"{results['success']} de {results['total']} enviados com sucesso."]
            if results["blocked"]:
                parts.append(f"\n{results['blocked']} bloqueado(s) pelo cooldown da tag '{tag}'.")
            if results["errors"]:
                parts.append(f"\n{results['errors']} falha(s).")
            msg = "".join(parts)
            if results["errors"]:
                erros = [d for d in results["details"] if not d["ok"] and not d.get("blocked")]
                if erros:
                    primeiro = erros[0]
                    erro_detalhe = primeiro.get("error") or f"HTTP {primeiro.get('status')}"
                    msg += f"\n\nExemplo de erro: {erro_detalhe}"
            show_success(self, "Resultado do Envio", msg)
            self._cancelar_selecao()

        def _on_error(e):
            self.btn_enviar.setEnabled(True)
            self.btn_enviar.setText("Enviar Agora")
            show_error(self, "Erro", f"Falha ao enviar requisição:\n{e}")

        run_in_thread(_do_send, _on_sent, _on_error)

    def _substitute_placeholders(self, template: str, row: tuple) -> str:
        result = template
        for placeholder, col_idx in PLACEHOLDER_MAP.items():
            if col_idx < len(row) and row[col_idx] is not None:
                val = str(row[col_idx])
                result = result.replace("{" + placeholder + "}", val)
        return result

    def _serialize_value(self, v):
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        if isinstance(v, (datetime, date)):
            if isinstance(v, date) and not isinstance(v, datetime):
                return v.isoformat()
            return v.isoformat()
        try:
            json.dumps(v)
            return v
        except (TypeError, ValueError):
            return str(v)

    def _serialize_row(self, row: tuple) -> list:
        return [self._serialize_value(v) for v in row]

    # ================== FORMAT HELPERS ==================

    def _format_date(self, raw) -> str:
        if raw is None:
            return "-"
        try:
            if isinstance(raw, datetime):
                return raw.strftime("%d/%m/%Y")
            d = str(raw)[:10]
            parts = d.split("-")
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
            return d
        except Exception:
            return str(raw)[:10]

    def _format_valor(self, raw) -> str:
        if raw is None:
            return "R$ 0,00"
        try:
            v = float(raw)
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return str(raw)

    # ================== REFRESH ==================

    def refresh(self):
        self._load_configured_set()
        self._refresh_template_combo()
        self._refresh_clientes_tab()
