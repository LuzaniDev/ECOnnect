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
from frontend.app.widgets.dialogs import show_error


def _log_login(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent.parent
    log_file = exe_dir / "econnect.log"
    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] login: {msg}\n")
        f.flush()


LOGIN_STYLE = """
QWidget#login_page {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d1117, stop:1 #161b22);
}
QWidget#login_card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 16px;
    min-width: 380px;
    max-width: 400px;
}
QWidget#login_card:hover {
    border-color: #1f6feb;
}
QLabel#login_title {
    font-size: 26px;
    font-weight: 800;
    color: #c9d1d9;
    letter-spacing: -0.3px;
}
QLabel#login_subtitle {
    font-size: 12px;
    color: #8b949e;
}
QLabel#field_label {
    font-size: 10px;
    color: #8b949e;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding-bottom: 2px;
}
QLineEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
    color: #c9d1d9;
    min-height: 18px;
}
QLineEdit:focus {
    border: 1px solid #1f6feb;
    background-color: #0d1117;
}
QLineEdit::placeholder {
    color: #484f58;
}
QComboBox {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
    color: #c9d1d9;
    min-height: 18px;
}
QComboBox:focus {
    border: 1px solid #1f6feb;
}
QComboBox::drop-down {
    border: none;
    width: 36px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    color: #c9d1d9;
    padding: 4px;
}
QPushButton#login_btn {
    background-color: #1f6feb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 12px;
    font-size: 14px;
    font-weight: 700;
    min-height: 20px;
}
QPushButton#login_btn:hover {
    background-color: #388bfd;
}
QPushButton#login_btn:disabled {
    background-color: #21262d;
    color: #484f58;
}
"""


class LoginView(QWidget):
    login_successful = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("login_page")
        self.setStyleSheet(LOGIN_STYLE)
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
            logo_label.setStyleSheet("font-size: 42px; font-weight: 800; color: #d29922;")
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
