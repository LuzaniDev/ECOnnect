import sys
import os
import subprocess
import uuid as uuid_mod
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox,
    QGroupBox, QSpinBox, QProgressBar, QCheckBox, QStackedWidget,
    QTextEdit, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QPixmap, QPalette, QColor

RESOLVED: dict = {}
ENV_LINES: list[str] = []

# ── ECocentauro Brand Palette ──
ECO = {
    "blue_dark":   "#00398a",
    "blue":        "#0e4f9c",
    "blue_light":  "#5c88b7",
    "orange":      "#fa8c20",
    "orange_light":"#eba964",
    "bg":          "#f0f3f5",
    "surface":     "#ffffff",
    "text":        "#1a1a2e",
    "text_sec":    "#5c88b7",
    "border":      "#dce1e5",
    "success":     "#2ecc71",
    "error":       "#e74c3c",
    "warning":     "#f39c12",
}


def _resolve_paths():
    if getattr(sys, "frozen", False):
        parent = Path(sys.executable).parent.resolve()
    else:
        parent = Path(__file__).parent.parent / "dist"
        parent.mkdir(parents=True, exist_ok=True)
    RESOLVED["exe"] = parent
    RESOLVED["env"] = parent / ".env"
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    for cand in [bundled / ".env.example", bundled / "backend" / ".env.example"]:
        if cand.exists():
            RESOLVED["example"] = cand
            break
    RESOLVED["econnect_exe"] = parent / "ECOnnect.exe"
    if not RESOLVED["econnect_exe"].exists():
        RESOLVED["econnect_exe"] = parent.parent / "ECOnnect.exe"


def _read_env_example() -> dict:
    defaults = {}
    path = RESOLVED.get("example")
    if path and path.exists():
        text = path.read_text(encoding="utf-8")
        ENV_LINES.clear()
        for line in text.splitlines():
            ENV_LINES.append(line)
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                defaults[k.strip()] = v.strip()
    return defaults


def _write_env(values: dict):
    lines = ENV_LINES[:]
    new_lines = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in values and values[k] is not None:
                new_lines.append(f"{k}={values[k]}")
                continue
        new_lines.append(line)
    env_path = RESOLVED["env"]
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return env_path


def _norm_path(path: str) -> str:
    path = path.strip()
    return path.replace("\\\\", "\\").replace("\\", "/")


# ── QSS Stylesheet (ECocentauro) ──
STYLES = f"""
QMainWindow, QWidget {{
    background-color: {ECO['bg']};
    color: {ECO['text']};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}}
QLabel {{
    color: {ECO['text']};
    background: transparent;
}}
QLabel[heading="true"] {{
    font-size: 22px;
    font-weight: 700;
    color: {ECO['blue_dark']};
}}
QLabel[subheading="true"] {{
    font-size: 14px;
    color: {ECO['text_sec']};
    font-weight: 400;
}}
QLabel[success="true"] {{
    color: {ECO['success']};
    font-weight: 600;
}}
QLabel[error="true"] {{
    color: {ECO['error']};
    font-weight: 600;
}}
QLineEdit {{
    border: 1.5px solid {ECO['border']};
    border-radius: 6px;
    padding: 7px 10px;
    background: {ECO['surface']};
    color: {ECO['text']};
    font-size: 13px;
    selection-background-color: {ECO['blue']};
    selection-color: white;
}}
QLineEdit:focus {{
    border-color: {ECO['blue']};
}}
QLineEdit[error="true"] {{
    border-color: {ECO['error']};
}}
QSpinBox {{
    border: 1.5px solid {ECO['border']};
    border-radius: 6px;
    padding: 7px 10px;
    background: {ECO['surface']};
    color: {ECO['text']};
    font-size: 13px;
}}
QSpinBox:focus {{
    border-color: {ECO['blue']};
}}
QPushButton {{
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    background-color: {ECO['blue']};
    color: white;
}}
QPushButton:hover {{
    background-color: {ECO['blue_dark']};
}}
QPushButton:pressed {{
    background-color: {ECO['blue_dark']};
}}
QPushButton:disabled {{
    background-color: #b0c4de;
    color: #e0e0e0;
}}
QPushButton[accent="true"] {{
    background-color: {ECO['orange']};
    color: white;
}}
QPushButton[accent="true"]:hover {{
    background-color: #e07a10;
}}
QPushButton[ghost="true"] {{
    background-color: transparent;
    color: {ECO['blue']};
    border: 1.5px solid {ECO['blue']};
}}
QPushButton[ghost="true"]:hover {{
    background-color: {ECO['blue']};
    color: white;
}}
QPushButton[danger="true"] {{
    background-color: {ECO['error']};
    color: white;
}}
QPushButton[danger="true"]:hover {{
    background-color: #c0392b;
}}
QPushButton[success="true"] {{
    background-color: {ECO['success']};
    color: white;
}}
QPushButton[success="true"]:hover {{
    background-color: #27ae60;
}}
QGroupBox {{
    font-size: 14px;
    font-weight: 600;
    color: {ECO['blue_dark']};
    border: 1.5px solid {ECO['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    background: {ECO['surface']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background: {ECO['surface']};
}}
QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: {ECO['border']};
    height: 8px;
    text-align: center;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {ECO['blue']};
    border-radius: 6px;
}}
QTextEdit {{
    border: 1.5px solid {ECO['border']};
    border-radius: 6px;
    padding: 8px;
    background: {ECO['surface']};
    color: {ECO['text']};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QFrame[card="true"] {{
    background: {ECO['surface']};
    border: 1.5px solid {ECO['border']};
    border-radius: 10px;
    padding: 16px;
}}
QCheckBox {{
    spacing: 8px;
    color: {ECO['text']};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1.5px solid {ECO['border']};
    background: {ECO['surface']};
}}
QCheckBox::indicator:checked {{
    background: {ECO['blue']};
    border-color: {ECO['blue']};
}}
"""


