import asyncio
import sys
import os
import datetime
import traceback as _tb_module
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import engine, Base, async_session
from .routers import auth, templates, requests, users, integrations, audit, company_config, sql_variables, dashboard, cobranca
from .models.integration import IntegrationConfig
from .models.audit_log import AuditLog
from .services.integration_service import IntegrationService


def _backend_log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        if getattr(sys, "frozen", False):
            log_file = Path(sys.executable).parent / "econnect.log"
        else:
            log_file = Path(__file__).parent.parent.parent / "econnect.log"
        with open(str(log_file), "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] backend: {msg}\n")
            f.flush()
    except Exception:
        pass


_backend_log("=== modulo backend.app.main carregado ===")

SCHEDULER_INTERVAL = 30
DB_RETRIES = 1
DB_RETRY_DELAY = 3


async def _run_migrations():
    _backend_log("[MIGRATION] Iniciando _run_migrations()...")
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users'
            """))
            existing_cols = {row[0] for row in result.fetchall()}
            _backend_log(f"[MIGRATION] users columns: {existing_cols}")

            if 'eco_usuario' not in existing_cols:
                await session.execute(text("ALTER TABLE users ADD COLUMN eco_usuario VARCHAR(50)"))
                _backend_log("[MIGRATION] users.eco_usuario adicionada")
            if 'eco_empresa' not in existing_cols:
                await session.execute(text("ALTER TABLE users ADD COLUMN eco_empresa VARCHAR(20)"))
                _backend_log("[MIGRATION] users.eco_empresa adicionada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration users: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'integration_configs'
            """))
            existing = {row[0] for row in result.fetchall()}
            _backend_log(f"[MIGRATION] integration_configs columns: {existing}")
            migs = [
                ('schedule_enabled', "BOOLEAN DEFAULT FALSE"),
                ('schedule_preset', "VARCHAR(20)"),
                ('schedule_days', "JSON DEFAULT '[]'"),
                ('schedule_time', "VARCHAR(5) DEFAULT '09:00'"),
                ('last_run_at', "TIMESTAMP"),
                ('next_run_at', "TIMESTAMP"),
                ('first_name_field', "VARCHAR(10) DEFAULT '1'"),
                ('manual_payload', "JSON"),
                ('manual_headers', "JSON"),
                ('name', "VARCHAR(100) DEFAULT 'Manual'"),
                ('type', "VARCHAR(20) DEFAULT 'normal'"),
            ]
            for col, dtype in migs:
                if col not in existing:
                    await session.execute(text(f"ALTER TABLE integration_configs ADD COLUMN {col} {dtype}"))
                    _backend_log(f"[MIGRATION] integration_configs.{col} adicionada")

            col_type_result = await session.execute(text("""
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'integration_configs' AND column_name = 'manual_payload'
            """))
            col_type = col_type_result.scalar()
            if col_type and col_type in ('json', 'jsonb'):
                await session.execute(text("ALTER TABLE integration_configs ALTER COLUMN manual_payload TYPE TEXT"))
                _backend_log("[MIGRATION] manual_payload convertido para TEXT")

            if 'template_id' in existing:
                try:
                    constr_result = await session.execute(text("""
                        SELECT conname FROM pg_constraint
                        WHERE conrelid = 'integration_configs'::regclass
                        AND confrelid = 'templates'::regclass
                        AND contype = 'f'
                    """))
                    fk_name = constr_result.scalar()
                    if fk_name:
                        await session.execute(text(f"ALTER TABLE integration_configs DROP CONSTRAINT {fk_name}"))
                        _backend_log(f"[MIGRATION] FK {fk_name} removida")
                except Exception:
                    pass
                await session.execute(text("ALTER TABLE integration_configs ALTER COLUMN template_id DROP NOT NULL"))
                _backend_log("[MIGRATION] template_id DROP NOT NULL")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration integration_configs: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'audit_logs'
            """))
            if not result.fetchone():
                await session.execute(text("""
                    CREATE TABLE audit_logs (
                        id UUID PRIMARY KEY,
                        user_id UUID REFERENCES users(id),
                        username VARCHAR(100) NOT NULL,
                        action VARCHAR(100) NOT NULL,
                        entity_type VARCHAR(50),
                        entity_id VARCHAR(100),
                        details JSON,
                        ip_address VARCHAR(45),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                _backend_log("[MIGRATION] Tabela audit_logs criada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration audit_logs: {e}", "WARNING")

    for table in ('integration_configs', 'templates'):
        async with async_session() as session:
            try:
                result = await session.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
                ), {"t": table})
                existing = {row[0] for row in result.fetchall()}
                if 'eco_empresa' not in existing:
                    await session.execute(text(f"ALTER TABLE {table} ADD COLUMN eco_empresa VARCHAR(20)"))
                    _backend_log(f"[MIGRATION] {table}.eco_empresa adicionada")
                await session.commit()
            except Exception as e:
                await session.rollback()
                _backend_log(f"[MIGRATION] Erro migration {table} eco_empresa: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_name = 'sql_variables'"
            ))
            if not result.fetchone():
                await session.execute(text("""
                    CREATE TABLE sql_variables (
                        id UUID PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        label VARCHAR(200),
                        sql_query TEXT NOT NULL,
                        company_code VARCHAR(20) NOT NULL,
                        created_by UUID REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await session.execute(text("CREATE INDEX ix_sql_variables_company_code ON sql_variables (company_code)"))
                _backend_log("[MIGRATION] Tabela sql_variables criada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration sql_variables: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns WHERE table_name = 'sql_variables'
            """))
            existing = {row[0] for row in result.fetchall()}
            if 'value_column' not in existing:
                await session.execute(text("ALTER TABLE sql_variables ADD COLUMN value_column INTEGER"))
                _backend_log("[MIGRATION] sql_variables.value_column adicionada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration sql_variables value_column: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns WHERE table_name = 'users'
            """))
            existing = {row[0] for row in result.fetchall()}
            if 'tab_permissions' not in existing:
                await session.execute(text("ALTER TABLE users ADD COLUMN tab_permissions JSON"))
                _backend_log("[MIGRATION] users.tab_permissions adicionada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration users.tab_permissions: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_name = 'company_configs'"
            ))
            if not result.fetchone():
                await session.execute(text("""
                    CREATE TABLE company_configs (
                        company_code VARCHAR(20) PRIMARY KEY,
                        fb_database VARCHAR(500) NOT NULL DEFAULT 'C:/ecosis/dados/ecodados.eco',
                        fb_user VARCHAR(50) NOT NULL DEFAULT 'SYSDBA',
                        fb_password VARCHAR(100) NOT NULL DEFAULT 'masterkey',
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                _backend_log("[MIGRATION] Tabela company_configs criada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration company_configs: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns WHERE table_name = 'templates'
            """))
            existing = {row[0] for row in result.fetchall()}
            if 'meta_template_id' not in existing:
                await session.execute(text("ALTER TABLE templates ADD COLUMN meta_template_id VARCHAR(100)"))
                _backend_log("[MIGRATION] templates.meta_template_id adicionada")
            if 'meta_status' not in existing:
                await session.execute(text("ALTER TABLE templates ADD COLUMN meta_status VARCHAR(20)"))
                _backend_log("[MIGRATION] templates.meta_status adicionada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration templates meta: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_name = 'meta_credentials'"
            ))
            if not result.fetchone():
                await session.execute(text("""
                    CREATE TABLE meta_credentials (
                        id UUID PRIMARY KEY,
                        eco_empresa VARCHAR(20) UNIQUE,
                        waba_id VARCHAR(100) NOT NULL,
                        phone_number_id VARCHAR(100) NOT NULL,
                        access_token TEXT NOT NULL,
                        is_verified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await session.execute(text("CREATE INDEX ix_meta_credentials_eco_empresa ON meta_credentials (eco_empresa)"))
                _backend_log("[MIGRATION] Tabela meta_credentials criada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration meta_credentials: {e}", "WARNING")

    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_name = 'meta_messages'"
            ))
            if not result.fetchone():
                await session.execute(text("""
                    CREATE TABLE meta_messages (
                        id UUID PRIMARY KEY,
                        eco_empresa VARCHAR(20),
                        from_phone VARCHAR(20) NOT NULL,
                        to_phone VARCHAR(20) NOT NULL,
                        direction VARCHAR(10) NOT NULL,
                        template_name VARCHAR(100),
                        body TEXT,
                        meta_message_id VARCHAR(100),
                        status VARCHAR(20) DEFAULT 'sent',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await session.execute(text("CREATE INDEX ix_meta_messages_eco_empresa ON meta_messages (eco_empresa)"))
                _backend_log("[MIGRATION] Tabela meta_messages criada")
            await session.commit()
        except Exception as e:
            await session.rollback()
            _backend_log(f"[MIGRATION] Erro migration meta_messages: {e}", "WARNING")

    _backend_log("[MIGRATION] _run_migrations() concluido")


async def _ensure_permissions():
    from .config import settings as _settings
    _urls = [
        f"postgresql+asyncpg://postgres:postgres@{_settings.DB_HOST}:{_settings.DB_PORT}/{_settings.DB_NAME}?ssl=disable",
        f"postgresql+asyncpg://postgres@localhost:{_settings.DB_PORT}/{_settings.DB_NAME}?ssl=disable",
    ]
    for _url in _urls:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine as _cae
            _eng = _cae(_url)
            async with _eng.begin() as _conn:
                await _conn.execute(text(f'GRANT ALL ON SCHEMA public TO "{_settings.DB_USER}"'))
                await _conn.execute(text(f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{_settings.DB_USER}"'))
                await _conn.execute(text(f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{_settings.DB_USER}"'))
                await _conn.execute(text(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{_settings.DB_USER}"'))
            await _eng.dispose()
            _backend_log(f"[DB] Permissoes garantidas para '{_settings.DB_USER}'!")
            return
        except Exception:
            pass


async def _scheduler_loop():
    while True:
        try:
            async with async_session() as session:
                service = IntegrationService(session)
                due = await service.get_due()
                for config in due:
                    try:
                        await service.trigger(config.id)
                    except Exception as e:
                        _backend_log(f"[Scheduler] Erro ao executar integracao {config.id}: {e}", "ERROR")
        except Exception as e:
            _backend_log(f"[Scheduler] Erro no ciclo: {e}", "ERROR")
        await asyncio.sleep(SCHEDULER_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _backend_log("[LIFESPAN] === LIFESPAN INICIADO ===")
    from .config import settings as _settings

    db_url_preview = _settings.DATABASE_URL.replace(_settings.DB_PASSWORD, "****")
    _backend_log(f"[LIFESPAN] DB_URL = {db_url_preview}")
    _backend_log(f"[LIFESPAN] DB_RETRIES = {DB_RETRIES}, DB_RETRY_DELAY = {DB_RETRY_DELAY}")

    last_exc = None
    for attempt in range(1, DB_RETRIES + 1):
        _backend_log(f"[LIFESPAN] engine.begin() tentativa {attempt}/{DB_RETRIES}...")
        t0 = datetime.datetime.now()
        try:
            async with engine.begin() as conn:
                _backend_log(f"[LIFESPAN] engine.begin() OK em {(datetime.datetime.now()-t0).total_seconds():.2f}s")
                _backend_log(f"[LIFESPAN] Executando Base.metadata.create_all...")
                await conn.run_sync(Base.metadata.create_all)
                _backend_log(f"[LIFESPAN] Base.metadata.create_all OK")
            last_exc = None
            break
        except Exception as e:
            elapsed = (datetime.datetime.now() - t0).total_seconds()
            last_exc = e
            err_str = str(e).rstrip(".!")
            tb_str = _tb_module.format_exc()
            _backend_log(f"[LIFESPAN] engine.begin() FALHOU apos {elapsed:.2f}s (attempt {attempt}/{DB_RETRIES})", "ERROR")
            _backend_log(f"[LIFESPAN] Erro: {err_str}", "ERROR")
            for line in tb_str.splitlines():
                _backend_log(f"[LIFESPAN] TRACEBACK: {line}", "ERROR")
            if attempt < DB_RETRIES:
                _backend_log(f"[LIFESPAN] Nova tentativa em {DB_RETRY_DELAY}s...")
                await asyncio.sleep(DB_RETRY_DELAY)

    if last_exc:
        _backend_log(f"[LIFESPAN] Todas as tentativas falharam. Iniciando fallback...", "WARNING")
        from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
        from .config import settings as _settings
        _fb_urls = [
            f"postgresql+asyncpg://postgres:postgres@{_settings.DB_HOST}:{_settings.DB_PORT}/postgres?ssl=disable",
            f"postgresql+asyncpg://postgres@localhost:{_settings.DB_PORT}/postgres?ssl=disable",
        ]
        _fb_success = False
        for idx, _fb_url in enumerate(_fb_urls):
            if _fb_success:
                break
            _backend_log(f"[LIFESPAN] Fallback {idx+1}/{len(_fb_urls)}: {_fb_url.replace('postgres:postgres', 'postgres:****')}", "WARNING")
            try:
                _fb_engine = _create_async_engine(_fb_url)
                async with _fb_engine.begin() as _conn:
                    await _conn.execute(text("SELECT 1"))
                    _backend_log("[LIFESPAN] Fallback conectou ao PostgreSQL superuser!")
                    _user_exists = await _conn.execute(
                        text(f"SELECT 1 FROM pg_roles WHERE rolname='{_settings.DB_USER}'")
                    )
                    if not _user_exists.scalar():
                        await _conn.execute(text(f'CREATE USER "{_settings.DB_USER}" WITH PASSWORD \'{_settings.DB_PASSWORD}\''))
                        _backend_log(f"[LIFESPAN] Usuario '{_settings.DB_USER}' criado!")
                    await _conn.execute(text(f'ALTER USER "{_settings.DB_USER}" WITH PASSWORD \'{_settings.DB_PASSWORD}\''))
                    _backend_log(f"[LIFESPAN] Usuario '{_settings.DB_USER}' senha atualizada!")
                    _db_exists = await _conn.execute(
                        text(f"SELECT 1 FROM pg_database WHERE datname='{_settings.DB_NAME}'")
                    )
                    if not _db_exists.scalar():
                        await _conn.execute(text(f'CREATE DATABASE "{_settings.DB_NAME}" OWNER "{_settings.DB_USER}"'))
                        _backend_log(f"[LIFESPAN] Database '{_settings.DB_NAME}' criado!")
                await _fb_engine.dispose()
                _new_db_url = f"postgresql+asyncpg://{_settings.DB_USER}:{_settings.DB_PASSWORD}@{_settings.DB_HOST}:{_settings.DB_PORT}/{_settings.DB_NAME}?ssl=disable"
                _new_engine = _create_async_engine(_new_db_url)
                async with _new_engine.begin() as _conn:
                    await _conn.run_sync(Base.metadata.create_all)
                await _new_engine.dispose()
                _backend_log("[LIFESPAN] Conexao estabelecida apos fallback!")
                _fb_success = True
                last_exc = None
            except Exception as _fb_err:
                _fb_tb = _tb_module.format_exc()
                _backend_log(f"[LIFESPAN] Fallback {idx+1} falhou: {_fb_err}", "ERROR")
                for line in _fb_tb.splitlines():
                    _backend_log(f"[LIFESPAN] FALLBACK_TRACEBACK: {line}", "ERROR")

        if last_exc:
            err_msg = str(last_exc).rstrip(".!")
            _backend_log(f"[LIFESPAN] NAO FOI POSSIVEL CONECTAR AO POSTGRESQL", "CRITICAL")
            _backend_log(f"[LIFESPAN] URL: {db_url_preview}", "CRITICAL")
            _backend_log(f"[LIFESPAN] Erro final: {err_msg}", "CRITICAL")
            _backend_log(f"[LIFESPAN] Verifique: (1) PostgreSQL rodando em localhost:{_settings.DB_PORT}", "CRITICAL")
            _backend_log(f"[LIFESPAN] (2) Usuario 'postgres' existe (senha 'postgres' ou vazia)", "CRITICAL")
            _backend_log(f"[LIFESPAN] (3) Database '{_settings.DB_NAME}' existe", "CRITICAL")
            for line in _tb_module.format_exc().splitlines():
                _backend_log(f"[LIFESPAN] TRACEBACK_FINAL: {line}", "CRITICAL")
            raise last_exc

    _backend_log("[LIFESPAN] Conectado ao PostgreSQL. Rodando migrations...")
    await _run_migrations()
    await _ensure_permissions()

    _backend_log("[LIFESPAN] Iniciando scheduler...")
    scheduler_task = asyncio.create_task(_scheduler_loop())

    _backend_log("[LIFESPAN] Lifspan pronto! Servidor aceitando requisicoes.")
    yield

    _backend_log("[LIFESPAN] Encerrando lifespan...")
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    _backend_log("[LIFESPAN] Lifespan encerrado")


app = FastAPI(title="ECOnnect API", lifespan=lifespan)
_backend_log("[APP] FastAPI app criada com lifespan")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_backend_log("[APP] CORS middleware adicionado")

app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(requests.router)
app.include_router(users.router)
app.include_router(integrations.router)
app.include_router(audit.router)
app.include_router(company_config.router)
app.include_router(sql_variables.router)
app.include_router(dashboard.router)
app.include_router(cobranca.router)

from .routers import meta as meta_router
from .routers import webhook as webhook_router
app.include_router(meta_router.router)
app.include_router(webhook_router.router)

_backend_log("[APP] Todos os routers registrados")


@app.get("/health")
async def health():
    return {"status": "ok"}
