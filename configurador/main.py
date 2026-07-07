import sys
import os
import subprocess
import uuid as uuid_mod
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox,
    QGroupBox, QSpinBox, QProgressBar, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal

_RESOLVED = {}
_ENV_LINES = []


def _resolve_paths():
    if getattr(sys, "frozen", False):
        parent = Path(sys.executable).parent.resolve()
    else:
        parent = Path(__file__).parent.parent / "dist"
        parent.mkdir(parents=True, exist_ok=True)
    _RESOLVED["exe"] = parent
    _RESOLVED["env"] = parent / ".env"
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    for cand in [bundled / ".env.example", bundled / "backend" / ".env.example"]:
        if cand.exists():
            _RESOLVED["example"] = cand
            break
    _RESOLVED["econnect_exe"] = parent / "ECOnnect.exe"
    if not _RESOLVED["econnect_exe"].exists():
        _RESOLVED["econnect_exe"] = parent.parent / "ECOnnect.exe"


def _read_env_example() -> dict:
    defaults = {}
    path = _RESOLVED.get("example")
    if path and path.exists():
        text = path.read_text(encoding="utf-8")
        _ENV_LINES.clear()
        for line in text.splitlines():
            _ENV_LINES.append(line)
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                defaults[k.strip()] = v.strip()
    return defaults


def _write_env(values: dict):
    lines = _ENV_LINES[:]
    new_lines = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in values and values[k] is not None:
                new_lines.append(f"{k}={values[k]}")
                continue
        new_lines.append(line)
    env_path = _RESOLVED["env"]
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return env_path


# ── THREADS ──────────────────────────────────────────────────────────

class SimpleLog:
    def __init__(self, callback):
        self._cb = callback
    def log(self, msg, level="INFO"):
        if self._cb:
            self._cb(f"[{level}] {msg}")


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
            self.finished.emit(True, f"Conectado! PostgreSQL: {ver}")
        except Exception as e:
            self.finished.emit(False, str(e))


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
            self.finished.emit(True, f"Conectado ao Firebird: {self.dsn}")
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
                slog.log(f"Conectando como superuser em {self.host}:{self.port}...")
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
            import traceback
            slog.log(f"ERRO: {e}", "ERROR")
            for line in traceback.format_exc().splitlines():
                slog.log(line, "ERROR")
            self.finished.emit(False, str(e))


class RunPgMigrationsThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)

    def __init__(self, host, port, user, password, database):
        super().__init__()
        self.host = host; self.port = port; self.user = user
        self.password = password; self.database = database

    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            import asyncio
            from sqlalchemy import create_engine, text as sa_text
            from sqlalchemy.orm import declarative_base

            dsn = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
            slog.log(f"Conectando a {self.host}:{self.port}/{self.database}...")
            eng = create_engine(dsn, echo=False)

            Base = declarative_base()

            import uuid
            from datetime import datetime
            from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
            from sqlalchemy.dialects.postgresql import UUID, JSON

            class User(Base):
                __tablename__ = "users"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                username = Column(String(50), unique=True, nullable=False, index=True)
                email = Column(String(255), unique=True, nullable=False)
                hashed_password = Column(String(255), nullable=False)
                role = Column(String(20), nullable=False, default="user")
                is_active = Column(Boolean, default=True)
                cobranca_cooldown_hours = Column(Integer, nullable=False, default=48)
                created_at = Column(DateTime, default=datetime.utcnow)
                eco_usuario = Column(String(50), nullable=True, index=True)
                eco_empresa = Column(String(20), nullable=True)
                tab_permissions = Column(JSON, nullable=True)

            class Template(Base):
                __tablename__ = "templates"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                name = Column(String(100), nullable=False)
                body = Column(Text, nullable=False)
                description = Column(Text, nullable=True)
                parameter_count = Column(Integer, nullable=False, default=0)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                is_active = Column(Boolean, default=True)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
                eco_empresa = Column(String(20), nullable=True, index=True)
                meta_template_id = Column(String(100), nullable=True)
                meta_status = Column(String(20), nullable=True)

            class Request(Base):
                __tablename__ = "requests"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
                client_phone = Column(String(20), nullable=False)
                tag = Column(String(30), nullable=True)
                link = Column(Text, nullable=True)
                status = Column(String(20), nullable=False, default="pending")
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            class RequestParameterValue(Base):
                __tablename__ = "request_parameter_values"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                request_id = Column(UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
                param_order = Column(Integer, nullable=False)
                param_label = Column(String(100), nullable=False)
                value = Column(Text, nullable=False)

            class IntegrationConfig(Base):
                __tablename__ = "integration_configs"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
                name = Column(String(100), default="Manual")
                api_url = Column(String(255), nullable=False, default="")
                api_token = Column(String(255), nullable=False)
                flow_id = Column(String(50), nullable=False, default="")
                field_mapping = Column(JSON, nullable=False, default=dict)
                is_active = Column(Boolean, default=True)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
                username = Column(String(100), nullable=False)
                action = Column(String(100), nullable=False)
                entity_type = Column(String(50), nullable=True)
                entity_id = Column(String(100), nullable=True)
                details = Column(JSON, nullable=True)
                ip_address = Column(String(45), nullable=True)
                created_at = Column(DateTime, default=datetime.utcnow)

            class CompanyConfig(Base):
                __tablename__ = "company_configs"
                company_code = Column(String(20), primary_key=True)
                fb_database = Column(String(500), nullable=False, default="")
                fb_user = Column(String(50), nullable=False, default="")
                fb_password = Column(String(100), nullable=False, default="")
                updated_at = Column(DateTime, default=datetime.utcnow)

            class MetaCredentials(Base):
                __tablename__ = "meta_credentials"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                eco_empresa = Column(String(20), nullable=True, index=True, unique=True)
                waba_id = Column(String(100), nullable=False)
                phone_number_id = Column(String(100), nullable=False)
                access_token = Column(Text, nullable=False)
                is_verified = Column(Boolean, default=False)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            class MetaMessage(Base):
                __tablename__ = "meta_messages"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                eco_empresa = Column(String(20), nullable=True, index=True)
                from_phone = Column(String(20), nullable=False)
                to_phone = Column(String(20), nullable=False)
                direction = Column(String(10), nullable=False)
                template_name = Column(String(100), nullable=True)
                body = Column(Text, nullable=True)
                meta_message_id = Column(String(100), nullable=True)
                status = Column(String(20), nullable=False, default="sent")
                created_at = Column(DateTime, default=datetime.utcnow)

            class SqlVariable(Base):
                __tablename__ = "sql_variables"
                id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                name = Column(String(100), nullable=False)
                label = Column(String(200), nullable=True)
                sql_query = Column(Text, nullable=False)
                value_column = Column(Integer, nullable=True)
                company_code = Column(String(20), nullable=False, index=True)
                created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            all_models = [User, Template, Request, RequestParameterValue,
                          IntegrationConfig, AuditLog, CompanyConfig,
                          MetaCredentials, MetaMessage, SqlVariable]

            slog.log("Criando tabelas...")
            Base.metadata.create_all(eng)
            slog.log("Tabelas criadas com sucesso! (sem seed de usuario — usa eco_login via Firebird)")
            eng.dispose()
            self.finished.emit(True, "Migracoes concluidas com sucesso!")
        except Exception as e:
            import traceback
            slog.log(f"ERRO: {e}", "ERROR")
            for line in traceback.format_exc().splitlines():
                slog.log(line, "ERROR")
            self.finished.emit(False, str(e))


class RunFbMigrationsThread(QThread):
    log_signal = Signal(str, str)
    finished = Signal(bool, str)

    def __init__(self, dsn, user, password):
        super().__init__()
        self.dsn = dsn; self.user = user; self.password = password

    def run(self):
        slog = SimpleLog(lambda m, l: self.log_signal.emit(m, l))
        try:
            import fdb
            slog.log(f"Conectando ao Firebird {self.dsn}...")
            conn = fdb.connect(dsn=self.dsn, user=self.user, password=self.password, charset="WIN1252")
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = 'BOLETO_GERADO'")
            exists = cur.fetchone()[0]
            if exists == 0:
                slog.log("Criando tabela BOLETO_GERADO...")
                cur.execute("""
                    CREATE TABLE BOLETO_GERADO (
                        EMPRESA         VARCHAR(10) NOT NULL,
                        PORTADOR        VARCHAR(10) NOT NULL,
                        NOSSONUMERO     VARCHAR(30) NOT NULL,
                        IDPARCELA       INTEGER,
                        NUMEROBOLETO    VARCHAR(30),
                        CODIGOBARRAS    VARCHAR(44),
                        LINHADIGITAVEL  VARCHAR(60),
                        CAMINHOPDF      VARCHAR(500),
                        DATAGERACAO     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (EMPRESA, PORTADOR, NOSSONUMERO)
                    )
                """)
                conn.commit()
                slog.log("Tabela BOLETO_GERADO criada com sucesso!")
            else:
                slog.log("Tabela BOLETO_GERADO ja existe")

            cur.close()
            conn.close()
            self.finished.emit(True, "Tabela Firebird criada com sucesso!")
        except Exception as e:
            import traceback
            slog.log(f"ERRO: {e}", "ERROR")
            for line in traceback.format_exc().splitlines():
                slog.log(line, "ERROR")
            self.finished.emit(False, str(e))


# ── UI ───────────────────────────────────────────────────────────────

class ConfiguradorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECOnnect Configurador")
        self.setMinimumSize(600, 650)
        self._threads = []
        self._build_ui()
        self._load_defaults()

    def _log_ui(self, msg, level="INFO"):
        if hasattr(self, '_log_area'):
            self._log_area.append(f"{msg}")

    def _build_ui(self):
        from PySide6.QtWidgets import QTextEdit
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        title = QLabel("<h2>ECOnnect — Configuração Inicial</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Preencha os dados abaixo. Use os botões para testar e preparar o ambiente.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── PostgreSQL ──
        pg = QGroupBox("PostgreSQL")
        pg_l = QFormLayout(pg)
        self.pg_host = QLineEdit("localhost")
        self.pg_port = QSpinBox(); self.pg_port.setRange(1, 65535); self.pg_port.setValue(5432)
        self.pg_user = QLineEdit("postgres")
        self.pg_pass = QLineEdit(); self.pg_pass.setEchoMode(QLineEdit.Password)
        self.pg_db = QLineEdit("econnect_db")
        pg_l.addRow("Host:", self.pg_host)
        pg_l.addRow("Porta:", self.pg_port)
        pg_l.addRow("Usuário:", self.pg_user)
        pg_l.addRow("Senha:", self.pg_pass)
        pg_l.addRow("Database:", self.pg_db)

        pg_btn = QHBoxLayout()
        self.btn_test_pg = QPushButton("Testar Conexão")
        self.btn_test_pg.clicked.connect(self._test_pg)
        self.btn_create_db = QPushButton("Criar DB/Usuário")
        self.btn_create_db.clicked.connect(self._create_db)
        self.btn_run_migrations = QPushButton("Criar Tabelas + Admin")
        self.btn_run_migrations.clicked.connect(self._run_pg_migrations)
        self.btn_run_migrations.setEnabled(False)
        pg_btn.addWidget(self.btn_test_pg)
        pg_btn.addWidget(self.btn_create_db)
        pg_btn.addWidget(self.btn_run_migrations)
        pg_l.addRow(pg_btn)

        self.pg_status = QLabel()
        self.pg_status.setWordWrap(True)
        pg_l.addRow(self.pg_status)
        layout.addWidget(pg)

        # ── Firebird ──
        fb = QGroupBox("Firebird")
        fb_l = QFormLayout(fb)
        self.fb_dsn = QLineEdit("C:\\ecosis\\dados\\ecodados.eco")
        self.fb_user = QLineEdit("SYSDBA")
        self.fb_pass = QLineEdit("masterkey")
        self.fb_pass.setEchoMode(QLineEdit.Password)
        fb_l.addRow("Database (dsn):", self.fb_dsn)
        fb_l.addRow("Usuário:", self.fb_user)
        fb_l.addRow("Senha:", self.fb_pass)

        fb_btn = QHBoxLayout()
        self.btn_test_fb = QPushButton("Testar Conexão")
        self.btn_test_fb.clicked.connect(self._test_fb)
        self.btn_fb_migration = QPushButton("Criar Tabela BOLETO_GERADO")
        self.btn_fb_migration.clicked.connect(self._run_fb_migrations)
        fb_btn.addWidget(self.btn_test_fb)
        fb_btn.addWidget(self.btn_fb_migration)
        fb_l.addRow(fb_btn)

        self.fb_status = QLabel()
        self.fb_status.setWordWrap(True)
        fb_l.addRow(self.fb_status)
        layout.addWidget(fb)

        # ── Boleto PDF (opcional) ──
        boleto = QGroupBox("Boleto PDF (opcional)")
        boleto_l = QVBoxLayout(boleto)
        self.chk_boleto = QCheckBox("Configurar leitura de boletos PDF via Firebird")
        self.chk_boleto.toggled.connect(self._on_boleto_toggle)
        boleto_l.addWidget(self.chk_boleto)
        self.boleto_info = QLabel(
            "Habilita o monitoramento de pastas para extrair dados de boletos PDF.\n"
            "Requer a tabela BOLETO_GERADO no Firebird e as configurações\n"
            "de empresa/portador no banco Firebird (TCOBPARAMETROECOBRANCA).\n\n"
            "Use o botão 'Criar Tabela BOLETO_GERADO' acima para criar a estrutura necessária."
        )
        self.boleto_info.setVisible(False)
        self.boleto_info.setWordWrap(True)
        boleto_l.addWidget(self.boleto_info)
        layout.addWidget(boleto)

        # ── Segurança ──
        sec = QGroupBox("Segurança")
        sec_l = QFormLayout(sec)
        jwt_row = QHBoxLayout()
        self.jwt_secret = QLineEdit()
        self.jwt_secret.setReadOnly(True)
        self.btn_gen_jwt = QPushButton("Gerar JWT Secret")
        self.btn_gen_jwt.clicked.connect(self._gen_jwt)
        jwt_row.addWidget(self.jwt_secret)
        jwt_row.addWidget(self.btn_gen_jwt)
        sec_l.addRow("JWT Secret:", jwt_row)
        layout.addWidget(sec)

        # ── Progress + Log ──
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMaximumHeight(150)
        self._log_area.setVisible(False)
        layout.addWidget(self._log_area)

        # ── Actions ──
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Salvar")
        self.btn_save.clicked.connect(self._save_only)
        self.btn_save_launch = QPushButton("Salvar e Abrir ECOnnect")
        self.btn_save_launch.clicked.connect(self._save_and_launch)
        self.btn_save_launch.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; }")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_save_launch)
        layout.addLayout(btn_row)

        self._path_label = QLabel()
        self._path_label.setTextFormat(Qt.RichText)
        self._path_label.setWordWrap(True)
        layout.addWidget(self._path_label)

    def _on_boleto_toggle(self, checked):
        self.boleto_info.setVisible(checked)
        self.btn_fb_migration.setEnabled(checked or self.btn_fb_migration.isEnabled())

    def _load_defaults(self):
        _resolve_paths()
        vals = _read_env_example()
        if vals.get("DB_HOST"): self.pg_host.setText(vals["DB_HOST"])
        if vals.get("DB_PORT"):
            try: self.pg_port.setValue(int(vals["DB_PORT"]))
            except ValueError: pass
        if vals.get("DB_USER"): self.pg_user.setText(vals["DB_USER"])
        if vals.get("DB_PASSWORD"): self.pg_pass.setText(vals["DB_PASSWORD"])
        if vals.get("DB_NAME"): self.pg_db.setText(vals["DB_NAME"])
        if vals.get("FB_DATABASE"): self.fb_dsn.setText(vals["FB_DATABASE"])
        if vals.get("FB_USER"): self.fb_user.setText(vals["FB_USER"])
        if vals.get("FB_PASSWORD"): self.fb_pass.setText(vals["FB_PASSWORD"])
        if vals.get("JWT_SECRET"): self.jwt_secret.setText(vals["JWT_SECRET"])
        else: self._gen_jwt()

        env_path = _RESOLVED.get("env")
        exe_path = _RESOLVED.get("econnect_exe")
        parts = []
        if env_path:
            e = "EXISTE" if env_path.exists() else "NÃO EXISTE"
            parts.append(f".env: <b>{env_path}</b> ({e})")
        if exe_path:
            e = "ENCONTRADO" if exe_path.exists() else "NÃO ENCONTRADO"
            parts.append(f"ECOnnect.exe: <b>{exe_path}</b> ({e})")
        self._path_label.setText("<br>".join(parts))

    def _get_values(self):
        return {
            "DB_HOST": self.pg_host.text().strip(),
            "DB_PORT": str(self.pg_port.value()),
            "DB_USER": self.pg_user.text().strip(),
            "DB_PASSWORD": self.pg_pass.text().strip(),
            "DB_NAME": self.pg_db.text().strip(),
            "JWT_SECRET": self.jwt_secret.text().strip(),
            "FB_DATABASE": self.fb_dsn.text().strip(),
            "FB_USER": self.fb_user.text().strip(),
            "FB_PASSWORD": self.fb_pass.text().strip(),
        }

    def _gen_jwt(self):
        self.jwt_secret.setText(uuid_mod.uuid4().hex + uuid_mod.uuid4().hex)

    def _set_enabled(self, enabled: bool):
        for w in [self.btn_save, self.btn_save_launch, self.btn_test_pg,
                  self.btn_test_fb, self.btn_create_db, self.btn_gen_jwt,
                  self.btn_run_migrations, self.btn_fb_migration]:
            w.setEnabled(enabled)
        self.progress.setVisible(not enabled)
        self._log_area.setVisible(not enabled)

    # ── PostgreSQL actions ──

    def _test_pg(self):
        self._set_enabled(False)
        self.pg_status.setText("Testando..."); self.pg_status.setStyleSheet("color: gray;")
        t = TestPgThread(self.pg_host.text().strip(), self.pg_port.value(),
                         self.pg_user.text().strip(), self.pg_pass.text().strip(),
                         self.pg_db.text().strip())
        t.finished.connect(lambda ok, msg: (self._set_enabled(True),
            self.pg_status.setText(msg), self.pg_status.setStyleSheet("color: green;" if ok else "color: red;"),
            self.btn_run_migrations.setEnabled(ok)))
        self._threads.append(t); t.start()

    def _create_db(self):
        self._set_enabled(False)
        self.pg_status.setText("Criando banco/usuário..."); self.pg_status.setStyleSheet("color: gray;")
        self._log_area.clear(); self._log_area.setVisible(True)
        self._log_area.append("[INFO] Iniciando criacao de banco/usuario...")
        t = CreateDbThread(self.pg_host.text().strip(), self.pg_port.value(),
                           "postgres", self.pg_pass.text().strip(),
                           self.pg_user.text().strip(), self.pg_pass.text().strip(),
                           self.pg_db.text().strip())
        t.log_signal.connect(lambda m, l: self._log_area.append(m))
        t.finished.connect(lambda ok, msg: (
            self._set_enabled(True),
            self.pg_status.setText(msg),
            self.pg_status.setStyleSheet("color: green;" if ok else "color: red;"),
            self.btn_run_migrations.setEnabled(ok),
        ))
        self._threads.append(t); t.start()

    def _run_pg_migrations(self):
        self._set_enabled(False)
        self._log_area.clear(); self._log_area.setVisible(True)
        self._log_area.append("[INFO] Iniciando migracoes PostgreSQL...")
        t = RunPgMigrationsThread(
            self.pg_host.text().strip(), self.pg_port.value(),
            self.pg_user.text().strip(), self.pg_pass.text().strip(),
            self.pg_db.text().strip(),
        )
        t.log_signal.connect(lambda m, l: self._log_area.append(m))
        t.finished.connect(lambda ok, msg: (
            self._set_enabled(True),
            self.pg_status.setText(msg),
            self.pg_status.setStyleSheet("color: green;" if ok else "color: red;"),
        ))
        self._threads.append(t); t.start()

    # ── Firebird actions ──

    def _test_fb(self):
        self._set_enabled(False)
        self.fb_status.setText("Testando..."); self.fb_status.setStyleSheet("color: gray;")
        t = TestFbThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.finished.connect(lambda ok, msg: (self._set_enabled(True),
            self.fb_status.setText(msg), self.fb_status.setStyleSheet("color: green;" if ok else "color: red;")))
        self._threads.append(t); t.start()

    def _run_fb_migrations(self):
        self._set_enabled(False)
        self._log_area.clear(); self._log_area.setVisible(True)
        self._log_area.append("[INFO] Iniciando migracoes Firebird...")
        t = RunFbMigrationsThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.log_signal.connect(lambda m, l: self._log_area.append(m))
        t.finished.connect(lambda ok, msg: (
            self._set_enabled(True),
            self.fb_status.setText(msg),
            self.fb_status.setStyleSheet("color: green;" if ok else "color: red;"),
        ))
        self._threads.append(t); t.start()

    # ── Save / Launch ──

    def _save(self) -> bool:
        vals = self._get_values()
        if not vals["DB_PASSWORD"]:
            QMessageBox.warning(self, "Atenção", "Preencha a senha do PostgreSQL.")
            return False
        if not vals["JWT_SECRET"]:
            QMessageBox.warning(self, "Atenção", "Gere um JWT Secret.")
            return False
        _write_env(vals)
        QMessageBox.information(self, "OK", f".env salvo em:\n{_RESOLVED['env']}")
        return True

    def _save_only(self):
        self._save()

    def _save_and_launch(self):
        if not self._save():
            return
        exe = _RESOLVED.get("econnect_exe")
        if exe and exe.exists():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            QApplication.quit()
        else:
            QMessageBox.warning(self, "ECOnnect não encontrado",
                f"ECOnnect.exe não encontrado em:\n{exe}\n\n"
                "O .env foi salvo. Execute o ECOnnect manualmente.")


def main():
    _resolve_paths()
    app = QApplication(sys.argv)
    app.setApplicationName("ECOnnect Configurador")

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
