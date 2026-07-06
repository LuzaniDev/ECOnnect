import os
import json
import shutil
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
    QFileDialog,
    QComboBox,
)
from PySide6.QtGui import QColor, QPixmap, QIcon, QImage
from frontend.app.api.client import client
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.core.logger import logger
from frontend.app.core.firebird_client import fb
from frontend.app.core.theme import theme_manager, _hex_to_rgb

TAG_COOLDOWN_FILE = os.path.join(os.path.expanduser("~"), ".econnect", "tag_cooldown_config.json")
TEMPLATES_FILE = os.path.join(os.path.expanduser("~"), ".econnect", "mundo_bots_templates.json")
AVATAR_DIR = os.path.join(os.path.expanduser("~"), ".econnect", "avatars")


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

        t = theme_manager.current()
        title = QLabel("Configuracoes")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {t.text};")
        layout.addWidget(title)

        user_info = QFrame()
        user_info.setObjectName("card")
        user_layout = QHBoxLayout(user_info)
        user_layout.setSpacing(14)

        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setCursor(Qt.PointingHandCursor)
        self._load_avatar(avatar)
        avatar.mousePressEvent = lambda e: self._pick_avatar(avatar)
        user_layout.addWidget(avatar)

        t = theme_manager.current()
        info_text = QLabel(
            f'<b style="color:{t.text};">{self.user.get("username", "")}</b><br>'
            f'<span style="color:{t.text_secondary};">{self.user.get("role", "").capitalize()} &bull; '
            f'{self.user.get("email", "")}</span>'
        )
        info_text.setTextFormat(Qt.RichText)
        user_layout.addWidget(info_text)
        user_layout.addStretch()

        layout.addWidget(user_info)

        t = theme_manager.current()
        CARD_STYLE = f"""
            QFrame#settingsCard {{
                background-color: {t.surface};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 24px;
            }}
            QLabel#sectionTitle {{
                font-size: 14px;
                font-weight: 700;
                color: {t.text};
                padding-bottom: 2px;
            }}
            QLabel#sectionDesc {{
                font-size: 12px;
                color: {t.text_secondary};
                padding-bottom: 14px;
            }}
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
            f"max-height: 1px; min-height: 1px; background-color: {t.border}; border: none;"
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
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_test_fb = QPushButton("Testar Conexao")
        btn_test_fb.setCursor(Qt.PointingHandCursor)
        btn_test_fb.setStyleSheet(f"""
            QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border};
                border-radius: 6px; color: {t.text}; padding: 8px 18px;
                font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {t.border}; }}
        """)
        btn_test_fb.clicked.connect(self._test_fb_connection)
        btn_row.addWidget(btn_test_fb)

        btn_save_fb = QPushButton("Salvar Configuracao Firebird")
        btn_save_fb.setProperty("accent", True)
        btn_save_fb.setCursor(Qt.PointingHandCursor)
        btn_save_fb.clicked.connect(self._save_fb)
        btn_row.addWidget(btn_save_fb)

        fb_card_layout.addLayout(btn_row)

        fb_card_layout.addStretch()
        layout.addWidget(fb_card)

        # --- Boleto directories card ---
        boleto_card = QFrame()
        boleto_card.setObjectName("settingsCard")
        boleto_card.setStyleSheet(CARD_STYLE)
        boleto_card_layout = QVBoxLayout(boleto_card)
        boleto_card_layout.setSpacing(6)

        boleto_section = QLabel("Diretorios de Boletos")
        boleto_section.setObjectName("sectionTitle")
        boleto_card_layout.addWidget(boleto_section)

        boleto_desc = QLabel(
            "Diretorios monitorados pelo watcher de boletos (boleto_pdf + watchdog). "
            "Os PDFs encontrados sao processados e inseridos em BOLETO_GERADO automaticamente."
        )
        boleto_desc.setObjectName("sectionDesc")
        boleto_desc.setWordWrap(True)
        boleto_card_layout.addWidget(boleto_desc)

        boleto_divider = QFrame()
        boleto_divider.setStyleSheet(f"max-height: 1px; min-height: 1px; background-color: {t.border}; border: none;")
        boleto_card_layout.addWidget(boleto_divider)

        self._boleto_dirs_label = QLabel("Carregando...")
        self._boleto_dirs_label.setWordWrap(True)
        self._boleto_dirs_label.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; padding: 4px 0;")
        boleto_card_layout.addWidget(self._boleto_dirs_label)

        layout.addWidget(boleto_card)

        # --- Tag Cooldown config card ---
        tag_card = QFrame()
        tag_card.setObjectName("settingsCard")
        tag_card.setStyleSheet(CARD_STYLE)
        tag_card_layout = QVBoxLayout(tag_card)
        tag_card_layout.setSpacing(6)

        tag_section = QLabel("Intervalo entre disparos por Tag")
        tag_section.setObjectName("sectionTitle")
        tag_card_layout.addWidget(tag_section)

        tag_desc = QLabel(
            "Defina o tempo de bloqueio (em horas) para cada tag. "
            "As tags sao carregadas automaticamente dos templates existentes. "
            "Quando uma mensagem com a tag for enviada para um cliente, "
            "ele nao podera receber outra com a mesma tag ate que o intervalo expire."
        )
        tag_desc.setObjectName("sectionDesc")
        tag_desc.setWordWrap(True)
        tag_card_layout.addWidget(tag_desc)

        tag_divider = QFrame()
        tag_divider.setStyleSheet(f"max-height: 1px; min-height: 1px; background-color: {t.border}; border: none;")
        tag_card_layout.addWidget(tag_divider)

        self.tag_table = QTableWidget()
        self.tag_table.setColumnCount(3)
        self.tag_table.setHorizontalHeaderLabels(["", "TAG", "BLOQUEIO (HORAS)"])
        self.tag_table.horizontalHeader().setStretchLastSection(True)
        self.tag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tag_table.horizontalHeader().resizeSection(0, 52)
        self.tag_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tag_table.setSelectionMode(QTableWidget.NoSelection)
        self.tag_table.setShowGrid(False)
        self.tag_table.setMinimumHeight(80)
        self.tag_table.verticalHeader().setDefaultSectionSize(28)
        self.tag_table.verticalHeader().setVisible(False)
        self.tag_table.setStyleSheet(f"""
            QTableWidget {{
                background: transparent;
                border: none;
                font-size: 12px;
                color: {t.text};
            }}
            QTableWidget::item {{
                padding: 2px 4px;
                border-bottom: 1px solid {t.border};
            }}
            QHeaderView::section {{
                background: transparent;
                color: {t.text_secondary};
                font-size: 10px;
                font-weight: 700;
                border: none;
                padding: 2px 0;
            }}
        """)
        tag_card_layout.addWidget(self.tag_table)

        tag_card_layout.addSpacing(6)
        btn_save_tags = QPushButton("Salvar Intervalo das Tags")
        btn_save_tags.setProperty("accent", True)
        btn_save_tags.setCursor(Qt.PointingHandCursor)
        btn_save_tags.clicked.connect(self._save_tag_cooldowns)
        tag_card_layout.addWidget(btn_save_tags)

        layout.addWidget(tag_card)

        # Theme selector was removed — now on login screen
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
        config = self._load_tag_cooldown_config()
        ordered = [t for t in config if t in tags]
        remaining = sorted(t for t in tags if t not in ordered)
        return ordered + remaining

    def _load_tag_cooldown_table(self):
        t = theme_manager.current()
        self.tag_table.setRowCount(0)
        config = self._load_tag_cooldown_config()
        all_tags = self._get_all_template_tags()

        self._tag_spins = {}
        if all_tags:
            for tag in all_tags:
                row = self.tag_table.rowCount()
                self.tag_table.insertRow(row)

                btn_widget = self._create_order_buttons(row, tag)
                self.tag_table.setCellWidget(row, 0, btn_widget)

                item = QTableWidgetItem(tag)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor(t.text))
                self.tag_table.setItem(row, 1, item)

                val = config.get(tag, 0)
                spin = QSpinBox()
                spin.setRange(0, 7200)
                spin.setValue(val)
                spin.setSuffix(" horas")
                spin.setFixedHeight(22)
                spin.setMinimumWidth(80)
                spin.setStyleSheet(f"""
                    QSpinBox {{ background: {t.bg}; border: 1px solid {t.border};
                        border-radius: 3px; padding: 0px 2px; color: {t.text};
                        font-size: 11px; }}
                """)
                self.tag_table.setCellWidget(row, 2, spin)
                self._tag_spins[tag] = spin

            self.tag_table.setVisible(True)
        else:
            self.tag_table.setRowCount(1)
            self.tag_table.setSpan(0, 0, 1, 3)
            item = QTableWidgetItem("Nenhuma tag encontrada. Crie templates com tags primeiro.")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QColor(t.text_secondary))
            self.tag_table.setItem(0, 1, item)

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
        show_success(self, "OK", "Intervalo das tags salvo com sucesso!")

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

    def _test_fb_connection(self):
        database = self.fb_database.text().strip()
        user = self.fb_user.text().strip()
        password = self.fb_password.text().strip()
        if not database:
            show_error(self, "Erro", "Preencha o caminho do banco Firebird primeiro.")
            return

        def _do_test():
            import fdb
            conn = fdb.connect(dsn=database, user=user, password=password, charset="WIN1252")
            conn.close()
            return True

        def _on_success(_):
            show_success(self, "OK", "Conexao Firebird bem-sucedida!")

        def _on_error(e):
            show_error(self, "Falha na Conexao", f"Nao foi possivel conectar ao Firebird:\n{e}")

        run_in_thread(_do_test, _on_success, _on_error)

    def _do_save_fb(self, company_code: str, data: dict):
        from frontend.app.api.company_config_api import update_company_config
        result = update_company_config(company_code, data)
        fb.configure(
            dsn=result["fb_database"],
            user=result["fb_user"],
            password=result["fb_password"],
        )
        return result

    def _avatar_path(self) -> str:
        uname = self.user.get("username", "user")
        os.makedirs(AVATAR_DIR, exist_ok=True)
        return os.path.join(AVATAR_DIR, f"{uname}.png")

    def _load_avatar(self, label: QLabel):
        path = self._avatar_path()
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                label.setPixmap(pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                label.setStyleSheet("border-radius: 18px; background: transparent;")
                return
        t = theme_manager.current()
        initial = self.user.get("username", "U")[0].upper()
        label.setText(initial)
        label.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {t.warning}; "
            f"background-color: rgba({_hex_to_rgb(t.warning)}, 0.12); "
            f"border-radius: 20px;"
        )

    def _pick_avatar(self, label: QLabel):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Foto de Perfil", "",
            "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        try:
            dest = self._avatar_path()
            os.makedirs(AVATAR_DIR, exist_ok=True)
            shutil.copy2(path, dest)
            self._load_avatar(label)
        except Exception as e:
            show_error(self, "Erro", f"Nao foi possivel carregar a imagem:\n{e}")

    def _create_order_buttons(self, row: int, tag: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        t = theme_manager.current()
        up_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>"""
        _up_img = QImage.fromData(up_svg.encode(), "SVG")
        _up_icon = QIcon(QPixmap.fromImage(_up_img))
        btn_up = QPushButton(_up_icon, "")
        btn_up.setFixedSize(22, 22)
        btn_up.setToolTip("Mover para cima")
        btn_up.setStyleSheet(
            f"QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border}; "
            f"border-radius: 3px; color: {t.text_secondary}; }} "
            f"QPushButton:hover {{ background: {t.border}; color: {t.text}; }}"
        )
        btn_up.clicked.connect(lambda checked, r=row, tname=tag: self._move_tag(r, tname, -1))

        down_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>"""
        _down_img = QImage.fromData(down_svg.encode(), "SVG")
        _down_icon = QIcon(QPixmap.fromImage(_down_img))
        btn_down = QPushButton(_down_icon, "")
        btn_down.setFixedSize(22, 22)
        btn_down.setToolTip("Mover para baixo")
        btn_down.setStyleSheet(
            f"QPushButton {{ background: {t.surface_elevated}; border: 1px solid {t.border}; "
            f"border-radius: 3px; color: {t.text_secondary}; }} "
            f"QPushButton:hover {{ background: {t.border}; color: {t.text}; }}"
        )
        btn_down.clicked.connect(lambda checked, r=row, t=tag: self._move_tag(r, t, 1))

        layout.addWidget(btn_up)
        layout.addWidget(btn_down)
        layout.addStretch()
        return container

    def _move_tag(self, row: int, tag: str, direction: int):
        new_row = row + direction
        if new_row < 0 or new_row >= self.tag_table.rowCount():
            return
        # Swap rows by rebuilding the table
        config = self._load_tag_cooldown_config()
        all_tags = self._get_all_template_tags()
        idx = all_tags.index(tag)
        all_tags[idx], all_tags[new_row] = all_tags[new_row], all_tags[idx]
        # Persist new order
        ordered_config = {}
        for t in all_tags:
            ordered_config[t] = config.get(t, 0)
        self._save_tag_cooldown_config(ordered_config)
        self._load_tag_cooldown_table()

    def refresh(self):
        from frontend.app.api.user_api import list_users
        users = list_users()
        for u in users:
            if u["id"] == self.user["id"]:
                self.user.update(u)
                break
        self._load_tag_cooldown_table()
        self._load_boleto_dirs()

    def _load_boleto_dirs(self):
        try:
            from frontend.app.services.boleto_watcher import _listar_configs, _diretorio_valido
            configs = _listar_configs()
            if not configs:
                self._boleto_dirs_label.setText("Nenhuma configuracao de boleto encontrada em TCOBPARAMETROECOBRANCA.")
                return
            lines = []
            for row in configs:
                emp = str(row[0]).strip()
                port = str(row[1]).strip()
                diretorio = str(row[2] or "").strip()
                prefixo = str(row[3] or "").strip()
                valido = _diretorio_valido(diretorio)
                status = "OK" if valido else "INACESSIVEL"
                lines.append(f"  Empresa {emp} / Portador {port}: {diretorio}")
                lines.append(f"    Prefixo: {prefixo}  Status: {status}")
            self._boleto_dirs_label.setText("\n".join(lines))
        except Exception as e:
            self._boleto_dirs_label.setText(f"Erro ao carregar diretorios: {e}")
