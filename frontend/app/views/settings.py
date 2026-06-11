import os
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QLineEdit,
    QFrame,
    QScrollArea,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtGui import QColor
from frontend.app.api.client import client
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb

TAG_COOLDOWN_FILE = os.path.join(os.path.expanduser("~"), ".econnect", "tag_cooldown_config.json")
TEMPLATES_FILE = os.path.join(os.path.expanduser("~"), ".econnect", "mundo_bots_templates.json")


class UserSettingsView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
        self._tag_spins = {}
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Configuracoes")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #c9d1d9;")
        layout.addWidget(title)

        user_info = QFrame()
        user_info.setStyleSheet(
            "QFrame { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 8px; padding: 14px 18px; }"
        )
        user_layout = QHBoxLayout(user_info)
        user_layout.setSpacing(14)

        avatar = QLabel(self.user.get("username", "U")[0].upper())
        avatar.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #d29922; "
            "background-color: rgba(210, 153, 34, 0.12); "
            "border-radius: 20px; padding: 6px 12px; min-width: 20px;"
        )
        user_layout.addWidget(avatar)

        info_text = QLabel(
            f'<b style="color:#c9d1d9;">{self.user.get("username", "")}</b><br>'
            f'<span style="color:#8b949e;">{self.user.get("role", "").capitalize()} &bull; '
            f'{self.user.get("email", "")}</span>'
        )
        info_text.setTextFormat(Qt.RichText)
        user_layout.addWidget(info_text)
        user_layout.addStretch()

        layout.addWidget(user_info)

        CARD_STYLE = """
            QFrame#settingsCard {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 24px;
            }
            QLabel#sectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #c9d1d9;
                padding-bottom: 2px;
            }
            QLabel#sectionDesc {
                font-size: 12px;
                color: #8b949e;
                padding-bottom: 14px;
            }
        """

        # --- Firebird config card ---
        fb_card = QFrame()
        fb_card.setObjectName("settingsCard")
        fb_card.setStyleSheet(CARD_STYLE)
        fb_card_layout = QVBoxLayout(fb_card)
        fb_card_layout.setSpacing(6)

        fb_section = QLabel("Conexao Firebird")
        fb_section.setObjectName("sectionTitle")
        fb_card_layout.addWidget(fb_section)

        fb_desc = QLabel(
            "Configuracoes do banco de dados Firebird para esta empresa. "
            "Altere apenas se o caminho padrao for diferente."
        )
        fb_desc.setObjectName("sectionDesc")
        fb_desc.setWordWrap(True)
        fb_card_layout.addWidget(fb_desc)

        fb_divider = QFrame()
        fb_divider.setStyleSheet(
            "QFrame { max-height: 1px; min-height: 1px; background-color: #30363d; border: none; }"
        )
        fb_card_layout.addWidget(fb_divider)

        fb_form = QFormLayout()
        fb_form.setSpacing(8)

        lbl_company = QLabel(f'Empresa: <b>{self.user.get("eco_empresa", "")}</b>')
        lbl_company.setTextFormat(Qt.RichText)
        fb_form.addRow(lbl_company)

        self.fb_database = QLineEdit()
        self.fb_database.setPlaceholderText("C:/ecosis/dados/ecodados.eco")
        self.fb_database.setMinimumHeight(34)
        fb_form.addRow("Caminho do banco:", self.fb_database)

        self.fb_user = QLineEdit()
        self.fb_user.setPlaceholderText("SYSDBA")
        self.fb_user.setMinimumHeight(34)
        fb_form.addRow("Usuario:", self.fb_user)

        self.fb_password = QLineEdit()
        self.fb_password.setPlaceholderText("masterkey")
        self.fb_password.setEchoMode(QLineEdit.Password)
        self.fb_password.setMinimumHeight(34)
        fb_form.addRow("Senha:", self.fb_password)

        fb_card_layout.addLayout(fb_form)

        fb_card_layout.addSpacing(6)
        btn_save_fb = QPushButton("Salvar Configuracao Firebird")
        btn_save_fb.setProperty("accent", True)
        btn_save_fb.setCursor(Qt.PointingHandCursor)
        btn_save_fb.clicked.connect(self._save_fb)
        fb_card_layout.addWidget(btn_save_fb)

        fb_card_layout.addStretch()
        layout.addWidget(fb_card)

        # --- Tag Cooldown config card ---
        tag_card = QFrame()
        tag_card.setObjectName("settingsCard")
        tag_card.setStyleSheet(CARD_STYLE)
        tag_card_layout = QVBoxLayout(tag_card)
        tag_card_layout.setSpacing(6)

        tag_section = QLabel("Cooldown por Tag")
        tag_section.setObjectName("sectionTitle")
        tag_card_layout.addWidget(tag_section)

        tag_desc = QLabel(
            "Defina o tempo de bloqueio (em horas) para cada tag. "
            "As tags sao carregadas automaticamente dos templates existentes. "
            "Quando uma mensagem com a tag for enviada para um cliente, "
            "ele nao podera receber outra com a mesma tag ate que o cooldown expire."
        )
        tag_desc.setObjectName("sectionDesc")
        tag_desc.setWordWrap(True)
        tag_card_layout.addWidget(tag_desc)

        tag_divider = QFrame()
        tag_divider.setStyleSheet("QFrame { max-height: 1px; min-height: 1px; background-color: #30363d; border: none; }")
        tag_card_layout.addWidget(tag_divider)

        self.tag_table = QTableWidget()
        self.tag_table.setColumnCount(2)
        self.tag_table.setHorizontalHeaderLabels(["TAG", "BLOQUEIO (HORAS)"])
        self.tag_table.horizontalHeader().setStretchLastSection(True)
        self.tag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tag_table.setSelectionMode(QTableWidget.NoSelection)
        self.tag_table.setShowGrid(False)
        self.tag_table.setMinimumHeight(80)
        self.tag_table.verticalHeader().setDefaultSectionSize(28)
        self.tag_table.verticalHeader().setVisible(False)
        self.tag_table.setStyleSheet("""
            QTableWidget {
                background: transparent;
                border: none;
                font-size: 12px;
                color: #c9d1d9;
            }
            QTableWidget::item {
                padding: 2px 4px;
                border-bottom: 1px solid #21262d;
            }
            QHeaderView::section {
                background: transparent;
                color: #8b949e;
                font-size: 10px;
                font-weight: 700;
                border: none;
                padding: 2px 0;
            }
        """)
        tag_card_layout.addWidget(self.tag_table)

        tag_card_layout.addSpacing(6)
        btn_save_tags = QPushButton("Salvar Cooldown das Tags")
        btn_save_tags.setProperty("accent", True)
        btn_save_tags.setCursor(Qt.PointingHandCursor)
        btn_save_tags.clicked.connect(self._save_tag_cooldowns)
        tag_card_layout.addWidget(btn_save_tags)

        layout.addWidget(tag_card)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Load configs
        self._load_fb_config()
        self._load_tag_cooldown_table()

    def _get_all_template_tags(self) -> list:
        tags = set()
        try:
            if os.path.exists(TEMPLATES_FILE):
                with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    templates = json.load(f)
                for t in templates:
                    tag = t.get("tag", "").strip()
                    if tag:
                        tags.add(tag)
        except Exception:
            pass
        return sorted(tags)

    def _load_tag_cooldown_table(self):
        self.tag_table.setRowCount(0)
        config = self._load_tag_cooldown_config()
        all_tags = self._get_all_template_tags()

        self._tag_spins = {}
        if all_tags:
            for tag in all_tags:
                row = self.tag_table.rowCount()
                self.tag_table.insertRow(row)

                item = QTableWidgetItem(tag)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor("#c9d1d9"))
                self.tag_table.setItem(row, 0, item)

                val = config.get(tag, 0)
                spin = QSpinBox()
                spin.setRange(0, 7200)
                spin.setValue(val)
                spin.setSuffix(" horas")
                spin.setFixedHeight(22)
                spin.setMinimumWidth(80)
                spin.setStyleSheet("""
                    QSpinBox { background: #0d1117; border: 1px solid #30363d;
                        border-radius: 3px; padding: 0px 2px; color: #c9d1d9;
                        font-size: 11px; }
                """)
                self.tag_table.setCellWidget(row, 1, spin)
                self._tag_spins[tag] = spin

            self.tag_table.setVisible(True)
        else:
            self.tag_table.setRowCount(1)
            self.tag_table.setSpan(0, 0, 1, 2)
            item = QTableWidgetItem("Nenhuma tag encontrada. Crie templates com tags primeiro.")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QColor("#8b949e"))
            self.tag_table.setItem(0, 0, item)

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
            os.makedirs(os.path.dirname(TAG_COOLDOWN_FILE), exist_ok=True)
            with open(TAG_COOLDOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _save_tag_cooldowns(self):
        config = {}
        for tag, spin in self._tag_spins.items():
            config[tag] = spin.value()
        self._save_tag_cooldown_config(config)
        show_success(self, "OK", "Cooldown das tags salvo com sucesso!")

    def _load_fb_config(self):
        eco_empresa = self.user.get("eco_empresa")
        if not eco_empresa:
            return
        try:
            from frontend.app.api.company_config_api import get_company_config
            config = get_company_config(eco_empresa)
            self.fb_database.setText(config.get("fb_database", ""))
            self.fb_user.setText(config.get("fb_user", ""))
            self.fb_password.setText(config.get("fb_password", ""))
        except Exception:
            self.fb_database.setPlaceholderText("C:/ecosis/dados/ecodados.eco")
            self.fb_user.setPlaceholderText("SYSDBA")
            self.fb_password.setPlaceholderText("masterkey")

    def _save_fb(self):
        eco_empresa = self.user.get("eco_empresa")
        if not eco_empresa:
            show_error(self, "Erro", "Empresa nao identificada no usuario logado.")
            return
        data = {
            "fb_database": self.fb_database.text().strip(),
            "fb_user": self.fb_user.text().strip(),
            "fb_password": self.fb_password.text().strip(),
        }
        if not data["fb_database"]:
            show_error(self, "Erro", "O caminho do banco Firebird e obrigatorio.")
            return
        logger.info("SETTINGS", "Salvando configuracao Firebird", empresa=eco_empresa, **data)
        run_in_thread(
            self._do_save_fb,
            lambda r: (
                logger.info("SETTINGS", "Configuracao Firebird salva"),
                show_success(self, "OK", "Configuracao Firebird salva!"),
            ),
            lambda e: show_error(self, "Erro", str(e)),
            eco_empresa,
            data,
        )

    def _do_save_fb(self, company_code: str, data: dict):
        from frontend.app.api.company_config_api import update_company_config
        result = update_company_config(company_code, data)
        fb.configure(
            dsn=result["fb_database"],
            user=result["fb_user"],
            password=result["fb_password"],
        )
        return result

    def refresh(self):
        from frontend.app.api.user_api import list_users
        users = list_users()
        for u in users:
            if u["id"] == self.user["id"]:
                self.user.update(u)
                break
        self._load_tag_cooldown_table()