# ── Step Indicator Widget ──
class StepIndicator(QWidget):
    clicked = Signal(int)

    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self._steps = steps
        self._current = 0
        self._completed = set()
        self.setFixedWidth(200)
        self._setup()

    def _setup(self):
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(12, 20, 12, 20)
        self._labels: list[QLabel] = []
        for i, name in enumerate(self._steps):
            row = QHBoxLayout()
            row.setSpacing(10)
            num = QLabel(str(i + 1))
            num.setFixedSize(30, 30)
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(self._circle_style(i))
            lbl = QLabel(name)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(self._label_style(i))
            self._labels.append(lbl)
            row.addWidget(num, 0, Qt.AlignCenter)
            row.addWidget(lbl, 1)
            self._layout.addLayout(row)
        self._layout.addStretch()

    def _circle_style(self, idx):
        if idx == self._current:
            return f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {ECO['blue']}, stop:1 {ECO['blue_dark']});
                color: white; font-weight: bold; border-radius: 15px;
                font-size: 13px;
            """
        elif idx in self._completed:
            return f"""
                background: {ECO['success']}; color: white; font-weight: bold;
                border-radius: 15px; font-size: 13px;
            """
        else:
            return f"""
                background: {ECO['border']}; color: {ECO['text_sec']};
                border-radius: 15px; font-size: 13px;
            """

    def _label_style(self, idx):
        if idx == self._current:
            return f"color: {ECO['blue_dark']}; font-weight: 700; font-size: 13px; background: transparent;"
        elif idx in self._completed:
            return f"color: {ECO['success']}; font-weight: 500; font-size: 13px; background: transparent;"
        return f"color: {ECO['text_sec']}; font-size: 12px; background: transparent;"

    def set_current(self, idx: int):
        self._current = idx
        self._refresh()

    def set_completed(self, idx: int):
        self._completed.add(idx)
        self._refresh()

    def _refresh(self):
        for i, lbl in enumerate(self._labels):
            parent = lbl.parentWidget()
            if parent:
                num_widgets = parent.findChildren(QLabel)
                for w in num_widgets:
                    if w is not lbl and w.text() == str(i + 1):
                        w.setStyleSheet(self._circle_style(i))
                        break
                lbl.setStyleSheet(self._label_style(i))


# ── Wizard Page Base ──
class WizardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._valid = True

    def validate(self) -> bool:
        return True

    def on_enter(self):
        pass


# ── Page 1: Welcome ──
class WelcomePage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        logo_lbl = QLabel("EC")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet(f"""
            font-size: 56px; font-weight: 900;
            color: {ECO['blue']};
            background: {ECO['surface']};
            border-radius: 20px;
            padding: 20px 30px;
            max-width: 120px;
            margin: 0 auto;
        """)
        layout.addWidget(logo_lbl, 0, Qt.AlignCenter)

        title = QLabel("ECOnnect Configurador")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Configure todo o ambiente ECOnnect em passos simples")
        sub.setProperty("subheading", True)
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        features = QFrame()
        features.setProperty("card", True)
        feat_l = QVBoxLayout(features)
        feat_l.setSpacing(8)
        for icon, text in [
            ("\u2714", "Conexao e configuracao do Firebird"),
            ("\u2714", "Criacao de tabelas e semente de permissoes"),
            ("\u2714", "Conexao e configuracao do PostgreSQL"),
            ("\u2714", "Criacao de banco, usuario admin e tabelas"),
            ("\u2714", "Arquivo .env pronto para usar"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(icon))
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {ECO['text']}; font-size: 13px; background: transparent;")
            row.addWidget(lbl)
            row.addStretch()
            feat_l.addLayout(row)
        layout.addWidget(features)

        btn = QPushButton("Comecar Configuracao")
        btn.setProperty("success", True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ECO['blue']}; color: white;
                border: none; border-radius: 8px; padding: 14px 40px;
                font-size: 16px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {ECO['blue_dark']}; }}
        """)
        btn.clicked.connect(lambda: parent.next_step() if parent else None)
        layout.addWidget(btn, 0, Qt.AlignCenter)


