import json
import os
import httpx
import uuid
import concurrent.futures
from datetime import datetime, date, timedelta
from PySide6.QtCore import Qt, QDate, QTimer, QDateTime, QSize, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QTextEdit, QLineEdit, QTabWidget,
    QDialog, QDateTimeEdit, QDialogButtonBox, QRadioButton,
    QAbstractItemView, QApplication, QMessageBox,
)
from PySide6.QtGui import QIcon, QPixmap, QImage


class _FilterPopup(QDialog):
    def __init__(self, all_items: list[tuple[str, str]], selected: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            _FilterPopup { background: #1e1e2e; border: 1px solid #3a3a4a; border-radius: 8px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self._checkboxes = {}
        for text, data in all_items:
            if data == "":
                continue
            cb = QCheckBox(text)
            cb.setChecked(data in (selected or set()))
            cb.setStyleSheet("""
                QCheckBox { color: #c0c0d0; font-size: 12px; padding: 4px 8px; }
                QCheckBox:hover { background: rgba(79,172,254,0.15); border-radius: 4px; }
                QCheckBox::indicator { width: 14px; height: 14px; }
            """)
            self._checkboxes[data] = cb
            layout.addWidget(cb)

        btn_limpar = QPushButton("Limpar filtro")
        btn_limpar.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #3a3a4a;
                border-radius: 4px; padding: 4px 12px; color: #e06c75;
                font-size: 11px; margin-top: 6px; }
            QPushButton:hover { background: rgba(224,108,117,0.15); }
        """)
        btn_limpar.clicked.connect(self._limpar)
        layout.addWidget(btn_limpar)

    def _limpar(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)
        self.accept()

    def get_selected(self) -> list[str]:
        return [data for data, cb in self._checkboxes.items() if cb.isChecked()]


from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_confirm, show_error, show_success
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb
from frontend.app.core.theme import theme_manager, _hex_to_rgb
from frontend.app.services.barcode import calcular_codigo_barras, calcular_linha_digitavel


COBRANCA_SQL = """
SELECT {paginacao}
       Par.Empresa,
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
       0                                                    AS Atrazo,
       Doc.Emissao,
       Par.Vencimento,
       Par.Valor,
       (Par.Valor - Par.ValorPendente)                     AS CapitalRecebido,
       Par.ValorPendente,
       0                                                    AS Multa,
       COALESCE(NULLIF(Cli.JurosAtraso, 0), 0)             AS Juros,
       ''                                                   AS TipoJuro,
       Par.IDTRECPARCELA,
       Par.PORTADOR,
       Par.PARCELA                                          AS Parcela,
       ''                                                   AS NossoNumero,
       ''                                                   AS NumeroBoleto,
       Par.UltimoRecebimento
  FROM TRecParcela Par
 INNER JOIN TRecDocumento Doc
    ON Doc.Empresa   = Par.Empresa
   AND Doc.Cliente   = Par.Cliente
   AND Doc.Tipo      = Par.Tipo
   AND Doc.Documento = Par.Documento
 INNER JOIN TRecTipoDocumento Tpd
    ON Tpd.Codigo    = Par.Tipo
   AND COALESCE(Tpd.Cartao, 'N') = 'N'
 INNER JOIN TRecCliente Cli
    ON Cli.Empresa   = Par.Empresa
   AND Cli.Codigo    = Par.Cliente
 INNER JOIN TRecClienteGeral Clg
    ON Clg.Codigo    = Cli.Codigo
 INNER JOIN TGerEmpresa Emp
    ON Emp.Codigo    = Par.Empresa
 WHERE Par.Empresa          = ?
   AND Par.Vencimento BETWEEN ? AND ?
   AND Par.ValorPendente    > 0
   AND Par.IdRenegociacao  IS NULL
   AND Par.Situacao        <> 'A'
   {tipo_filter}
 ORDER BY Par.Vencimento DESC
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
    ("valor_juros",         "{valor_juros}", 30, "ValorJuros (calc)","Juros calculado sobre atraso (R$)"),
    ("valor_multa",         "{valor_multa}", 31, "ValorMulta (calc)","Multa calculada sobre pendente (R$)"),
    ("codigo_barras",       "{codigo_barras}", 999, "Calculado", "Código de barras de 44 dígitos (calculado automaticamente)"),
    ("linha_digitavel",     "{linha_digitavel}", 999, "Calculado", "Linha digitável de 47 dígitos (calculada a partir do código de barras)"),
    ("numero_boleto / num_boleto", "{numero_boleto}", 28, "NumeroBoleto", "Número do boleto"),
    ("nosso_numero",        "{nosso_numero}", 27, "NossoNumero", "Nosso número (registro no banco)"),
    ("portador",            "{portador}",   25, "Portador",        "Código do portador/carteira"),
    ("parcela",             "{parcela}",    26, "Parcela",         "Número da parcela"),
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
PLACEHOLDER_MAP["num_boleto"] = 28

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
        self._bank_config_cache = None

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

    def _get_tab_style(self) -> str:
        t = theme_manager.current()
        return f"""
QTabWidget::pane {{
    background: transparent; border: none;
}}
QTabBar::tab {{
    background: transparent; color: {t.text_secondary};
    padding: 8px 20px; font-size: 13px; font-weight: 600;
    border: none; border-bottom: 2px solid transparent;
    margin: 0 2px;
}}
QTabBar::tab:selected {{
    color: {t.text}; border-bottom: 2px solid {t.primary};
}}
QTabBar::tab:hover {{
    color: {t.text};
}}
"""

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self._get_tab_style())
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_cobranca_tab(), "Cobrança em Lote")
        self.tabs.addTab(self._build_clientes_tab(), "Clientes Agendados")
        self.tabs.addTab(self._build_history_tab(), "Histórico de Envios")
        self.tabs.addTab(self._build_template_tab(), "Criar Template")

    # ================== COBRANCA TAB ==================

    def _build_cobranca_tab(self) -> QWidget:
        t = theme_manager.current()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {t.bg}; border: none; }}")

        container = QWidget()
        container.setStyleSheet(f"background: {t.bg};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Filters ──
        filter_card = QFrame()
        filter_card.setStyleSheet(f"""
            QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}
        """)
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(20, 16, 20, 16)
        filter_layout.setSpacing(12)

        filter_title = QLabel("FILTROS")
        filter_title.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px;")
        filter_layout.addWidget(filter_title)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        date_row.addWidget(QLabel("Vencimento inicial:"))
        self.dt_ini = QDateEdit()
        self.dt_ini.setCalendarPopup(True)
        self.dt_ini.setDate(QDate.currentDate().addMonths(-1))
        self.dt_ini.setStyleSheet(f"background: {t.bg}; border: 1px solid {t.border}; border-radius: 4px; padding: 6px; color: {t.text};")
        date_row.addWidget(self.dt_ini)
        date_row.addWidget(QLabel("Vencimento final:"))
        self.dt_fim = QDateEdit()
        self.dt_fim.setCalendarPopup(True)
        self.dt_fim.setDate(QDate.currentDate())
        self.dt_fim.setStyleSheet(self.dt_ini.styleSheet())
        date_row.addWidget(self.dt_fim)
        self.btn_12m = QPushButton("12 meses")
        self.btn_12m.setCursor(Qt.PointingHandCursor)
        self.btn_12m.setStyleSheet(f"""
            QPushButton {{ background: {t.surface}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px 12px; color: {t.primary};
                font-size: 11px; font-weight: 600; }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(t.primary)},0.15); }}
        """)
        self.btn_12m.clicked.connect(lambda: (
            self.dt_ini.setDate(QDate.currentDate().addYears(-1)),
            self.dt_fim.setDate(QDate.currentDate()),
        ))
        date_row.addWidget(self.btn_12m)
        date_row.addStretch()
        filter_layout.addLayout(date_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_row.addWidget(QLabel("Cliente:"))
        self.txt_nome_cliente = QLineEdit()
        self.txt_nome_cliente.setPlaceholderText("Digite parte do nome para filtrar...")
        self.txt_nome_cliente.setStyleSheet(f"""
            QLineEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text};
                font-size: 12px; }}
            QLineEdit:focus {{ border-color: {t.primary}; }}
        """)
        self.txt_nome_cliente.returnPressed.connect(self._filtrar)
        name_row.addWidget(self.txt_nome_cliente, 1)
        filter_layout.addLayout(name_row)

        tipo_row = QHBoxLayout()
        tipo_row.setSpacing(12)

        btn_style = f"""
            QPushButton {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text};
                font-size: 12px; text-align: left; }}
            QPushButton:hover {{ border-color: {t.primary}; }}
        """

        self._tipo_pessoa_selected = set()
        self._tipo_cliente_selected = set()

        def _show_popup(btn, all_items, store_attr):
            popup = _FilterPopup(all_items, selected=getattr(self, store_attr))
            pos = btn.mapToGlobal(QPoint(0, btn.height()))
            popup.setGeometry(pos.x(), pos.y(), 220, min(40 * len(all_items) + 20, 400))

            def _on_close(result):
                selected = popup.get_selected()
                getattr(self, store_attr).clear()
                getattr(self, store_attr).update(selected)
                btn.setText(f"{len(selected)} selecionado(s)" if selected else "Todos")

            popup.finished.connect(_on_close)
            popup.show()

        tipo_row.addWidget(QLabel("Tipo Pessoa:"))
        self.btn_tipopessoa = QPushButton("Todos")
        self.btn_tipopessoa.setCursor(Qt.PointingHandCursor)
        self.btn_tipopessoa.setMinimumWidth(140)
        self.btn_tipopessoa.setStyleSheet(btn_style)
        self.btn_tipopessoa.clicked.connect(
            lambda: _show_popup(
                self.btn_tipopessoa,
                [("Pessoa Física (F)", "F"), ("Pessoa Jurídica (J)", "J"), ("Produtor Rural (P)", "P")],
                "_tipo_pessoa_selected",
            )
        )
        tipo_row.addWidget(self.btn_tipopessoa)

        tipo_row.addWidget(QLabel("Tipo Cliente:"))
        self.btn_tipocliente = QPushButton("Todos")
        self.btn_tipocliente.setCursor(Qt.PointingHandCursor)
        self.btn_tipocliente.setMinimumWidth(200)
        self.btn_tipocliente.setStyleSheet(btn_style)
        tipo_cliente_items = self._load_tipo_cliente_options()
        self.btn_tipocliente.clicked.connect(
            lambda: _show_popup(
                self.btn_tipocliente, tipo_cliente_items, "_tipo_cliente_selected",
            )
        )
        tipo_row.addWidget(self.btn_tipocliente)

        tipo_row.addStretch()
        filter_layout.addLayout(tipo_row)

        self.btn_filtrar = QPushButton("Filtrar")
        self.btn_filtrar.setCursor(Qt.PointingHandCursor)
        self.btn_filtrar.setStyleSheet(f"""
            QPushButton {{ background: {t.primary}; color: {t.selection_text}; border: none;
                border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: {t.primary_hover}; }}
        """)
        self.btn_filtrar.clicked.connect(self._filtrar)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_filtrar)
        filter_layout.addLayout(btn_row)

        # Pagination row
        page_row = QHBoxLayout()
        self.lbl_loading = QLabel("Nenhum")
        self.lbl_loading.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; font-weight: 600;")
        page_row.addWidget(self.lbl_loading)

        self.lbl_configured_hidden = QLabel("0 clientes agendados")
        self.lbl_configured_hidden.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")
        self.lbl_configured_hidden.setCursor(Qt.PointingHandCursor)
        self.lbl_configured_hidden.mousePressEvent = lambda e: self._show_hidden_clients_dialog()
        page_row.addWidget(self.lbl_configured_hidden)

        page_row.addStretch()

        self.btn_prev = QPushButton("< Anterior")
        self.btn_prev.setEnabled(False)
        self.btn_prev.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 4px; color: {t.text}; padding: 6px 16px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
            QPushButton:disabled {{ color: {t.text_muted}; }}
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
        results_label.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px;")
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
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background-color: rgba({_hex_to_rgb(t.primary)},0.3); }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 8px; font-weight: 600; font-size: 11px; }}
        """)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)
        self.table.itemChanged.connect(self._on_check_changed)

        # ── Selected + Actions ──
        actions_card = QFrame()
        actions_card.setStyleSheet(f"QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(20, 16, 20, 16)
        actions_layout.setSpacing(10)

        sel_header = QHBoxLayout()
        sel_title = QLabel("SELECIONADOS PARA ENVIO")
        sel_title.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 700; letter-spacing: 0.5px;")
        sel_header.addWidget(sel_title)
        self.lbl_selected_count = QLabel("0 clientes")
        self.lbl_selected_count.setStyleSheet(f"font-size: 12px; color: {t.accent_blue}; font-weight: 600;")
        sel_header.addWidget(self.lbl_selected_count)
        sel_header.addStretch()
        actions_layout.addLayout(sel_header)

        # ── Ver Pendencias ──
        boletos_row = QHBoxLayout()
        boletos_row.setSpacing(8)
        self.btn_ver_boletos = QPushButton("Ver Pendências")
        self.btn_ver_boletos.setCursor(Qt.PointingHandCursor)
        self.btn_ver_boletos.setStyleSheet(f"""
            QPushButton {{ background: {t.accent_blue}; color: {t.selection_text}; border: none;
                border-radius: 6px; padding: 8px 20px;
                font-size: 12px; font-weight: 700; }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(t.accent_blue)},0.8); }}
            QPushButton:disabled {{ background: {t.surface_elevated}; color: {t.text_muted}; }}
        """)
        self.btn_ver_boletos.clicked.connect(self._open_boletos_dialog)
        boletos_row.addWidget(self.btn_ver_boletos)
        boletos_row.addStretch()
        actions_layout.addLayout(boletos_row)

        template_row = QHBoxLayout()
        template_row.setSpacing(8)
        template_row.addWidget(QLabel("Template:"))
        self.cmb_template = QComboBox()
        self.cmb_template.setMinimumWidth(250)
        self.cmb_template.setStyleSheet(f"""
            QComboBox {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        template_row.addWidget(self.cmb_template)
        template_row.addStretch()

        btn_visualizar = QPushButton("Visualizar")
        btn_visualizar.setCursor(Qt.PointingHandCursor)
        btn_visualizar.setStyleSheet(f"""
            QPushButton {{ background: {t.primary}; color: {t.selection_text}; border: none;
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: {t.primary_hover}; }}
        """)
        btn_visualizar.clicked.connect(self._open_preview_dialog)
        template_row.addWidget(btn_visualizar)

        calc_svg_data = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="8" y2="10.01"/><line x1="12" y1="10" x2="12" y2="10.01"/><line x1="16" y1="10" x2="16" y2="10.01"/><line x1="8" y1="14" x2="8" y2="14.01"/><line x1="12" y1="14" x2="12" y2="14.01"/><line x1="16" y1="14" x2="16" y2="14.01"/><line x1="8" y1="18" x2="16" y2="18"/></svg>"""
        _calc_img = QImage.fromData(calc_svg_data.encode(), "SVG")
        calc_icon = QIcon(QPixmap.fromImage(_calc_img))
        self.btn_calculadora = QPushButton(calc_icon, "")
        self.btn_calculadora.setToolTip("Calculadora")
        self.btn_calculadora.setCursor(Qt.PointingHandCursor)
        self.btn_calculadora.setIconSize(QSize(20, 20))
        self.btn_calculadora.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {t.border};
                border-radius: 6px; padding: 8px 10px; min-width: 40px; }}
            QPushButton:hover {{ background: {t.surface_elevated}; }}
        """)
        self.btn_calculadora.clicked.connect(self._open_calculadora)
        template_row.addWidget(self.btn_calculadora)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {t.danger};
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; color: {t.danger}; }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(t.danger)},0.1); }}
        """)
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar_selecao)
        template_row.addWidget(self.btn_cancelar)

        self.btn_agendar = QPushButton("Agendar")
        self.btn_agendar.setCursor(Qt.PointingHandCursor)
        self.btn_agendar.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {t.warning};
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; color: {t.warning}; }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(t.warning)},0.1); }}
            QPushButton:disabled {{ border-color: {t.border}; color: {t.text_muted}; }}
        """)
        self.btn_agendar.setEnabled(False)
        self.btn_agendar.clicked.connect(self._agendar)
        template_row.addWidget(self.btn_agendar)

        self.btn_enviar = QPushButton("Enviar Agora")
        self.btn_enviar.setCursor(Qt.PointingHandCursor)
        self.btn_enviar.setStyleSheet(f"""
            QPushButton {{ background: {t.success}; color: {t.selection_text}; border: none;
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: {t.success_hover}; }}
            QPushButton:disabled {{ background: {t.surface_elevated}; color: {t.text_muted}; }}
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
        t = theme_manager.current()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Clientes Agendados")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.text};")
        header.addWidget(title)
        header.addStretch()

        btn_refresh_jobs = QPushButton("Atualizar")
        btn_refresh_jobs.setCursor(Qt.PointingHandCursor)
        btn_refresh_jobs.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 16px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_refresh_jobs.clicked.connect(self._refresh_clientes_tab)
        header.addWidget(btn_refresh_jobs)
        layout.addLayout(header)

        filter_card = QFrame()
        filter_card.setStyleSheet(f"""
            QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}
        """)
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.job_search_input = QLineEdit()
        self.job_search_input.setPlaceholderText("Buscar por nome, template ou tag...")
        self.job_search_input.setStyleSheet(f"""
            QLineEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        search_row.addWidget(self.job_search_input, 1)

        search_row.addWidget(QLabel("Data início:"))
        self.job_filter_dt_ini = QDateEdit()
        self.job_filter_dt_ini.setCalendarPopup(True)
        self.job_filter_dt_ini.setDate(QDate.currentDate().addMonths(-1))
        self.job_filter_dt_ini.setSpecialValueText(" ")
        self.job_filter_dt_ini.setStyleSheet(f"""
            QDateEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 4px; color: {t.text}; font-size: 12px; }}
        """)
        search_row.addWidget(self.job_filter_dt_ini)

        search_row.addWidget(QLabel("Data fim:"))
        self.job_filter_dt_fim = QDateEdit()
        self.job_filter_dt_fim.setCalendarPopup(True)
        self.job_filter_dt_fim.setDate(QDate.currentDate())
        self.job_filter_dt_fim.setSpecialValueText(" ")
        self.job_filter_dt_fim.setStyleSheet(self.job_filter_dt_ini.styleSheet())
        search_row.addWidget(self.job_filter_dt_fim)

        btn_filter_jobs = QPushButton("Filtrar")
        btn_filter_jobs.setCursor(Qt.PointingHandCursor)
        btn_filter_jobs.setStyleSheet(f"""
            QPushButton {{ background: {t.primary}; color: {t.selection_text}; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; font-weight: 700; }}
            QPushButton:hover {{ background: {t.primary_hover}; }}
        """)
        btn_filter_jobs.clicked.connect(self._refresh_clientes_tab)
        search_row.addWidget(btn_filter_jobs)

        btn_clear_filters = QPushButton("Limpar")
        btn_clear_filters.setCursor(Qt.PointingHandCursor)
        btn_clear_filters.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {t.border};
                border-radius: 4px; color: {t.text}; padding: 6px 12px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_clear_filters.clicked.connect(self._clear_job_filters)
        search_row.addWidget(btn_clear_filters)

        filter_layout.addLayout(search_row)
        layout.addWidget(filter_card)

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
        self.jobs_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
            QTableWidget::item {{ padding: 6px; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 8px; font-weight: 600; font-size: 11px; }}
        """)
        self.jobs_table.setSortingEnabled(True)
        layout.addWidget(self.jobs_table, 1)

        self._refresh_clientes_tab()
        return container

    def _clear_job_filters(self):
        self.job_search_input.clear()
        self.job_filter_dt_ini.setDate(QDate.currentDate().addMonths(-1))
        self.job_filter_dt_fim.setDate(QDate.currentDate())
        self._refresh_clientes_tab()

    def _refresh_clientes_tab(self):
        t = theme_manager.current()
        all_jobs = self._load_jobs()

        all_jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

        search_text = self.job_search_input.text().strip().lower() if hasattr(self, 'job_search_input') else ""
        dt_ini_str = self.job_filter_dt_ini.date().toString("yyyy-MM-dd") if hasattr(self, 'job_filter_dt_ini') else ""
        dt_fim_str = self.job_filter_dt_fim.date().toString("yyyy-MM-dd") if hasattr(self, 'job_filter_dt_fim') else ""
        if dt_ini_str and dt_fim_str:
            from datetime import date as _jd
            if (_jd.fromisoformat(dt_fim_str) - _jd.fromisoformat(dt_ini_str)).days > 365*3:
                show_error(self, "Limite excedido", "O período entre as datas não pode ultrapassar 3 anos.")
                return

        jobs = []
        for j in all_jobs:
            if search_text:
                name = j.get("name", "").lower()
                template = j.get("template_name", "").lower()
                tag = j.get("tag", "").lower()
                if search_text not in name and search_text not in template and search_text not in tag:
                    continue
            sched = j.get("scheduled_for", "")
            if sched and dt_ini_str and dt_fim_str:
                try:
                    dt_val_str = datetime.fromisoformat(sched).date().isoformat()
                    if dt_val_str < dt_ini_str or dt_val_str > dt_fim_str:
                        continue
                except Exception:
                    pass
            jobs.append(j)

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
            repeat = j.get("repeat", {})
            if repeat and repeat.get("type") and repeat["type"] != "none":
                labels = {
                    "hourly": f"a cada {repeat.get('interval', 1)}h",
                    "daily": "diário",
                    "weekly": "semanal",
                    "monthly": "mensal",
                }
                lbl = labels.get(repeat["type"], "")
                if lbl:
                    sched += f" ({lbl})" if sched else lbl
            self.jobs_table.setItem(row, 4, QTableWidgetItem(sched))
            status = j.get("status", "pending")
            status_item = QTableWidgetItem(status.upper())
            if status == "pending":
                status_item.setForeground(QColor(t.warning))
            elif status in ("sent",):
                status_item.setForeground(QColor(t.success))
            elif status in ("partial",):
                status_item.setForeground(QColor(t.warning))
            elif status == "error":
                status_item.setForeground(QColor(t.danger))
            self.jobs_table.setItem(row, 5, status_item)

            btn_ver = QPushButton("Ver")
            btn_ver.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: 1px solid {t.accent_blue};
                    border-radius: 3px; color: {t.accent_blue}; padding: 2px 8px;
                    font-size: 10px; font-weight: 600; }}
                QPushButton:hover {{ background: rgba({_hex_to_rgb(t.accent_blue)},0.1); }}
            """)
            btn_ver.clicked.connect(lambda checked, jid=j["id"]: self._show_job_clients_dialog(jid))

            if status == "pending":
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(4, 2, 4, 2)
                actions_layout.setSpacing(4)
                actions_layout.addWidget(btn_ver)

                btn_cancel = QPushButton("Cancelar")
                btn_cancel.setStyleSheet(f"""
                    QPushButton {{ background: transparent; border: 1px solid {t.danger};
                        border-radius: 3px; color: {t.danger}; padding: 2px 8px;
                        font-size: 10px; font-weight: 600; }}
                    QPushButton:hover {{ background: rgba({_hex_to_rgb(t.danger)},0.1); }}
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
                actions_layout.setContentsMargins(4, 2, 4, 2)
                actions_layout.setSpacing(4)
                actions_layout.addWidget(btn_ver)

                lbl_result = QLabel(result_text)
                lbl_result.setStyleSheet(f"font-size: 10px; color: {t.text_secondary};")
                actions_layout.addWidget(lbl_result)
                self.jobs_table.setCellWidget(row, 6, actions_widget)

        self.jobs_table.setRowCount(len(jobs))

    def _show_job_clients_dialog(self, job_id: str):
        t = theme_manager.current()
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
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
            QLabel {{ color: {t.text}; font-size: 13px; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"{job.get('name', '')} — {len(job.get('clients', []))} cliente(s)")
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {t.text};")
        layout.addWidget(title)

        info = QLabel(f"Template: {job.get('template_name', '')} · Tag: {job.get('tag', '-')} · Status: {job.get('status', 'pending').upper()}")
        info.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")
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
        table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 6px; font-weight: 600; font-size: 11px; }}
        """)
        table.setSortingEnabled(True)

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
        btn_fechar.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_fechar.clicked.connect(dlg.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_fechar)
        layout.addLayout(btn_layout)

        dlg.exec()

    # ================== HISTORY TAB ==================

    def _build_history_tab(self) -> QWidget:
        t = theme_manager.current()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Histórico de Envios")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.text};")
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 16px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_refresh.clicked.connect(self._refresh_history_tab)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "Data/Hora", "Cliente", "Telefone", "Template", "Tag", "Status", "Método", "Ações"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.history_table.horizontalHeader().resizeSection(7, 100)
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.setSortingEnabled(True)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(36)
        self.history_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
            QTableWidget::item {{ padding: 6px; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 8px; font-weight: 600; font-size: 11px; }}
        """)
        layout.addWidget(self.history_table, 1)

        self._refresh_history_tab()
        return container

    def _refresh_history_tab(self):
        t = theme_manager.current()
        history = self._load_sent_history()
        history.reverse()
        self.history_table.setRowCount(0)

        for entry in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            sent_at = entry.get("sent_at", "")
            try:
                dt = datetime.fromisoformat(sent_at)
                sent_at = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
            self.history_table.setItem(row, 0, QTableWidgetItem(sent_at))
            self.history_table.setItem(row, 1, QTableWidgetItem(entry.get("client_name", "-")))
            self.history_table.setItem(row, 2, QTableWidgetItem(entry.get("phone", "-")))
            self.history_table.setItem(row, 3, QTableWidgetItem(entry.get("template_name", "-")))
            self.history_table.setItem(row, 4, QTableWidgetItem(entry.get("tag", "-")))

            success = entry.get("success", True)
            status_item = QTableWidgetItem("Sucesso" if success else "Falha")
            status_item.setForeground(QColor(t.success) if success else QColor(t.danger))
            self.history_table.setItem(row, 5, status_item)
            self.history_table.setItem(row, 6, QTableWidgetItem(entry.get("method", "-")))

            btn_ver = QPushButton("Visualizar")
            btn_ver.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: 1px solid {t.accent_blue};
                    border-radius: 3px; color: {t.accent_blue}; padding: 2px 8px;
                    font-size: 10px; font-weight: 600; }}
                QPushButton:hover {{ background: rgba({_hex_to_rgb(t.accent_blue)},0.1); }}
            """)
            btn_ver.clicked.connect(lambda checked, e=entry: self._show_history_detail(e))
            self.history_table.setCellWidget(row, 7, btn_ver)

        self.history_table.setRowCount(len(history))

    def _show_history_detail(self, entry: dict):
        t = theme_manager.current()
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFrame

        dlg = QDialog(self)
        dlg.setWindowTitle("Detalhes do Envio")
        dlg.resize(560, 520)
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Detalhes do Envio")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {t.text};")
        layout.addWidget(title)

        info_card = QFrame()
        info_card.setStyleSheet(f"""
            QFrame {{ background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 6px; }}
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(6)

        sent_at = entry.get("sent_at", "")
        try:
            dt = datetime.fromisoformat(sent_at)
            sent_at = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass

        success = entry.get("success", True)
        status_text = "✅ Sucesso" if success else "❌ Falha"
        status_color = t.success if success else t.danger

        fields = [
            ("📅 Data/Hora:", sent_at),
            ("👤 Cliente:", entry.get("client_name", "-")),
            ("📱 Telefone:", entry.get("phone", "-")),
            ("📋 Template:", entry.get("template_name", "-")),
            ("🏷️  Tag:", entry.get("tag", "-")),
            ("🔗 URL:", entry.get("url", "-")),
            ("⚙️  Método:", entry.get("method", "-")),
            ("📊 Status HTTP:", str(entry.get("status_code", "-"))),
            ("📌 Resultado:", status_text),
        ]

        for label, value in fields:
            row_w = QWidget()
            row_w.setStyleSheet("border: none; background: transparent;")
            row_layout = QHBoxLayout(row_w)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {t.text_secondary}; border: none; background: transparent;")
            row_layout.addWidget(lbl)

            val = QLabel(value)
            if label.startswith("📌"):
                val.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {status_color}; border: none; background: transparent;")
            else:
                val.setStyleSheet(f"font-size: 12px; color: {t.text}; border: none; background: transparent;")
            val.setWordWrap(True)
            row_layout.addWidget(val, 1)
            info_layout.addWidget(row_w)

        layout.addWidget(info_card)

        body = entry.get("body", "")
        if body:
            body_label = QLabel("Mensagem enviada:")
            body_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {t.text_secondary};")
            layout.addWidget(body_label)

            body_edit = QTextEdit()
            body_edit.setReadOnly(True)
            body_edit.setPlainText(body)
            body_edit.setMinimumHeight(100)
            body_edit.setMaximumHeight(200)
            body_edit.setStyleSheet(f"""
                QTextEdit {{ background: {t.bg}; border: 1px solid {t.border};
                    border-radius: 4px; padding: 8px; color: {t.text};
                    font-size: 11px; font-family: Consolas, monospace; }}
            """)
            layout.addWidget(body_edit)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_fechar.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

        dlg.exec()

    # ================== TEMPLATE TAB ==================

    def _build_template_tab(self) -> QWidget:
        t = theme_manager.current()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {t.bg}; border: none; }}")

        container = QWidget()
        container.setStyleSheet(f"background: {t.bg};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Criar Template")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.text};")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Template name + load/save/delete
        manage_row = QHBoxLayout()
        manage_row.setSpacing(8)
        manage_row.addWidget(QLabel("Template:"))
        self.cmb_saved_templates = QComboBox()
        self.cmb_saved_templates.setMinimumWidth(250)
        self.cmb_saved_templates.setStyleSheet(f"""
            QComboBox {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        self.cmb_saved_templates.currentIndexChanged.connect(self._load_selected_template)
        manage_row.addWidget(self.cmb_saved_templates)

        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Nome do template...")
        self.template_name_input.setStyleSheet(f"""
            QLineEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        manage_row.addWidget(self.template_name_input, 1)

        btn_save_template = QPushButton("Salvar")
        btn_save_template.setStyleSheet(f"""
            QPushButton {{ background: {t.success}; color: {t.selection_text}; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.success_hover}; }}
        """)
        btn_save_template.clicked.connect(self._save_template)
        manage_row.addWidget(btn_save_template)

        btn_delete_template = QPushButton("Excluir")
        btn_delete_template.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {t.danger};
                border-radius: 4px; color: {t.danger}; padding: 6px 16px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(t.danger)},0.1); }}
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
        self.tmpl_tag.setStyleSheet(f"""
            QLineEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
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
        self.tmpl_method.setStyleSheet(f"""
            QComboBox {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        url_row.addWidget(self.tmpl_method)
        self.tmpl_url = QLineEdit()
        self.tmpl_url.setPlaceholderText("https://app.mundodosbots.com.br/api/users")
        self.tmpl_url.setStyleSheet(f"""
            QLineEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 6px; color: {t.text}; font-size: 12px; }}
        """)
        url_row.addWidget(self.tmpl_url, 1)
        btn_paste = QPushButton("Colar")
        btn_paste.setFixedWidth(60)
        btn_paste.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 4px; color: {t.text}; padding: 6px;
                font-size: 11px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_paste.clicked.connect(self._import_curl_template)
        url_row.addWidget(btn_paste)
        layout.addLayout(url_row)

        # Headers
        headers_label = QLabel("HEADERS")
        headers_label.setStyleSheet(f"font-size: 10px; color: {t.text_secondary}; font-weight: 600; letter-spacing: 0.5px;")
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
        self.tmpl_headers.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 11px; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 4px; font-weight: 600; font-size: 10px; }}
        """)
        for key, val in DEFAULT_HEADERS:
            self._add_tmpl_header_row(key, val)
        layout.addWidget(self.tmpl_headers)

        btn_add_hdr = QPushButton("+ Adicionar header")
        btn_add_hdr.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px dashed {t.border};
                border-radius: 4px; color: {t.text_secondary}; padding: 6px;
                font-size: 11px; font-weight: 600; }}
            QPushButton:hover {{ border-color: {t.accent_blue}; color: {t.accent_blue}; }}
        """)
        btn_add_hdr.clicked.connect(lambda: self._add_tmpl_header_row())
        layout.addWidget(btn_add_hdr)

        # Body
        body_label = QLabel("BODY TEMPLATE")
        body_label.setStyleSheet(f"font-size: 10px; color: {t.text_secondary}; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(body_label)

        self.tmpl_body = QTextEdit()
        self.tmpl_body.setPlainText(DEFAULT_BODY_TEMPLATE)
        self.tmpl_body.setMinimumHeight(160)
        self.tmpl_body.setMaximumHeight(240)
        self.tmpl_body.setStyleSheet(f"""
            QTextEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 8px; color: {t.text};
                font-size: 11px; font-family: Consolas, monospace; }}
        """)
        layout.addWidget(self.tmpl_body)

        # ── Variable Reference ──
        vars_label = QLabel("VARIÁVEIS DISPONÍVEIS")
        vars_label.setStyleSheet(f"font-size: 10px; color: {t.text_secondary}; font-weight: 600; letter-spacing: 0.5px; margin-top: 8px;")
        layout.addWidget(vars_label)

        vars_container = QFrame()
        vars_container.setStyleSheet(f"""
            QFrame {{ background-color: {t.surface}; border: 1px solid {t.border};
                     border-radius: 6px; }}
        """)
        vars_inner = QVBoxLayout(vars_container)
        vars_inner.setContentsMargins(12, 10, 12, 10)
        vars_inner.setSpacing(6)

        var_desc = QLabel("Use <b>{{placeholder}}</b> no Body Template e Headers. Eles serão substituídos pelos dados de cada cliente.")
        var_desc.setWordWrap(True)
        var_desc.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; border: none;")
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
        var_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.surface_elevated}; gridline-color: {t.surface_elevated};
                font-size: 11px; font-family: Consolas, monospace; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: none; border-bottom: 1px solid {t.border};
                padding: 4px; font-weight: 600; font-size: 10px; }}
            QTableWidget::item {{ padding: 2px 8px; }}
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
            show_error(self, "Erro", f"Não foi possível salvar configuração de intervalo entre disparos:\n{e}")

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

    def _record_sent(self, phone: str, tag: str, client_name: str = "", template_name: str = "", body: str = "", url: str = "", method: str = "", status_code: int = 0, success: bool = True):
        if not tag:
            return
        history = self._load_sent_history()
        history.append({
            "phone": phone,
            "tag": tag,
            "sent_at": datetime.now().isoformat(),
            "client_name": client_name,
            "template_name": template_name,
            "body": body,
            "url": url,
            "method": method,
            "status_code": status_code,
            "success": success,
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
        t = theme_manager.current()
        row = self.tmpl_headers.rowCount()
        self.tmpl_headers.insertRow(row)
        self.tmpl_headers.setItem(row, 0, QTableWidgetItem(key))
        self.tmpl_headers.setItem(row, 1, QTableWidgetItem(val))
        btn_del = QPushButton("×")
        btn_del.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none;
                color: {t.danger}; font-size: 16px; font-weight: 700; }}
            QPushButton:hover {{ color: {t.danger_hover}; }}
        """)
        btn_del.clicked.connect(lambda: self.tmpl_headers.removeRow(row))
        self.tmpl_headers.setCellWidget(row, 2, btn_del)

    def _import_curl_template(self):
        t = theme_manager.current()
        from PySide6.QtWidgets import QDialog as QDlg, QTextEdit as QTE, QVBoxLayout as QVL, QDialogButtonBox as QDB

        dlg = QDlg(self)
        dlg.setWindowTitle("Importar cURL")
        dlg.resize(500, 300)
        dlg.setStyleSheet(f"QDialog {{ background-color: {t.bg}; color: {t.text}; }}")
        lay = QVL(dlg)
        lay.addWidget(QLabel("Cole o comando cURL:"))
        editor = QTE()
        editor.setPlaceholderText("curl -X POST https://api.exemplo.com ...")
        editor.setStyleSheet(f"background: {t.bg}; color: {t.text}; border: 1px solid {t.border};")
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

    def _agendar(self):
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
            "repeat": schedule.get("repeat", {"type": "none"}),
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
                        success = resp.status_code < 300
                        if success:
                            results["success"] += 1
                        else:
                            results["errors"] += 1
                        client_name = str(c[3]) if len(c) > 3 and c[3] else ""
                        self._record_sent(phone, job_tag,
                            client_name=client_name,
                            template_name=job.get("template_name", ""),
                            body=body,
                            url=url,
                            method=method,
                            status_code=resp.status_code,
                            success=success)
                    except Exception:
                        results["errors"] += 1
            return results, job["id"]

        def _on_done(results_and_id):
            results, job_id = results_and_id
            jobs = self._load_jobs()
            for j in jobs:
                if j["id"] == job_id:
                    repeat = j.get("repeat", {})
                    if repeat and repeat.get("type") and repeat["type"] != "none":
                        next_run = self._compute_next_run(
                            datetime.fromisoformat(j["scheduled_for"]),
                            repeat
                        )
                        if next_run:
                            j["scheduled_for"] = next_run.isoformat()
                            j["status"] = "pending"
                            j["result"] = results
                        else:
                            j["status"] = "sent"
                            j["result"] = results
                    else:
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

    def _compute_next_run(self, scheduled_for: datetime, repeat: dict) -> datetime | None:
        t = repeat.get("type", "none")
        if t == "hourly":
            return scheduled_for + timedelta(hours=repeat.get("interval", 1))
        elif t == "daily":
            return scheduled_for + timedelta(days=1)
        elif t == "weekly":
            days = repeat.get("days", [])
            if not days:
                return scheduled_for + timedelta(days=7)
            current_weekday = scheduled_for.weekday()
            for d in sorted(days):
                if d > current_weekday:
                    return scheduled_for + timedelta(days=d - current_weekday)
            return scheduled_for + timedelta(days=(7 - current_weekday + days[0]))
        elif t == "monthly":
            return scheduled_for + timedelta(days=30)
        return None

    # ================== FILTER / PAGINATION ==================

    def _filtrar(self, keep_page: bool = False):
        t = theme_manager.current()
        if not keep_page:
            self._page = 0

        data_ini = self.dt_ini.date().toString("yyyy-MM-dd")
        data_fim = self.dt_fim.date().toString("yyyy-MM-dd")
        from datetime import date as _date
        qdi = _date.fromisoformat(data_ini)
        qdf = _date.fromisoformat(data_fim)
        if (qdf - qdi).days > 365*3:
            show_error(self, "Limite excedido", "O período entre as datas não pode ultrapassar 3 anos.")
            self.btn_filtrar.setEnabled(True)
            self.btn_filtrar.setText("Filtrar")
            return
        empresa = self.user.get("eco_empresa", "01")

        filtros = []
        nome_cliente = self.txt_nome_cliente.text().strip()
        if nome_cliente:
            logger.info("QUERY", f"Filtro nome: {nome_cliente!r} (>=3 caracteres: {len(nome_cliente) >= 3})")
        if nome_cliente:
            safe = nome_cliente.replace(chr(39), chr(39)+chr(39))
            if len(nome_cliente) >= 3:
                filtros.append(f"AND Clg.Nome STARTING WITH '{safe}'")
            else:
                filtros.append(f"AND Clg.Nome CONTAINING '{safe}'")
        selected_pessoa = list(self._tipo_pessoa_selected)
        if selected_pessoa:
            pess_str = ",".join(f"'{p}'" for p in selected_pessoa)
            filtros.append(f"AND Clg.PESSOA IN ({pess_str})")
        selected_tipos = list(self._tipo_cliente_selected)
        if selected_tipos:
            tipos_str = ",".join(f"'{t}'" for t in selected_tipos)
            filtros.append(f"AND Clg.TIPOCLIENTE IN ({tipos_str})")

        pag_sql = ""
        pag_params: tuple = ()
        if self._page_size > 0:
            pag_sql = "FIRST ? SKIP ?"
            pag_params = (self._page_size, self._page * self._page_size)

        params = pag_params + (empresa, data_ini, data_fim)
        logger.info("QUERY", f"Filtrando: empresa={empresa!r}, datas={data_ini} a {data_fim}, "
                             f"cliente={nome_cliente or '(vazio)'}, "
                             f"pessoa={selected_pessoa}, tipo_cliente={selected_tipos}, "
                             f"rota={self._page}")

        sql = COBRANCA_SQL.format(
            tipo_filter=" ".join(filtros),
            paginacao=pag_sql,
        )

        self.btn_filtrar.setEnabled(False)
        self.btn_filtrar.setText("Filtrando...")
        self.lbl_loading.setText("Carregando...")
        self.table.setRowCount(0)

        def _do_query():
            logger.info("QUERY", f"Iniciando consulta Firebird: empresa={empresa!r}, "
                                 f"datas={data_ini} a {data_fim}, filtros={len(filtros)}")
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
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
                self.lbl_loading.setStyleSheet(f"font-size: 12px; color: {t.success}; font-weight: 600;")

                from datetime import date as _calc_date
                today = _calc_date.today()
                filtered = []
                for r in rows:
                    rl = list(r)
                    venc = rl[17]
                    ult_rec = rl[29]
                    atrazo_val = 0
                    if venc:
                        if ult_rec and venc < ult_rec:
                            atrazo_val = (today - ult_rec).days
                        else:
                            atrazo_val = (today - venc).days
                        rl[15] = max(atrazo_val, 0)
                    pendente = float(rl[20] or 0)
                    multa_val = float(rl[21] or 0)
                    juros_val = float(rl[22] or 0)
                    tipo_juro = str(rl[23] or "")
                    dias_carencia = float(rl[11] or 0)
                    if atrazo_val > dias_carencia and pendente and juros_val:
                        if tipo_juro == 'S':
                            vj = pendente * (juros_val / 100.0) * atrazo_val
                        elif tipo_juro == 'C':
                            vj = pendente * (pow(1 + (juros_val / 100.0), atrazo_val) - 1)
                        else:
                            vj = 0
                    else:
                        vj = 0
                    vm = pendente * (multa_val / 100.0) if pendente else 0
                    rl.append(vj)
                    rl.append(vm)
                    filtered.append(tuple(rl))
                self._hidden_clients_data = []
                hidden_count = 0
                seen_hidden = set()
                for r in rows:
                    key = (str(r[0]), str(r[2]))
                    if key in self._configured_set and key not in seen_hidden:
                        hidden_count += 1
                        self._hidden_clients_data.append(r)
                        seen_hidden.add(key)

                self._results_data = filtered
                self._selected_rows.clear()
                self._update_selected_count()
                self._has_more = len(filtered) >= self._page_size

                self._update_hidden_label(hidden_count)
                self._update_page_info()

                if not filtered:
                    if hidden_count:
                        show_error(self, "Sem Resultados", "Todos os resultados desta página já foram configurados. Avance para a próxima página ou ajuste os filtros.")
                    else:
                        logger.info("QUERY", f"Sem resultados: empresa={empresa!r}, datas={data_ini} a {data_fim}")
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
                self.lbl_loading.setStyleSheet(f"font-size: 12px; color: {t.danger}; font-weight: 600;")
                show_error(self, "Erro", f"Erro ao processar resultados:\n{e}")

        def _on_error(e):
            self.btn_filtrar.setEnabled(True)
            self.btn_filtrar.setText("Filtrar")
            self.lbl_loading.setText("Nenhum")
            self.lbl_loading.setStyleSheet(f"font-size: 12px; color: {t.danger}; font-weight: 600;")
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
        t = theme_manager.current()
        self.lbl_configured_hidden.setText(f"{count} cliente(s) agendado(s)")
        if count > 0:
            self.lbl_configured_hidden.setStyleSheet(f"font-size: 12px; color: {t.accent_blue}; text-decoration: underline;")
        else:
            self.lbl_configured_hidden.setStyleSheet(f"font-size: 12px; color: {t.text_secondary};")

    def _update_page_info(self):
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._has_more)

    def _show_hidden_clients_dialog(self):
        t = theme_manager.current()
        if not self._hidden_clients_data:
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("Clientes Agendados")
        dlg.resize(600, 400)
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
            QLabel {{ color: {t.text}; font-size: 13px; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"Clientes ocultos ({len(self._hidden_clients_data)})")
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {t.text};")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Código", "Nome", "Celular", ""])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.horizontalHeader().resizeSection(3, 120)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setStyleSheet(f"""
            QTableWidget {{ background-color: {t.bg}; color: {t.text};
                border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
            QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                border: 1px solid {t.border}; padding: 6px; font-weight: 600; font-size: 11px; }}
        """)
        table.setSortingEnabled(True)

        for i, r in enumerate(self._hidden_clients_data):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(r[2]) if r[2] is not None else "-"))
            table.setItem(row, 1, QTableWidgetItem(str(r[3]) if r[3] else "-"))
            cel = str(r[5]).strip() if r[5] else "-"
            table.setItem(row, 2, QTableWidgetItem(cel))

            btn_remover = QPushButton("Remover")
            btn_remover.setFixedWidth(70)
            btn_remover.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: 1px solid {t.danger};
                    border-radius: 3px; color: {t.danger}; padding: 1px 4px;
                    font-size: 9px; font-weight: 600; }}
                QPushButton:hover {{ background: rgba({_hex_to_rgb(t.danger)},0.1); }}
            """)
            btn_remover.clicked.connect(lambda checked, idx=i: self._remove_hidden_client(idx, dlg, table))
            table.setCellWidget(row, 3, btn_remover)

        layout.addWidget(table, 1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
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
        name = str(r[3]) if r[3] else "desconhecido"
        if not show_confirm(self, "Remover Cliente Agendado",
                           f"Tem certeza que deseja remover \"{name}\" dos clientes agendados?\n\n"
                           f"Ele voltara a aparecer na listagem e podera receber mensagens novamente."):
            return
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
        t = theme_manager.current()
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
                    env_item.setForeground(QColor(t.success) if ja_enviado else QColor(t.danger))
                    self.table.setItem(row, 7, env_item)

                    if ja_enviado and remaining > 0:
                        resto = f"{remaining:.0f}h restantes"
                        resto_item = QTableWidgetItem(resto)
                        resto_item.setForeground(QColor(t.warning))
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it:
                                parts = _hex_to_rgb(t.warning).split(",")
                                it.setBackground(QColor(int(parts[0]), int(parts[1]), int(parts[2]), 20))
                    elif ja_enviado:
                        resto_item = QTableWidgetItem("Disponível")
                        resto_item.setForeground(QColor(t.success))
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it:
                                parts = _hex_to_rgb(t.success).split(",")
                                it.setBackground(QColor(int(parts[0]), int(parts[1]), int(parts[2]), 20))
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
            self.lbl_loading.setStyleSheet(f"font-size: 12px; color: {t.danger}; font-weight: 600;")
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

    def _update_selected_count(self):
        count = len(self._selected_rows)
        self.lbl_selected_count.setText(f"{count} cliente{'s' if count != 1 else ''}")
        self.btn_enviar.setEnabled(count > 0 and self.cmb_template.currentData() is not None)
        self.btn_agendar.setEnabled(count > 0 and self.cmb_template.currentData() is not None)
        self.btn_cancelar.setEnabled(count > 0)
        self.btn_ver_boletos.setEnabled(count > 0 and self._results_data is not None)

    def _cancelar_selecao(self):
        self._selected_rows.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._update_selected_count()

    # ================== PREVIEW ==================

    def _open_preview_dialog(self):
        template_data = self.cmb_template.currentData()
        if not template_data:
            show_error(self, "Aviso", "Selecione um template para visualizar a prévia.")
            return

        row_idx = self.table.currentRow()
        if row_idx < 0 or row_idx >= len(self._results_data):
            show_error(self, "Aviso", "Selecione um registro na tabela para visualizar.")
            return

        row = self._results_data[row_idx]
        body = template_data.get("body", "")
        substituted = self._substitute_placeholders(body, row)
        t = theme_manager.current()

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Prévia do Envio")
        dlg.resize(580, 480)
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {t.bg}; color: {t.text}; }}
            QTabWidget::pane {{ background: {t.bg}; border: none; }}
            QTabBar::tab {{ background: transparent; color: {t.text_secondary};
                padding: 8px 20px; font-size: 13px; font-weight: 600;
                border: none; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {t.text}; border-bottom: 2px solid {t.primary}; }}
            QTabBar::tab:hover {{ color: {t.text}; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # ── Visual tab ──
        visual_container = QWidget()
        visual_container.setStyleSheet(f"background: {t.bg}; border: none;")
        visual_layout = QVBoxLayout(visual_container)
        visual_layout.setContentsMargins(0, 0, 0, 0)
        visual_layout.setSpacing(0)

        phone = str(row[5]).strip() if row[5] else "-"
        nome = str(row[3]) if row[3] else "-"
        valor = self._format_valor(row[20]) if len(row) > 20 else "-"
        venc = self._format_date(row[17]) if len(row) > 17 else "-"

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{ background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 6px; }}
            QFrame * {{ background: transparent; }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        lbl_phone = QLabel(f"📱  Para:  {phone}")
        lbl_phone.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {t.text}; border: none;")
        card_layout.addWidget(lbl_phone)

        lbl_nome = QLabel(f"👤  Cliente:  {nome}")
        lbl_nome.setStyleSheet(f"font-size: 13px; color: {t.text}; border: none;")
        card_layout.addWidget(lbl_nome)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: transparent; border: none; border-top: 1px solid {t.border};")
        card_layout.addWidget(sep)

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent; border: none;")
        grid = QHBoxLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(self._visual_field("💰 Valor:", valor, t))
        left_col.addWidget(self._visual_field("📅 Vencimento:", venc, t))
        grid.addLayout(left_col)

        if len(row) > 15 and row[15] is not None:
            right_col = QVBoxLayout()
            right_col.setSpacing(6)
            right_col.addWidget(self._visual_field("⏱  Atraso:", f"{row[15]} dia(s)", t))
            if len(row) > 24 and row[24] is not None:
                right_col.addWidget(self._visual_field("📊 Juros:", self._format_valor(row[24]), t))
            grid.addLayout(right_col)

        card_layout.addWidget(grid_w)

        try:
            parsed = json.loads(substituted)
            actions = parsed.get("actions", [])
            fields = [a for a in actions if a.get("action") == "set_field_value"]
            flow = [a for a in actions if a.get("action") == "send_flow"]

            if fields:
                sep2 = QFrame()
                sep2.setFrameShape(QFrame.HLine)
                sep2.setStyleSheet(f"background: transparent; border: none; border-top: 1px solid {t.border};")
                card_layout.addWidget(sep2)

                lbl_f = QLabel("Campos que serão preenchidos:")
                lbl_f.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {t.text_secondary}; border: none; background: transparent;")
                card_layout.addWidget(lbl_f)

                field_labels = {
                    "nome_cliente": "Nome do Cliente",
                    "valor_cobranca": "Valor da Cobrança",
                    "data_vencimento": "Data de Vencimento",
                    "numero_boleto": "Nº do Boleto",
                    "codigo_barras": "Código de Barras",
                    "status_cobranca": "Status da Cobrança",
                }

                for f in fields:
                    fn = f.get("field_name", "")
                    fv = f.get("value", "")
                    label = field_labels.get(fn, fn.replace("_", " ").title())
                    if fn in ("codigo_barras", "linha_digitavel") and fv:
                        row_w = QWidget()
                        row_w.setStyleSheet(f"background: transparent; border: none;")
                        row_lo = QHBoxLayout(row_w)
                        row_lo.setContentsMargins(0, 2, 0, 2)
                        row_lo.setSpacing(4)
                        lbl_f = QLabel(f"• {label}:")
                        lbl_f.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {t.text_secondary}; border: none; background: transparent;")
                        val_f = QLabel(fv)
                        val_f.setStyleSheet(f"font-size: 11px; color: {t.text}; border: none; background: transparent; font-family: Consolas, monospace;")
                        val_f.setTextInteractionFlags(Qt.TextSelectableByMouse)
                        btn_f = QPushButton("📋")
                        btn_f.setToolTip(f"Copiar {label.lower()}")
                        btn_f.setStyleSheet(f"QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border}; border-radius: 4px; color: {t.text}; padding: 2px 8px; font-size: 11px; }} QPushButton:hover {{ background: {t.primary}; color: #fff; }}")
                        btn_f.clicked.connect(lambda _, v=fv: QApplication.clipboard().setText(v))
                        row_lo.addWidget(lbl_f, 0)
                        row_lo.addWidget(val_f, 1)
                        row_lo.addWidget(btn_f, 0)
                        card_layout.addWidget(row_w)
                    else:
                        card_layout.addWidget(self._visual_field(f"• {label}:", fv, t))

            if flow:
                sep3 = QFrame()
                sep3.setFrameShape(QFrame.HLine)
                sep3.setStyleSheet(f"background: transparent; border: none; border-top: 1px solid {t.border};")
                card_layout.addWidget(sep3)

                flow_id = flow[0].get("flow_id", "")
                lbl_flow = QLabel(f"🚀 Fluxo: #{flow_id}")
                lbl_flow.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t.accent_blue}; border: none; background: transparent;")
                card_layout.addWidget(lbl_flow)
        except json.JSONDecodeError:
            pass

        visual_layout.addWidget(card)
        visual_layout.addStretch()
        tabs.addTab(visual_container, "Visual")

        # ── JSON tab ──
        json_edit = QTextEdit()
        json_edit.setReadOnly(True)
        json_edit.setPlainText(substituted)
        json_edit.setStyleSheet(f"""
            QTextEdit {{ background: {t.bg}; border: 1px solid {t.border};
                border-radius: 4px; padding: 8px; color: {t.text};
                font-size: 11px; font-family: Consolas, monospace; }}
        """)
        tabs.addTab(json_edit, "JSON")

        # ── Boleto tab (só se tiver código de barras) ──
        bc_preview = self._calcular_barcode(row)
        ld_preview = calcular_linha_digitavel(bc_preview) if bc_preview else ""

        pdf_caminho = ""
        if bc_preview:
            try:
                id_parcela = row[24]
                from frontend.app.core.firebird_client import FirebirdClient
                fbc = FirebirdClient()
                fbc.conectar()
                r = fbc.query(
                    "SELECT CAMINHOPDF FROM BOLETO_GERADO "
                    "WHERE IDPARCELA = ?",
                    (id_parcela,),
                )
                fbc.fechar()
                if r and r[0][0]:
                    pdf_caminho = r[0][0]
            except Exception:
                pass

        if bc_preview:
            copy_svg_clip = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>"""
            _ci = QImage.fromData(copy_svg_clip.encode(), "SVG")
            _copy_icon = QIcon(QPixmap.fromImage(_ci))

            boleto_container = QWidget()
            boleto_container.setStyleSheet(f"background: {t.bg}; border: none;")
            boleto_layout = QVBoxLayout(boleto_container)
            boleto_layout.setContentsMargins(12, 12, 12, 12)
            boleto_layout.setSpacing(10)

            def _make_copy_row(label: str, valor: str, t_obj) -> QWidget:
                w = QWidget()
                w.setStyleSheet(f"background: {t_obj.surface_elevated}; border: 1px solid {t_obj.border}; border-radius: 6px;")
                lo = QHBoxLayout(w)
                lo.setContentsMargins(12, 10, 12, 10)
                lbl = QLabel(label)
                lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {t_obj.text_secondary}; border: none; background: transparent;")
                val = QLabel(valor)
                val.setStyleSheet(f"font-size: 13px; color: {t_obj.text}; border: none; background: transparent; font-family: Consolas, monospace;")
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
                btn = QPushButton(_copy_icon, "Copiar")
                btn.setIconSize(QSize(14, 14))
                btn.setStyleSheet(f"QPushButton {{ background: {t_obj.primary}; color: #fff; border: none; border-radius: 4px; padding: 6px 14px; font-size: 11px; }} QPushButton:hover {{ opacity: 0.8; }}")
                btn.clicked.connect(lambda _, v=valor: QApplication.clipboard().setText(v))
                lo.addWidget(lbl, 0)
                lo.addWidget(val, 1)
                lo.addWidget(btn, 0)
                return w

            boleto_layout.addWidget(_make_copy_row("C\u00f3digo de Barras", bc_preview, t))
            boleto_layout.addWidget(_make_copy_row("Linha Digit\u00e1vel", ld_preview, t))

            if pdf_caminho:
                import os as _os
                pdf_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>"""
                _pi = QImage.fromData(pdf_svg.encode(), "SVG")
                _pdf_icon = QIcon(QPixmap.fromImage(_pi))
                btn_pdf = QPushButton(_pdf_icon, " Abrir PDF")
                btn_pdf.setIconSize(QSize(18, 18))
                btn_pdf.setCursor(Qt.PointingHandCursor)
                btn_pdf.setStyleSheet(f"""
                    QPushButton {{ background: {t.danger}; color: #fff; border: none;
                        border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 600; }}
                    QPushButton:hover {{ opacity: 0.85; }}
                """)
                btn_pdf.clicked.connect(lambda: _os.startfile(pdf_caminho))
                boleto_layout.addWidget(btn_pdf)

            boleto_layout.addStretch()
            tabs.addTab(boleto_container, "Boleto")

        layout.addWidget(tabs, 1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 20px;
                font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_fechar.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

        dlg.exec()

    def _visual_field(self, label: str, value: str, t) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border: none;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 11px; color: {t.text_secondary}; font-weight: 600; border: none;")
        layout.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(f"font-size: 11px; color: {t.text}; font-weight: 700; border: none;")
        layout.addWidget(val)

        layout.addStretch()
        return w

    # ================== VER BOLETOS ==================

    def _open_boletos_dialog(self):
        if not self._results_data:
            show_error(self, "Aviso", "Nenhum cliente carregado. Faca uma pesquisa primeiro.")
            return

        selected = sorted(self._selected_rows)
        if not selected:
            show_error(self, "Aviso", "Marque um cliente na tabela para ver as pendencias.")
            return

        row_idx = selected[0]
        if row_idx >= len(self._results_data):
            return
        row = self._results_data[row_idx]

        cliente = str(row[2]) if row[2] else None
        empresa = str(row[0]) if row[0] else "01"
        if not cliente:
            show_error(self, "Erro", "Cliente sem codigo.")
            return

        sql = """
        SELECT Par.Documento, Par.Parcela, Par.Vencimento, Par.ValorPendente,
               Par.Valor, Par.Situacao, Cob.NomeCarteira, Tpd.Abreviatura
        FROM TRecParcela Par
        LEFT JOIN TRecTipoDocumento Tpd ON Tpd.Codigo = Par.Tipo
        LEFT JOIN TCOBPARAMETROECOBRANCA Cob
            ON Cob.Empresa = Par.Empresa AND Cob.Portador = Par.PORTADOR
        WHERE Par.Empresa = ? AND Par.Cliente = ?
          AND Par.ValorPendente > 0
          AND Par.IdRenegociacao IS NULL
          AND Par.Situacao <> 'P'
        ORDER BY Par.Vencimento DESC
        """
        t = theme_manager.current()

        def _do_query():
            try:
                return fb.query(sql, (empresa, cliente))
            except Exception as e:
                logger.error("PENDENCIAS", f"Erro: {e}")
                raise

        def _on_result(rows):
            from datetime import date as _dt
            hoje = _dt.today()

            dlg = QDialog(self)
            dlg.setWindowTitle(f"Pendencias do Cliente {cliente}")
            dlg.resize(850, 500)
            dlg.setStyleSheet(f"""
                QDialog {{ background-color: {t.bg}; color: {t.text}; }}
                QTableWidget {{ background-color: {t.bg}; color: {t.text};
                    border: 1px solid {t.border}; gridline-color: {t.surface_elevated}; font-size: 12px; }}
                QTableWidget::item {{ padding: 6px; }}
                QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary};
                    border: 1px solid {t.border}; padding: 8px; font-weight: 600; font-size: 11px; }}
            """)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            if not rows:
                lbl = QLabel("Nenhuma pendencia encontrada para este cliente.")
                lbl.setStyleSheet(f"font-size: 13px; color: {t.text_secondary};")
                layout.addWidget(lbl)
            else:
                table = QTableWidget()
                table.setColumnCount(8)
                table.setHorizontalHeaderLabels([
                    "Documento", "Parcela", "Vencimento", "Valor Pendente",
                    "Valor Total", "Dias", "Status", "Tipo",
                ])
                for c in range(7):
                    table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
                table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
                table.setAlternatingRowColors(True)
                table.setEditTriggers(QTableWidget.NoEditTriggers)
                table.verticalHeader().setVisible(False)
                table.setRowCount(len(rows))

                total_pendente = 0
                for i, r in enumerate(rows):
                    doc = str(r[0] or "") + "/" + str(r[1] or "")
                    table.setItem(i, 0, QTableWidgetItem(doc))
                    table.setItem(i, 1, QTableWidgetItem(str(r[1] or "")))
                    venc = r[2]
                    venc_str = str(venc) if venc else "-"
                    table.setItem(i, 2, QTableWidgetItem(venc_str))
                    pend = r[3]
                    if pend is not None:
                        v = float(pend)
                        total_pendente += v
                        table.setItem(i, 3, QTableWidgetItem(f"R$ {v:.2f}"))
                    else:
                        table.setItem(i, 3, QTableWidgetItem("-"))
                    total = r[4]
                    if total is not None:
                        table.setItem(i, 4, QTableWidgetItem(f"R$ {float(total):.2f}"))
                    else:
                        table.setItem(i, 4, QTableWidgetItem("-"))

                    situacao = str(r[5] or "").strip().upper()
                    atraso = 0
                    if venc:
                        atraso = (hoje - venc).days
                    if situacao == "P":
                        status_text = "Paga"
                        status_color = t.success
                    elif situacao == "C":
                        status_text = "Cancelada"
                        status_color = t.text_muted
                    elif situacao == "B":
                        status_text = "Baixada (escritural)"
                        status_color = t.text_muted
                    elif atraso > 0:
                        status_text = f"Vencida ({atraso} dia(s))"
                        status_color = t.danger
                    elif atraso == 0:
                        status_text = "Vence hoje"
                        status_color = t.warning
                    else:
                        status_text = f"A vencer ({-atraso} dia(s))"
                        status_color = t.success

                    table.setItem(i, 5, QTableWidgetItem(str(atraso) if venc else "-"))
                    sit_item = QTableWidgetItem(status_text)
                    sit_item.setForeground(QColor(status_color))
                    table.setItem(i, 6, sit_item)

                    nome_carteira = str(r[6] or "").strip()
                    if nome_carteira:
                        tipo_text = nome_carteira
                    else:
                        abrev = str(r[7] or "").strip()
                        tipo_map = {"DUP": "Duplicata", "CHQ": "Cheque", "BOL": "Boleto",
                                    "CAR": "Cartao", "NP": "Nota Promissoria", "REC": "Recibo"}
                        tipo_text = tipo_map.get(abrev, abrev)
                    table.setItem(i, 7, QTableWidgetItem(tipo_text))

                layout.addWidget(table)

                lbl_total = QLabel(f"Total pendente: R$ {total_pendente:.2f}  |  {len(rows)} parcela(s)")
                lbl_total.setStyleSheet(f"font-size: 12px; color: {t.success}; font-weight: 600; padding: 4px 0;")
                layout.addWidget(lbl_total)

            btn_fechar = QPushButton("Fechar")
            btn_fechar.setStyleSheet(f"""
                QPushButton {{ background: {t.primary}; color: {t.selection_text}; border: none;
                    border-radius: 6px; padding: 8px 24px; font-size: 12px; font-weight: 600; }}
                QPushButton:hover {{ background: {t.primary_hover}; }}
            """)
            btn_fechar.clicked.connect(dlg.accept)
            layout.addWidget(btn_fechar, 0, Qt.AlignCenter)

            dlg.exec()

        def _on_error(e):
            show_error(self, "Erro", f"Falha ao buscar pendencias:\n{e}")

        run_in_thread(_do_query, _on_result, _on_error)
    def _open_calculadora(self):
        from frontend.app.services.calculadora import CalculadoraDialog
        dlg = CalculadoraDialog(self)
        dlg.exec()

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

        if not self._validar_boletos_antes_envio(body_template, selected):
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
                        success = resp.status_code < 300
                        if success:
                            results["success"] += 1
                        else:
                            results["errors"] += 1
                        results["details"].append({"idx": idx, "ok": success, "status": resp.status_code, "body" if not success else "": resp.text[:200] if not success else ""})
                        client_name = str(row[3]) if row[3] else ""
                        self._record_sent(phone, tag,
                            client_name=client_name,
                            template_name=template_data.get("name", ""),
                            body=body,
                            url=url,
                            method=method,
                            status_code=resp.status_code,
                            success=success)
                    except Exception as e:
                        results["errors"] += 1
                        results["details"].append({"idx": idx, "ok": False, "error": str(e)})
            return results

        def _on_sent(results: dict):
            self.btn_enviar.setEnabled(True)
            self.btn_enviar.setText("Enviar Agora")
            parts = [f"{results['success']} de {results['total']} enviados com sucesso."]
            if results["blocked"]:
                parts.append(f"\n{results['blocked']} bloqueado(s) pelo intervalo entre disparos da tag '{tag}'.")
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

    def _calcular_barcode(self, row: tuple) -> str | None:
        id_parcela = row[24]
        if not id_parcela:
            return None

        try:
            from frontend.app.core.firebird_client import FirebirdClient
            from frontend.app.services.boleto_watcher import _ensure_table
            fb = FirebirdClient()
            fb.conectar()
            _ensure_table()
            r = fb.query(
                "SELECT CODIGOBARRAS, LINHADIGITAVEL, CAMINHOPDF "
                "FROM BOLETO_GERADO "
                "WHERE IDPARCELA = ?",
                (id_parcela,),
            )
            fb.fechar()
            if r:
                return r[0][0]
        except Exception:
            pass

        return None

    def _load_tipo_cliente_options(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        try:
            from frontend.app.core.firebird_client import FirebirdClient
            fb = FirebirdClient()
            try:
                fb.conectar()
                rows = fb.query(
                    "SELECT COD_TIPO, DESCR_TIPO FROM TRECTIPOCLIENTE WHERE ATIVO = 1 ORDER BY COD_TIPO"
                )
                if rows:
                    for r in rows:
                        label = f"{r[1]} ({r[0]})" if r[1] else str(r[0])
                        items.append((label, str(r[0])))
            except Exception:
                pass
            finally:
                fb.fechar()
        except Exception:
            pass
        if not items:
            items = [("Padrão (01)", "01"), ("Administradora (02)", "02")]
        return items

    def _load_bank_config(self) -> dict:
        from frontend.app.core.firebird_client import FirebirdClient
        configs = {}
        fb = FirebirdClient()
        try:
            fb.conectar()
            rows = fb.query(r"""
                SELECT
                    Par.Empresa,
                    Par.Portador,
                    Par.NomeCarteira,
                    Par.CodCarteira,
                    Cta.Agencia,
                    Cta.Numero,
                    MAX(CASE WHEN Conf.Nome = 'CodigoAgencia'       THEN Conf.Valor END) AS AgenciaPosto,
                    MAX(CASE WHEN Conf.Nome = 'NumeroContaCorrente' THEN Conf.Valor END) AS ContaCorrente,
                    MAX(CASE WHEN Conf.Nome = 'CodigoCedente'       THEN Conf.Valor END) AS CodigoCedente,
                    MAX(CASE WHEN Conf.Nome = 'PrefixoNossoNumero'  THEN Conf.Valor END) AS PrefixoNossoNumero,
                    MAX(CASE WHEN Conf.Nome = 'Modalidade'          THEN Conf.Valor END) AS Modalidade,
                    MAX(CASE WHEN Conf.Nome = 'Variacao'            THEN Conf.Valor END) AS Variacao,
                    Par.DIRETORIOGERACAOBOLETO,
                    Par.PREFIXONOMENCLATURA
                FROM TCOBPARAMETROECOBRANCA Par
                LEFT JOIN TBANCONTA Cta ON Cta.Codigo = Par.CodigoConta AND Cta.Empresa = Par.Empresa
                LEFT JOIN TCOBCONFECOBRANCA Conf ON Conf.Empresa = Par.Empresa
                                            AND Conf.Portador = Par.Portador
                                            AND Conf.NomeCarteira = Par.NomeCarteira
                GROUP BY Par.Empresa, Par.Portador, Par.NomeCarteira, Par.CodCarteira,
                         Cta.Agencia, Cta.Numero,
                         Par.DIRETORIOGERACAOBOLETO, Par.PREFIXONOMENCLATURA
            """)
            if rows:
                for r in rows:
                    key = (str(r[0]), str(r[1]))
                    agencia, posto = self._parse_agencia_posto(str(r[6] or ""))
                    configs[key] = {
                        "nome_carteira": r[2],
                        "cod_carteira": r[3],
                        "agencia": agencia,
                        "posto": posto,
                        "conta": str(r[5] or ""),
                        "conta_corrente": str(r[7] or ""),
                        "beneficiario": str(r[8] or ""),
                        "prefixo_nosso_numero": str(r[9] or ""),
                        "modalidade": str(r[10] or ""),
                        "variacao": str(r[11] or ""),
                        "diretorio_boletos": str(r[12] or ""),
                        "prefixo_nomenclatura": str(r[13] or ""),
                        "convenio": "",
                        "banco": None,
                    }
            for cfg in configs.values():
                cfg["banco"] = self._extrair_banco(cfg["nome_carteira"])
        except Exception:
            pass
        finally:
            fb.fechar()
        return configs

    def _parse_agencia_posto(self, valor: str) -> tuple[str, str]:
        if not valor:
            return ("", "")
        agencia = valor.split(".")[0].split("-")[0].strip()
        if "." in valor:
            posto = valor.split(".")[1].split("-")[0].strip()
        else:
            posto = ""
        return (agencia, posto)

    def _extrair_banco(self, nome_carteira: str) -> int | None:
        import re
        m = re.search(r"\d{3}", nome_carteira or "")
        if m:
            return int(m.group())
        return None

    def _validar_boletos_antes_envio(self, template_body: str, selected_rows: list[int]) -> bool:
        usa_barcode = "{codigo_barras}" in template_body or "{linha_digitavel}" in template_body
        if not usa_barcode:
            return True

        sem_boleto = []
        for idx in selected_rows:
            row = self._results_data[idx]
            bc = self._calcular_barcode(row)
            if not bc:
                nome = str(row[3] or f"ID {row[2]}") if len(row) > 3 else f"linha {idx}"
                sem_boleto.append(nome)

        if not sem_boleto:
            return True

        limite = 10
        msg = (
            "Os seguintes clientes n\u00e3o possuem boleto gerado:\n\n"
            + "\n".join(f"\u2022 {nome}" for nome in sem_boleto[:limite])
            + ("\n..." if len(sem_boleto) > limite else "")
            + "\n\nAcesse o eCobranca e gere um boleto antes de cobrar."
        )
        resposta = QMessageBox.warning(self, "Boletos Pendentes", msg,
                                       QMessageBox.Yes | QMessageBox.No)
        return resposta == QMessageBox.Yes

    def _substitute_placeholders(self, template: str, row: tuple) -> str:
        result = template
        for placeholder, col_idx in PLACEHOLDER_MAP.items():
            if col_idx < len(row) and row[col_idx] is not None:
                val = str(row[col_idx])
                result = result.replace("{" + placeholder + "}", val)
        if "{codigo_barras}" in result or "{linha_digitavel}" in result:
            bc = self._calcular_barcode(row)
            result = result.replace("{codigo_barras}", bc or "")
            result = result.replace("{linha_digitavel}", calcular_linha_digitavel(bc) if bc else "")
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
