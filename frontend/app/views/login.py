import sys
import os
import datetime
import traceback
from pathlib import Path
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFrame,
)
from frontend.app.core.eco_auth import login_completo, listar_empresas
from frontend.app.core.logger import logger
from frontend.app.core.theme import theme_manager, ThemeType
from frontend.app.widgets.dialogs import show_error


def _log_login(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent.parent
    log_file = exe_dir / "econnect.log"
    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] login: {msg}\n")
        f.flush()


def _login_qss():
    t = theme_manager.current()
    return f"""
QWidget#login_page {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {t.gradient_start}, stop:1 {t.gradient_end});
}}
"""


class LoginView(QWidget):
    login_successful = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("login_page")
        self.setStyleSheet(_login_qss())
        self._build_ui()
        self._carregar_empresas()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        card_container = QHBoxLayout()
        card_container.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("login_card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(36, 36, 36, 36)

        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "logo_128.png"
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setFixedSize(64, 64)
        else:
            logo_label.setText("EC")
            logo_label.setStyleSheet("font-size: 42px; font-weight: 800;")
        logo_layout.addWidget(logo_label)
        card_layout.addLayout(logo_layout)

        title = QLabel("ECOnnect")
        title.setObjectName("login_title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("Sistema de Gerenciamento de Mensagens")
        subtitle.setObjectName("login_subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(16)

        lbl_user = QLabel("Usuario ECO")
        lbl_user.setObjectName("field_label")
        card_layout.addWidget(lbl_user)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Digite seu usuario ECO")
        card_layout.addWidget(self.txt_usuario)

        lbl_senha = QLabel("Senha")
        lbl_senha.setObjectName("field_label")
        card_layout.addWidget(lbl_senha)

        self.txt_senha = QLineEdit()
        self.txt_senha.setPlaceholderText("Digite sua senha ECO")
        self.txt_senha.setEchoMode(QLineEdit.Password)
        card_layout.addWidget(self.txt_senha)

        lbl_empresa = QLabel("Empresa")
        lbl_empresa.setObjectName("field_label")
        card_layout.addWidget(lbl_empresa)

        self.cmb_empresa = QComboBox()
        self.cmb_empresa.setPlaceholderText("Selecione a empresa")
        card_layout.addWidget(self.cmb_empresa)

        lbl_tema = QLabel("Tema")
        lbl_tema.setObjectName("field_label")
        card_layout.addWidget(lbl_tema)

        self.theme_combo = QComboBox()
        t = theme_manager.current()
        self.theme_combo.setStyleSheet(
            f"QComboBox {{ background: {t.bg}; border: 1px solid {t.border}; "
            f"border-radius: 4px; padding: 6px 10px; color: {t.text}; font-size: 12px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background: {t.surface}; color: {t.text}; "
            f"border: 1px solid {t.border}; }}"
        )
        self.theme_combo.addItem("🌙 Black (Escuro)", ThemeType.BLACK)
        self.theme_combo.addItem("☀️ White (Claro)", ThemeType.WHITE)
        self.theme_combo.addItem("💚 Matrix (Verde)", ThemeType.MATRIX)
        idx = self.theme_combo.findData(theme_manager.current().type)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        card_layout.addWidget(self.theme_combo)

        card_layout.addSpacing(12)

        self.btn_entrar = QPushButton("Entrar no ECOnnect")
        self.btn_entrar.setObjectName("login_btn")
        self.btn_entrar.setEnabled(False)
        self.btn_entrar.clicked.connect(self._on_entrar)
        card_layout.addWidget(self.btn_entrar)

        self.txt_usuario.textChanged.connect(self._check_fields)
        self.txt_senha.textChanged.connect(self._check_fields)

        self.txt_usuario.installEventFilter(self)
        self.txt_senha.installEventFilter(self)

        card_container.addStretch()
        card_container.addWidget(card)
        card_container.addStretch()

        outer.addStretch()
        outer.addLayout(card_container)
        outer.addStretch()

    def _check_fields(self):
        enabled = bool(self.txt_usuario.text().strip()) and bool(self.txt_senha.text().strip())
        self.btn_entrar.setEnabled(enabled)

    def _carregar_empresas(self):
        try:
            _log_login("Carregando lista de empresas...")
            empresas = listar_empresas()
            self.cmb_empresa.clear()
            for i, emp in enumerate(empresas):
                cod = emp["codigo"]
                fantasia = emp["fantasia"]
                self.cmb_empresa.addItem(f"{cod} - {fantasia}", cod)
            if self.cmb_empresa.count() > 0:
                self.cmb_empresa.setCurrentIndex(0)
            _log_login(f"Carregadas {len(empresas)} empresas")
        except Exception as e:
            _log_login(f"Erro ao carregar empresas: {e}", "ERROR")
            _log_login(f"Traceback: {traceback.format_exc()}", "ERROR")
            logger.error("LOGIN", "Erro ao carregar empresas", erro=str(e))
            self.cmb_empresa.addItem("Erro ao carregar empresas", "")

    def _on_theme_changed(self, idx: int):
        theme_type = self.theme_combo.itemData(idx)
        theme_manager.set_theme(theme_type)
        t = theme_manager.current()
        self.setStyleSheet(_login_qss())
        self.theme_combo.setStyleSheet(
            f"QComboBox {{ background: {t.bg}; border: 1px solid {t.border}; "
            f"border-radius: 4px; padding: 6px 10px; color: {t.text}; font-size: 12px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background: {t.surface}; color: {t.text}; "
            f"border: 1px solid {t.border}; }}"
        )

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.btn_entrar.isEnabled():
                self._on_entrar()
            return True
        return super().eventFilter(obj, event)

    def _on_entrar(self):
        usuario = self.txt_usuario.text().strip()
        senha = self.txt_senha.text()
        empresa = self.cmb_empresa.currentData()

        if not empresa:
            show_error(self, "Empresa", "Selecione uma empresa.")
            return

        self.btn_entrar.setEnabled(False)
        self.btn_entrar.setText("Autenticando...")

        try:
            dados = login_completo(usuario, senha, empresa)
            self.login_successful.emit(dados)
        except PermissionError as e:
            show_error(self, "Acesso Negado", str(e))
        except (ConnectionError, RuntimeError) as e:
            show_error(self, "Erro de Autenticação", str(e))
        except Exception as e:
            _log_login(f"Erro inesperado no login: {traceback.format_exc()}", "ERROR")
            show_error(self, "Erro Inesperado", f"Ocorreu um erro ao autenticar:\n{e}")
        finally:
            self.btn_entrar.setEnabled(True)
            self.btn_entrar.setText("Entrar no ECOnnect")
