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
)
from frontend.app.api.client import client
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb


class UserSettingsView(QWidget):
    def __init__(self, token: str, user: dict):
        super().__init__()
        self.token = token
        self.user = user
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

        card = QFrame()
        card.setObjectName("settingsCard")
        card.setStyleSheet(
            """
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
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)

        section = QLabel("Cooldown de Cobranca")
        section.setObjectName("sectionTitle")
        card_layout.addWidget(section)

        desc = QLabel(
            "Tempo minimo entre envios de cobranca para o mesmo numero. "
            "Este limite e individual por usuario."
        )
        desc.setObjectName("sectionDesc")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        divider = QFrame()
        divider.setStyleSheet("QFrame { max-height: 1px; min-height: 1px; background-color: #30363d; border: none; }")
        card_layout.addWidget(divider)

        form = QFormLayout()
        form.setSpacing(8)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 720)
        self.cooldown_spin.setSuffix(" horas")
        self.cooldown_spin.setValue(self.user.get("cobranca_cooldown_hours", 48))
        self.cooldown_spin.setMinimumHeight(34)
        self.cooldown_spin.setMinimumWidth(140)
        form.addRow("Intervalo minimo:", self.cooldown_spin)
        card_layout.addLayout(form)

        card_layout.addSpacing(6)
        btn_save = QPushButton("Salvar Configuracoes")
        btn_save.setProperty("accent", True)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save)
        card_layout.addWidget(btn_save)

        card_layout.addStretch()
        layout.addWidget(card)

        # --- Firebird config card ---
        fb_card = QFrame()
        fb_card.setObjectName("settingsCard")
        fb_card.setStyleSheet(card.styleSheet())
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
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Load current Firebird config
        self._load_fb_config()

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

    def _save(self):
        data = {
            "cobranca_cooldown_hours": self.cooldown_spin.value(),
        }
        logger.info("SETTINGS", "Salvando configuracoes", cooldown=data["cobranca_cooldown_hours"])
        run_in_thread(
            self._update_user,
            lambda r: (
                logger.info("SETTINGS", "Configuracoes salvas com sucesso"),
                show_success(self, "OK", "Configuracoes salvas!"),
            ),
            lambda e: show_error(self, "Erro", str(e)),
            self.user["id"],
            data,
        )

    def _update_user(self, user_id: str, data: dict) -> dict:
        from frontend.app.api.user_api import update_user
        result = update_user(user_id, data)
        client.set_token(client._token)
        return result

    def refresh(self):
        from frontend.app.api.user_api import list_users
        users = list_users()
        for u in users:
            if u["id"] == self.user["id"]:
                self.user.update(u)
                self.cooldown_spin.setValue(u.get("cobranca_cooldown_hours", 48))
                break