# ── Page 2: Firebird Connection ──
class FirebirdPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_wizard = parent
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Conexao Firebird"))
        layout.addWidget(QLabel("Informe os dados do banco Firebird do sistema ECO."))

        fb = QGroupBox("Firebird")
        fb_l = QFormLayout(fb)
        self.fb_dsn = QLineEdit("C:\\ecosis\\dados\\ecodados.eco")
        self.fb_dsn.setToolTip(
            "Para servidor remoto: servidor:C:\\path\\banco.fdb\n"
            "Ex: srvlubri:C:\\ecosis\\dados\\ECODADOS.ECO\n\n"
            "Para local: C:\\path\\banco.fdb\n\n"
            "NAO use \\\\servidor\\compartilhamento (UNC).")
        self.fb_user = QLineEdit("SYSDBA")
        self.fb_pass = QLineEdit("masterkey")
        self.fb_pass.setEchoMode(QLineEdit.Password)
        fb_l.addRow("Database (DSN):", self.fb_dsn)
        fb_l.addRow("Usuario:", self.fb_user)
        fb_l.addRow("Senha:", self.fb_pass)

        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("Testar Conexao")
        self.btn_test.clicked.connect(self._test)
        btn_row.addWidget(self.btn_test)
        btn_row.addStretch()
        fb_l.addRow(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"background: transparent;")
        fb_l.addRow(self.status)
        layout.addWidget(fb)
        layout.addStretch()

    def get_values(self) -> dict:
        return {
            "FB_DATABASE": _norm_path(self.fb_dsn.text()),
            "FB_USER": self.fb_user.text().strip(),
            "FB_PASSWORD": self.fb_pass.text().strip(),
        }

    def _test(self):
        self.btn_test.setEnabled(False)
        self.status.setText("Testando...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        dsn = self.fb_dsn.text().strip()
        usr = self.fb_user.text().strip()
        pwd = self.fb_pass.text().strip()
        t = TestFbThread(dsn, usr, pwd)
        t.finished.connect(self._on_result)
        self._parent_wizard._run_thread(t)

    def _on_result(self, ok, msg):
        self.btn_test.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")


# ── Page 3: Firebird Setup ──
class FirebirdSetupPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_wizard = parent
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Preparacao do Firebird"))
        layout.addWidget(QLabel("Cria tabelas necessarias e insere permissoes (autonomias) no banco ECO."))

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(250)
        layout.addWidget(self.log_area)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("Executar Preparacao")
        self.btn_run.setProperty("success", True)
        self.btn_run.clicked.connect(self._run)
        btn_row.addWidget(self.btn_run)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def _log(self, msg, level="INFO"):
        tag = {"INFO": "INFO", "WARNING": "WARN", "ERROR": "ERRO"}.get(level, level)
        color = {"INFO": ECO['text'], "WARNING": ECO['warning'], "ERROR": ECO['error']}.get(level, ECO['text'])
        self.log_area.append(f'<span style="color:{color};">[{tag}] {msg}</span>')

    def _run(self):
        self.btn_run.setEnabled(False)
        self.status.setText("Preparando Firebird...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        self.log_area.clear()
        dsn = _norm_path(self._parent_wizard.fb_dsn.text())
        usr = self._parent_wizard.fb_user.text().strip()
        pwd = self._parent_wizard.fb_pass.text().strip()
        t = FbSetupThread(dsn, usr, pwd)
        t.log_signal.connect(self._log)
        t.finished.connect(self._on_result)
        self._parent_wizard._run_thread(t)

    def _on_result(self, ok, msg):
        self.btn_run.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")


# ── Page 4: PostgreSQL Connection ──
class PostgresPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_wizard = parent
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Conexao PostgreSQL"))
        layout.addWidget(QLabel("Informe os dados do banco PostgreSQL do ECOnnect."))

        pg = QGroupBox("PostgreSQL")
        pg_l = QFormLayout(pg)
        self.pg_host = QLineEdit("localhost")
        self.pg_port = QSpinBox(); self.pg_port.setRange(1, 65535); self.pg_port.setValue(5432)
        self.pg_user = QLineEdit("postgres")
        self.pg_pass = QLineEdit(); self.pg_pass.setEchoMode(QLineEdit.Password)
        self.pg_db = QLineEdit("econnect_db")
        pg_l.addRow("Host:", self.pg_host)
        pg_l.addRow("Porta:", self.pg_port)
        pg_l.addRow("Usuario:", self.pg_user)
        pg_l.addRow("Senha:", self.pg_pass)
        pg_l.addRow("Database:", self.pg_db)

        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("Testar Conexao")
        self.btn_test.clicked.connect(self._test)
        btn_row.addWidget(self.btn_test)
        btn_row.addStretch()
        pg_l.addRow(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        pg_l.addRow(self.status)
        layout.addWidget(pg)
        layout.addStretch()

    def get_values(self) -> dict:
        return {
            "DB_HOST": self.pg_host.text().strip(),
            "DB_PORT": str(self.pg_port.value()),
            "DB_USER": self.pg_user.text().strip(),
            "DB_PASSWORD": self.pg_pass.text().strip(),
            "DB_NAME": self.pg_db.text().strip(),
        }

    def _test(self):
        self.btn_test.setEnabled(False)
        self.status.setText("Testando...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        t = TestPgThread(self.pg_host.text().strip(), self.pg_port.value(),
                         self.pg_user.text().strip(), self.pg_pass.text().strip(),
                         self.pg_db.text().strip())
        t.finished.connect(self._on_result)
        self._parent_wizard._run_thread(t)

    def _on_result(self, ok, msg):
        self.btn_test.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")


# ── Page 5: PostgreSQL Setup ──
class PostgresSetupPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_wizard = parent
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Preparacao do PostgreSQL"))
        layout.addWidget(QLabel("Cria banco, usuario, tabelas, aplica migracoes e cria admin."))

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(250)
        layout.addWidget(self.log_area)

        btn_row = QHBoxLayout()
        self.btn_step1 = QPushButton("1. Criar DB + Usuario")
        self.btn_step1.clicked.connect(self._create_db)
        btn_row.addWidget(self.btn_step1)
        self.btn_step2 = QPushButton("2. Criar Tabelas + Migracoes")
        self.btn_step2.clicked.connect(self._run_migrations)
        self.btn_step2.setEnabled(False)
        btn_row.addWidget(self.btn_step2)
        self.btn_step3 = QPushButton("3. Criar Admin")
        self.btn_step3.clicked.connect(self._seed_admin)
        self.btn_step3.setEnabled(False)
        btn_row.addWidget(self.btn_step3)
        layout.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def _log(self, msg, level="INFO"):
        tag = {"INFO": "INFO", "WARNING": "WARN", "ERROR": "ERRO"}.get(level, level)
        color = {"INFO": ECO['text'], "WARNING": ECO['warning'], "ERROR": ECO['error']}.get(level, ECO['text'])
        self.log_area.append(f'<span style="color:{color};">[{tag}] {msg}</span>')

    def get_values(self) -> dict:
        return {
            "DB_HOST": self._parent_wizard.pg_host.text().strip(),
            "DB_PORT": str(self._parent_wizard.pg_port.value()),
            "DB_USER": self._parent_wizard.pg_user.text().strip(),
            "DB_PASSWORD": self._parent_wizard.pg_pass.text().strip(),
            "DB_NAME": self._parent_wizard.pg_db.text().strip(),
        }

    def _create_db(self):
        self.btn_step1.setEnabled(False)
        self.status.setText("Criando banco/usuario...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        self.log_area.clear()
        v = self.get_values()
        t = CreateDbThread(v["DB_HOST"], int(v["DB_PORT"]),
                           "postgres", v["DB_PASSWORD"],
                           v["DB_USER"], v["DB_PASSWORD"], v["DB_NAME"])
        t.log_signal.connect(self._log)
        t.finished.connect(self._on_db_created)
        self._parent_wizard._run_thread(t)

    def _on_db_created(self, ok, msg):
        self.btn_step1.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
            self.btn_step2.setEnabled(True)
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")

    def _run_migrations(self):
        self.btn_step2.setEnabled(False)
        self.status.setText("Executando migracoes...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        v = self.get_values()
        dsn = f"postgresql://{v['DB_USER']}:{v['DB_PASSWORD']}@{v['DB_HOST']}:{v['DB_PORT']}/{v['DB_NAME']}"
        t = PgMigrationsThread(dsn)
        t.log_signal.connect(self._log)
        t.finished.connect(self._on_migrations_done)
        self._parent_wizard._run_thread(t)

    def _on_migrations_done(self, ok, msg):
        self.btn_step2.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
            self.btn_step3.setEnabled(True)
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")

    def _seed_admin(self):
        self.btn_step3.setEnabled(False)
        self.status.setText("Criando admin...")
        self.status.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        v = self.get_values()
        dsn = f"postgresql://{v['DB_USER']}:{v['DB_PASSWORD']}@{v['DB_HOST']}:{v['DB_PORT']}/{v['DB_NAME']}"
        t = SeedAdminThread(dsn)
        t.log_signal.connect(self._log)
        t.finished.connect(self._on_admin_done)
        self._parent_wizard._run_thread(t)

    def _on_admin_done(self, ok, msg):
        self.btn_step3.setEnabled(True)
        if ok:
            self.status.setText("\u2714 " + msg)
            self.status.setStyleSheet(f"color: {ECO['success']}; font-weight: 600; background: transparent;")
        else:
            self.status.setText("\u2716 " + msg)
            self.status.setStyleSheet(f"color: {ECO['error']}; background: transparent;")


# ── Page 6: Review ──
class ReviewPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_wizard = parent
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Revisao e Salvamento"))
        layout.addWidget(QLabel("Confira os dados antes de salvar o arquivo .env."))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll_w = QWidget()
        scroll_w.setStyleSheet("background: transparent;")
        self.summary = QVBoxLayout(scroll_w)
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll, 1)

        self.file_info = QLabel("")
        self.file_info.setWordWrap(True)
        self.file_info.setStyleSheet(f"color: {ECO['text_sec']}; background: transparent;")
        layout.addWidget(self.file_info)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Salvar .env")
        self.btn_save.setProperty("success", True)
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        self.btn_launch = QPushButton("Salvar e Abrir ECOnnect")
        self.btn_launch.setStyleSheet(f"""
            QPushButton {{
                background-color: {ECO['orange']}; color: white;
                border: none; border-radius: 8px; padding: 10px 24px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #e07a10; }}
        """)
        self.btn_launch.clicked.connect(self._save_and_launch)
        btn_row.addWidget(self.btn_launch)
        layout.addLayout(btn_row)

    def on_enter(self):
        self._build_summary()

    def _build_summary(self):
        while self.summary.count():
            item = self.summary.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = [
            ("Firebird", [
                ("DSN", _norm_path(self._parent_wizard.fb_dsn.text())),
                ("Usuario", self._parent_wizard.fb_user.text().strip()),
            ]),
            ("PostgreSQL", [
                ("Host", self._parent_wizard.pg_host.text().strip()),
                ("Porta", str(self._parent_wizard.pg_port.value())),
                ("Usuario", self._parent_wizard.pg_user.text().strip()),
                ("Database", self._parent_wizard.pg_db.text().strip()),
            ]),
            ("Seguranca", [
                ("JWT Secret", self._get_jwt()[:20] + "..." if len(self._get_jwt()) > 20 else self._get_jwt()),
            ]),
        ]

        for title, pairs in sections:
            card = QFrame()
            card.setProperty("card", True)
            card_l = QVBoxLayout(card)
            h = QLabel(f"<b>{title}</b>")
            h.setStyleSheet(f"color: {ECO['blue_dark']}; font-size: 14px; background: transparent;")
            card_l.addWidget(h)
            for k, v in pairs:
                r = QHBoxLayout()
                kl = QLabel(k + ":")
                kl.setStyleSheet(f"color: {ECO['text_sec']}; font-weight: 600; background: transparent; min-width: 80px;")
                vl = QLabel(str(v))
                vl.setStyleSheet(f"color: {ECO['text']}; background: transparent;")
                r.addWidget(kl); r.addWidget(vl, 1); card_l.addLayout(r)
            self.summary.addWidget(card)

        env_path = RESOLVED.get("env")
        exe_path = RESOLVED.get("econnect_exe")
        parts = []
        if env_path:
            e = "EXISTE" if env_path.exists() else "SERA CRIADO"
            parts.append(f".env: {env_path} ({e})")
        if exe_path:
            e = "ENCONTRADO" if exe_path.exists() else "NAO ENCONTRADO"
            parts.append(f"ECOnnect.exe: {exe_path} ({e})")
        self.file_info.setText("<br>".join(parts))
        self.summary.addStretch()

    def _get_jwt(self):
        return self._parent_wizard._gen_jwt() if not hasattr(self._parent_wizard, '_jwt_val') else self._parent_wizard._jwt_val

    def _save(self):
        vals = {
            "DB_HOST": self._parent_wizard.pg_host.text().strip(),
            "DB_PORT": str(self._parent_wizard.pg_port.value()),
            "DB_USER": self._parent_wizard.pg_user.text().strip(),
            "DB_PASSWORD": self._parent_wizard.pg_pass.text().strip(),
            "DB_NAME": self._parent_wizard.pg_db.text().strip(),
            "JWT_SECRET": self._get_jwt(),
            "FB_DATABASE": _norm_path(self._parent_wizard.fb_dsn.text()),
            "FB_USER": self._parent_wizard.fb_user.text().strip(),
            "FB_PASSWORD": self._parent_wizard.fb_pass.text().strip(),
        }
        _write_env(vals)
        self.file_info.setText(f".env salvo em:\n{RESOLVED['env']}")

    def _save_and_launch(self):
        self._save()
        exe = RESOLVED.get("econnect_exe")
        if exe and exe.exists():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            QApplication.quit()
        else:
            QMessageBox.warning(self, "ECOnnect nao encontrado",
                f"ECOnnect.exe nao encontrado em:\n{exe}\n\n"
                "O .env foi salvo. Execute o ECOnnect manualmente.")


# ── Page 7: Done ──
class DonePage(WizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icon = QLabel("\u2714")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"""
            font-size: 64px;
            color: {ECO['success']};
            background: {ECO['surface']};
            border-radius: 40px;
            padding: 20px;
            max-width: 80px;
            margin: 0 auto;
        """)
        layout.addWidget(icon, 0, Qt.AlignCenter)

        title = QLabel("Configuracao Concluida!")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Seu ambiente ECOnnect esta pronto para uso.")
        sub.setProperty("subheading", True)
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        btn = QPushButton("Abrir ECOnnect")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ECO['orange']}; color: white;
                border: none; border-radius: 8px; padding: 14px 40px;
                font-size: 16px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #e07a10; }}
        """)
        btn.clicked.connect(self._launch)
        layout.addWidget(btn, 0, Qt.AlignCenter)

    def _launch(self):
        exe = RESOLVED.get("econnect_exe")
        if exe and exe.exists():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            QApplication.quit()
        else:
            QMessageBox.warning(self, "ECOnnect nao encontrado",
                f"ECOnnect.exe nao encontrado em:\n{exe}")


# ── THREADS ──

class SimpleLog:
    def __init__(self, callback: Callable):
        self._cb = callback
    def log(self, msg, level="INFO"):
        if self._cb:
            self._cb(f"[{level}] {msg}")


class TestFbThread(QThread):
    finished = Signal(bool, str)
    def __init__(self, dsn, user, password):
        super().__init__()
        self.dsn = dsn; self.user = user; self.password = password
    def run(self):
        try:
            import fdb
            conn = fdb.connect(dsn=self.dsn, user=self.user, password=self.password, charset="WIN1252")
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM RDB$DATABASE")
            cur.fetchone(); cur.close(); conn.close()
            self.finished.emit(True, f"Conectado ao Firebird")
        except Exception as e:
            self.finished.emit(False, str(e))


class TestPgThread(QThread):
    finished = Signal(bool, str)
    def __init__(self, host, port, user, password, database):
        super().__init__()
        self.host = host; self.port = port; self.user = user
        self.password = password; self.database = database
    def run(self):
        try:
            import asyncio; import asyncpg
            async def _test():
                dsn = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
                conn = await asyncpg.connect(dsn, timeout=5)
                ver = await conn.fetchval("SELECT version()")
                await conn.close()
                return ver
            ver = asyncio.run(_test())
            self.finished.emit(True, f"Conectado! {ver.split(',')[0]}")
        except Exception as e:
            self.finished.emit(False, str(e))


class CreateDbThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)
    def __init__(self, host, port, superuser, superpass, db_user, db_pass, db_name):
        super().__init__()
        self.host = host; self.port = port; self.superuser = superuser
        self.superpass = superpass; self.db_user = db_user
        self.db_pass = db_pass; self.db_name = db_name
    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            import asyncio; import asyncpg
            async def _create():
                dsn = f"postgresql://{self.superuser}:{self.superpass}@{self.host}:{self.port}/postgres"
                slog.log(f"Conectando como superuser...")
                conn = await asyncpg.connect(dsn, timeout=5)
                exists_user = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", self.db_user)
                if not exists_user:
                    await conn.execute(f'CREATE USER "{self.db_user}" WITH PASSWORD $1', self.db_pass)
                    slog.log(f"Usuario '{self.db_user}' criado")
                else:
                    await conn.execute(f'ALTER USER "{self.db_user}" WITH PASSWORD $1', self.db_pass)
                    slog.log(f"Senha do usuario '{self.db_user}' atualizada")
                exists_db = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", self.db_name)
                if not exists_db:
                    await conn.execute(f'CREATE DATABASE "{self.db_name}" OWNER "{self.db_user}"')
                    slog.log(f"Database '{self.db_name}' criado")
                else:
                    slog.log(f"Database '{self.db_name}' ja existe")
                await conn.close()
                dsn2 = f"postgresql://{self.db_user}:{self.db_pass}@{self.host}:{self.port}/{self.db_name}"
                conn2 = await asyncpg.connect(dsn2, timeout=5)
                await conn2.execute("CREATE TABLE IF NOT EXISTS _econnect_test (id SERIAL PRIMARY KEY)")
                await conn2.execute("DROP TABLE _econnect_test")
                await conn2.close()
                slog.log("Conexao de testes OK")
            asyncio.run(_create())
            self.finished.emit(True, "Banco/usuário criados com sucesso!")
        except Exception as e:
            slog.log(f"ERRO: {e}", "ERROR")
            self.finished.emit(False, str(e))


class FbSetupThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)
    def __init__(self, dsn, user, password):
        super().__init__()
        self.dsn = dsn; self.user = user; self.password = password
    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            from backend.app.migrations import ensure_firebird_tables, seed_firebird_autonomias
            ensure_firebird_tables(self.dsn, self.user, self.password, slog.log)
            seed_firebird_autonomias(self.dsn, self.user, self.password, slog.log)
            self.finished.emit(True, "Firebird preparado com sucesso!")
        except Exception as e:
            slog.log(str(e), "ERROR")
            self.finished.emit(False, str(e))


class PgMigrationsThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)
    def __init__(self, dsn):
        super().__init__()
        self.dsn = dsn

    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime, ForeignKey, Integer
            from sqlalchemy.orm import declarative_base
            from sqlalchemy.dialects.postgresql import UUID, JSON
            from backend.app.migrations import run_pg_migrations
            import uuid as _uuid
            from datetime import datetime, timezone

            Base = declarative_base()

            models = {}

            class User(Base):
                __tablename__ = "users"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                username = Column(String(50), unique=True, nullable=False, index=True)
                email = Column(String(255), unique=True, nullable=False)
                hashed_password = Column(String(255), nullable=False)
                role = Column(String(20), nullable=False, default="user")
                is_active = Column(Boolean, default=True)
                cobranca_cooldown_hours = Column(Integer, nullable=False, default=48)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                eco_usuario = Column(String(50), nullable=True, index=True)
                eco_empresa = Column(String(20), nullable=True)
                tab_permissions = Column(JSON, nullable=True)

            class Template(Base):
                __tablename__ = "templates"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                name = Column(String(100), nullable=False)
                body = Column(Text, nullable=False)
                description = Column(Text, nullable=True)
                parameter_count = Column(Integer, nullable=False, default=0)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                is_active = Column(Boolean, default=True)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
                eco_empresa = Column(String(20), nullable=True, index=True)
                meta_template_id = Column(String(100), nullable=True)
                meta_status = Column(String(20), nullable=True)

            class Request(Base):
                __tablename__ = "requests"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
                client_phone = Column(String(20), nullable=False)
                tag = Column(String(30), nullable=True)
                link = Column(Text, nullable=True)
                status = Column(String(20), nullable=False, default="pending")
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

            class RequestParameterValue(Base):
                __tablename__ = "request_parameter_values"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                request_id = Column(UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
                param_order = Column(Integer, nullable=False)
                param_label = Column(String(100), nullable=False)
                value = Column(Text, nullable=False)

            class IntegrationConfig(Base):
                __tablename__ = "integration_configs"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                name = Column(String(100), default="Manual")
                api_url = Column(String(255), nullable=False, default="")
                api_token = Column(String(255), nullable=False)
                flow_id = Column(String(50), nullable=False, default="")
                field_mapping = Column(JSON, nullable=False, default=dict)
                is_active = Column(Boolean, default=True)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
                first_name_field = Column(String(10), default="1")
                manual_payload = Column(Text, nullable=True)
                manual_headers = Column(JSON, nullable=True)
                schedule_enabled = Column(Boolean, default=False)
                schedule_preset = Column(String(20), nullable=True)
                schedule_days = Column(JSON, nullable=True, default=list)
                schedule_time = Column(String(5), nullable=True, default="09:00")
                last_run_at = Column(DateTime, nullable=True)
                next_run_at = Column(DateTime, nullable=True)
                type = Column(String(20), nullable=False, default="normal")
                eco_empresa = Column(String(20), nullable=True, index=True)

            class AuditLog(Base):
                __tablename__ = "audit_logs"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
                username = Column(String(100), nullable=False)
                action = Column(String(100), nullable=False)
                entity_type = Column(String(50), nullable=True)
                entity_id = Column(String(100), nullable=True)
                details = Column(JSON, nullable=True)
                ip_address = Column(String(45), nullable=True)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

            class CompanyConfig(Base):
                __tablename__ = "company_configs"
                company_code = Column(String(20), primary_key=True)
                fb_database = Column(String(500), nullable=False, default="")
                fb_user = Column(String(50), nullable=False, default="")
                fb_password = Column(String(100), nullable=False, default="")
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

            class MetaCredentials(Base):
                __tablename__ = "meta_credentials"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                eco_empresa = Column(String(20), nullable=True, index=True, unique=True)
                waba_id = Column(String(100), nullable=False)
                phone_number_id = Column(String(100), nullable=False)
                access_token = Column(Text, nullable=False)
                is_verified = Column(Boolean, default=False)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

            class MetaMessage(Base):
                __tablename__ = "meta_messages"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                eco_empresa = Column(String(20), nullable=True, index=True)
                from_phone = Column(String(20), nullable=False)
                to_phone = Column(String(20), nullable=False)
                direction = Column(String(10), nullable=False)
                template_name = Column(String(100), nullable=True)
                body = Column(Text, nullable=True)
                meta_message_id = Column(String(100), nullable=True)
                status = Column(String(20), nullable=False, default="sent")
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

            class SqlVariable(Base):
                __tablename__ = "sql_variables"
                id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
                name = Column(String(100), nullable=False)
                label = Column(String(200), nullable=True)
                sql_query = Column(Text, nullable=False)
                value_column = Column(Integer, nullable=True)
                company_code = Column(String(20), nullable=False, index=True)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
                created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
                updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

            eng = create_engine(self.dsn, echo=False)
            slog.log("Criando tabelas...")
            Base.metadata.create_all(eng)
            eng.dispose()
            slog.log("Tabelas criadas")

            run_pg_migrations(self.dsn, slog.log)
            self.finished.emit(True, "Migracoes concluidas!")
        except Exception as e:
            import traceback
            slog.log(str(e), "ERROR")
            for line in traceback.format_exc().splitlines():
                slog.log(line, "ERROR")
            self.finished.emit(False, str(e))


class SeedAdminThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)
    def __init__(self, dsn):
        super().__init__()
        self.dsn = dsn
    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            from backend.app.migrations import seed_admin_user
            seed_admin_user(self.dsn, log_fn=slog.log)
            self.finished.emit(True, "Admin verificado/criado!")
        except Exception as e:
            slog.log(str(e), "ERROR")
            self.finished.emit(False, str(e))


# ── MAIN WINDOW ──

class ConfiguradorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECOnnect Configurador")
        self.setMinimumSize(820, 620)
        self._threads = []
        self._jwt_val = ""
        self._build_ui()
        self._load_defaults()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._steps = [
            "Boas-vindas", "Firebird\nConexao", "Firebird\nSetup",
            "PostgreSQL\nConexao", "PostgreSQL\nSetup", "Revisao", "Concluido"
        ]
        self._indicator = StepIndicator(self._steps)
        self._indicator.setStyleSheet(f"background: {ECO['surface']}; border-right: 1px solid {ECO['border']};")
        root.addWidget(self._indicator)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background: {ECO['blue_dark']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        logo = QLabel("ECOnnect Configurador")
        logo.setStyleSheet("color: white; font-weight: 700; font-size: 15px; background: transparent;")
        hl.addWidget(logo)
        hl.addStretch()
        self._step_title = QLabel("Passo 1 de 7")
        self._step_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px; background: transparent;")
        hl.addWidget(self._step_title)
        right.addWidget(header)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {ECO['bg']};")
        self._pages = [
            WelcomePage(self),
            FirebirdPage(self),
            FirebirdSetupPage(self),
            PostgresPage(self),
            PostgresSetupPage(self),
            ReviewPage(self),
            DonePage(self),
        ]
        for page in self._pages:
            self._stack.addWidget(page)
        right.addWidget(self._stack, 1)

        nav = QWidget()
        nav.setFixedHeight(52)
        nav.setStyleSheet(f"background: {ECO['surface']}; border-top: 1px solid {ECO['border']};")
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(16, 8, 16, 8)

        self._back_btn = QPushButton("Voltar")
        self._back_btn.setProperty("ghost", True)
        self._back_btn.clicked.connect(self._prev)
        nl.addWidget(self._back_btn)
        nl.addStretch()
        self._next_btn = QPushButton("Proximo")
        self._next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ECO['blue']}; color: white;
                border: none; border-radius: 6px; padding: 8px 24px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {ECO['blue_dark']}; }}
            QPushButton:disabled {{
                background-color: #b0c4de; color: #e0e0e0;
            }}
        """)
        self._next_btn.clicked.connect(self._next)
        nl.addWidget(self._next_btn)
        right.addWidget(nav)

        root.addLayout(right, 1)
        self._update_nav()

    def _load_defaults(self):
        _resolve_paths()
        vals = _read_env_example()

        fb_page = self._pages[1]
        if vals.get("FB_DATABASE"): fb_page.fb_dsn.setText(vals["FB_DATABASE"])
        if vals.get("FB_USER"): fb_page.fb_user.setText(vals["FB_USER"])
        if vals.get("FB_PASSWORD"): fb_page.fb_pass.setText(vals["FB_PASSWORD"])

        pg_page = self._pages[3]
        if vals.get("DB_HOST"): pg_page.pg_host.setText(vals["DB_HOST"])
        if vals.get("DB_PORT"):
            try: pg_page.pg_port.setValue(int(vals["DB_PORT"]))
            except ValueError: pass
        if vals.get("DB_USER"): pg_page.pg_user.setText(vals["DB_USER"])
        if vals.get("DB_PASSWORD"): pg_page.pg_pass.setText(vals["DB_PASSWORD"])
        if vals.get("DB_NAME"): pg_page.pg_db.setText(vals["DB_NAME"])

        if vals.get("JWT_SECRET"): self._jwt_val = vals["JWT_SECRET"]
        else: self._jwt_val = uuid_mod.uuid4().hex + uuid_mod.uuid4().hex

    def _gen_jwt(self) -> str:
        if not self._jwt_val:
            self._jwt_val = uuid_mod.uuid4().hex + uuid_mod.uuid4().hex
        return self._jwt_val

    # ── Wizard navigation ──
    @property
    def fb_dsn(self): return self._pages[1].fb_dsn
    @property
    def fb_user(self): return self._pages[1].fb_user
    @property
    def fb_pass(self): return self._pages[1].fb_pass
    @property
    def pg_host(self): return self._pages[3].pg_host
    @property
    def pg_port(self): return self._pages[3].pg_port
    @property
    def pg_user(self): return self._pages[3].pg_user
    @property
    def pg_pass(self): return self._pages[3].pg_pass
    @property
    def pg_db(self): return self._pages[3].pg_db

    def _current_idx(self):
        return self._stack.currentIndex()

    def _update_nav(self):
        idx = self._current_idx()
        total = len(self._pages)
        self._step_title.setText(f"Passo {idx + 1} de {total}")
        self._back_btn.setVisible(idx > 0 and idx < total - 1)
        if idx == 0:
            self._next_btn.setText("Proximo")
            self._next_btn.setVisible(True)
        elif idx == total - 1:
            self._next_btn.setVisible(False)
        elif idx == total - 2:
            self._next_btn.setVisible(False)
        else:
            self._next_btn.setText("Proximo")
            self._next_btn.setVisible(True)

    def next_step(self):
        idx = self._current_idx()
        if idx < len(self._pages) - 1:
            self._indicator.set_completed(idx)
            self._stack.setCurrentIndex(idx + 1)
            self._indicator.set_current(idx + 1)
            page = self._pages[idx + 1]
            if hasattr(page, "on_enter"):
                page.on_enter()
            self._update_nav()

    def _next(self):
        idx = self._current_idx()
        page = self._pages[idx]
        if not page.validate():
            return
        if idx < len(self._pages) - 1:
            self._indicator.set_completed(idx)
            nxt = idx + 1
            self._stack.setCurrentIndex(nxt)
            self._indicator.set_current(nxt)
            page = self._pages[nxt]
            if hasattr(page, "on_enter"):
                page.on_enter()
            self._update_nav()

    def _prev(self):
        idx = self._current_idx()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._indicator.set_current(idx - 1)
            self._update_nav()

    def _run_thread(self, thread: QThread):
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.start()


def main():
    _resolve_paths()
    app = QApplication(sys.argv)
    app.setApplicationName("ECOnnect Configurador")
    app.setStyleSheet(STYLES)

    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    icon_path = bundled / "frontend" / "assets" / "app_icon.ico"
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    window = ConfiguradorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
