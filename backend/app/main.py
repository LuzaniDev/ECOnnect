import asyncio
import sys
import os
import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import engine, Base, async_session
from .routers import auth, templates, requests, users, integrations, audit, company_config, sql_variables, dashboard
from .models.integration import IntegrationConfig
from .models.audit_log import AuditLog
from .services.integration_service import IntegrationService


def _backend_log(msg: str, level: str = "INFO") -> None:
    """Write directly to econnect.log (same file as frontend)."""
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent.parent
    log_file = exe_dir / "econnect.log"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] backend: {msg}\n")
        f.flush()


SCHEDULER_INTERVAL = 30
DB_RETRIES = 5
DB_RETRY_DELAY = 3


async def _run_migrations():
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users'
            """))
            existing_cols = {row[0] for row in result.fetchall()}

            if 'eco_usuario' not in existing_cols:
                await session.execute(text(
                    "ALTER TABLE users ADD COLUMN eco_usuario VARCHAR(50)"
                ))
            if 'eco_empresa' not in existing_cols:
                await session.execute(text(
                    "ALTER TABLE users ADD COLUMN eco_empresa VARCHAR(20)"
                ))
            await session.commit()
        except Exception:
            await session.rollback()

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'integration_configs'
            """))
            existing = {row[0] for row in result.fetchall()}

            if 'schedule_enabled' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN schedule_enabled BOOLEAN DEFAULT FALSE"
                ))
            if 'schedule_preset' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN schedule_preset VARCHAR(20)"
                ))
            if 'schedule_days' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN schedule_days JSON DEFAULT '[]'"
                ))
            if 'schedule_time' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN schedule_time VARCHAR(5) DEFAULT '09:00'"
                ))
            if 'last_run_at' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN last_run_at TIMESTAMP"
                ))
            if 'next_run_at' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN next_run_at TIMESTAMP"
                ))
            if 'first_name_field' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN first_name_field VARCHAR(10) DEFAULT '1'"
                ))
            if 'manual_payload' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN manual_payload JSON"
                ))
            if 'manual_headers' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN manual_headers JSON"
                ))
            if 'name' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN name VARCHAR(100) DEFAULT 'Manual'"
                ))

            if 'type' not in existing:
                await session.execute(text(
                    "ALTER TABLE integration_configs ADD COLUMN type VARCHAR(20) DEFAULT 'normal'"
                ))

            col_type_result = await session.execute(text("""
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'integration_configs' AND column_name = 'manual_payload'
            """))
            col_type = col_type_result.scalar()
            if col_type and col_type in ('json', 'jsonb'):
                await session.execute(text(
                    "ALTER TABLE integration_configs ALTER COLUMN manual_payload TYPE TEXT"
                ))
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
                        await session.execute(text(
                            f"ALTER TABLE integration_configs DROP CONSTRAINT {fk_name}"
                        ))
                except Exception:
                    pass
                await session.execute(text(
                    "ALTER TABLE integration_configs ALTER COLUMN template_id DROP NOT NULL"
                ))
            await session.commit()
        except Exception:
            await session.rollback()

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
            await session.commit()
        except Exception:
            await session.rollback()

    # Migrations for eco_empresa columns (Item 2)
    for table in ('integration_configs', 'templates'):
        async with async_session() as session:
            try:
                result = await session.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :t"
                ), {"t": table})
                existing = {row[0] for row in result.fetchall()}
                if 'eco_empresa' not in existing:
                    await session.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN eco_empresa VARCHAR(20)"
                    ))
                await session.commit()
            except Exception:
                await session.rollback()

    # Migration for sql_variables table (Item 3)
    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = 'sql_variables'"
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
                await session.execute(text(
                    "CREATE INDEX ix_sql_variables_company_code ON sql_variables (company_code)"
                ))
            await session.commit()
        except Exception:
            await session.rollback()

    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'sql_variables'
            """))
            existing = {row[0] for row in result.fetchall()}
            if 'value_column' not in existing:
                await session.execute(text(
                    "ALTER TABLE sql_variables ADD COLUMN value_column INTEGER"
                ))
            await session.commit()
        except Exception:
            await session.rollback()

    # Migration for company_configs table (Item 4)
    async with async_session() as session:
        try:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = 'company_configs'"
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
            await session.commit()
        except Exception:
            await session.rollback()


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
                await _conn.execute(text(
                    f"GRANT ALL ON SCHEMA public TO \"{_settings.DB_USER}\""
                ))
                await _conn.execute(text(
                    f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{_settings.DB_USER}\""
                ))
                await _conn.execute(text(
                    f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"{_settings.DB_USER}\""
                ))
                await _conn.execute(text(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO \"{_settings.DB_USER}\""
                ))
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
    from .config import settings as _settings

    db_url_preview = _settings.DATABASE_URL.replace(
        _settings.DB_PASSWORD, "****"
    )
    _backend_log(f"[DB] Conectando em: {db_url_preview}")

    last_exc = None
    for attempt in range(1, DB_RETRIES + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if attempt < DB_RETRIES:
                err_msg = str(e).rstrip(".!")
                _backend_log(f"[DB] Conexao falhou (tentativa {attempt}/{DB_RETRIES}): {err_msg}", "WARNING")
                _backend_log(f"[DB] Nova tentativa em {DB_RETRY_DELAY}s...")
                await asyncio.sleep(DB_RETRY_DELAY)
    if last_exc:
        from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
        _fb_urls = [
            f"postgresql+asyncpg://postgres:postgres@{_settings.DB_HOST}:{_settings.DB_PORT}/postgres?ssl=disable",
            f"postgresql+asyncpg://postgres@localhost:{_settings.DB_PORT}/postgres?ssl=disable",
        ]
        _fb_success = False
        for _fb_url in _fb_urls:
            if _fb_success:
                break
            try:
                _backend_log(f"[DB] Tentando fallback com superuser do PostgreSQL...", "WARNING")
                _fb_engine = _create_async_engine(_fb_url)
                async with _fb_engine.begin() as _conn:
                    await _conn.execute(text("SELECT 1"))
                    _user_exists = await _conn.execute(
                        text(f"SELECT 1 FROM pg_roles WHERE rolname='{_settings.DB_USER}'")
                    )
                    if not _user_exists.scalar():
                        await _conn.execute(text(
                            f"CREATE USER \"{_settings.DB_USER}\" WITH PASSWORD '{_settings.DB_PASSWORD}'"
                        ))
                        _backend_log(f"[DB] Usuario '{_settings.DB_USER}' criado!")
                    await _conn.execute(text(
                        f"ALTER USER \"{_settings.DB_USER}\" WITH PASSWORD '{_settings.DB_PASSWORD}'"
                    ))
                    _backend_log(f"[DB] Usuario '{_settings.DB_USER}' configurado com nova senha!")
                    _db_exists = await _conn.execute(
                        text(f"SELECT 1 FROM pg_database WHERE datname='{_settings.DB_NAME}'")
                    )
                    if not _db_exists.scalar():
                        await _conn.execute(text(
                            f"CREATE DATABASE \"{_settings.DB_NAME}\" OWNER \"{_settings.DB_USER}\""
                        ))
                        _backend_log(f"[DB] Database '{_settings.DB_NAME}' criado!")
                await _fb_engine.dispose()
                _new_db_url = f"postgresql+asyncpg://{_settings.DB_USER}:{_settings.DB_PASSWORD}@{_settings.DB_HOST}:{_settings.DB_PORT}/{_settings.DB_NAME}?ssl=disable"
                _new_engine = _create_async_engine(_new_db_url)
                async with _new_engine.begin() as _conn:
                    await _conn.run_sync(Base.metadata.create_all)
                await _new_engine.dispose()
                _backend_log(f"[DB] Conexao estabelecida apos fallback!")
                _fb_success = True
                last_exc = None
            except Exception as _fb_err:
                _backend_log(f"[DB] Tentativa de fallback falhou: {_fb_err}", "WARNING")
        if last_exc:
            err_msg = str(last_exc).rstrip(".!")
            _backend_log(f"[DB] Nao foi possivel conectar ao PostgreSQL apos {DB_RETRIES} tentativas.", "ERROR")
            _backend_log(f"[DB] URL: {db_url_preview}", "ERROR")
            _backend_log(f"[DB] Erro final: {err_msg}", "ERROR")
            _backend_log(f"[DB] Verifique se: (1) PostgreSQL instalado e rodando em localhost:{_settings.DB_PORT}", "ERROR")
            _backend_log(f"[DB] (2) Usuario 'postgres' existe (senha: 'postgres' ou vazia)", "ERROR")
            _backend_log(f"[DB] (3) Database '{_settings.DB_NAME}' existe", "ERROR")
            raise last_exc

    await _run_migrations()
    await _ensure_permissions()

    scheduler_task = asyncio.create_task(_scheduler_loop())

    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(title="ECOnnect API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(requests.router)
app.include_router(users.router)
app.include_router(integrations.router)
app.include_router(audit.router)
app.include_router(company_config.router)
app.include_router(sql_variables.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
