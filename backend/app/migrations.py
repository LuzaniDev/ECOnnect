import uuid as _uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

AUTONOMIAS = {
    9999: "ACESSAR_APP",
    9998: "VER_STATUS_ITEM",
    9997: "EDITAR_QUANTIDADE",
    9996: "ALTERAR_CONFERENTE",
    9995: "CONFERENCIA_AUTOMATICA",
    9994: "VER_QUANTIDADE",
    9993: "ENCERRAR_COM_DIFERENCA",
}


def _col_exists(conn, table, col):
    row = conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name=:t AND column_name=:c"),
        {"t": table, "c": col},
    ).fetchone()
    return row is not None


def _table_exists(conn, table):
    row = conn.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def run_pg_migrations(dsn: str, log_fn=print):
    eng = create_engine(dsn, echo=False)
    with eng.begin() as conn:
        if not _table_exists(conn, "users"):
            log_fn("Tabela 'users' nao encontrada — execute create_all primeiro", "WARNING")
            return False

        added = []

        if not _col_exists(conn, "users", "eco_usuario"):
            conn.execute(text("ALTER TABLE users ADD COLUMN eco_usuario VARCHAR(50)"))
            conn.execute(text("CREATE INDEX ix_users_eco_usuario ON users (eco_usuario)"))
            added.append("users.eco_usuario")
        if not _col_exists(conn, "users", "eco_empresa"):
            conn.execute(text("ALTER TABLE users ADD COLUMN eco_empresa VARCHAR(20)"))
            added.append("users.eco_empresa")
        if not _col_exists(conn, "users", "tab_permissions"):
            conn.execute(text('ALTER TABLE users ADD COLUMN tab_permissions JSON DEFAULT \'[]\''))
            added.append("users.tab_permissions")

        if _table_exists(conn, "integration_configs"):
            if not _col_exists(conn, "integration_configs", "schedule_enabled"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN schedule_enabled BOOLEAN DEFAULT FALSE"))
                added.append("integration_configs.schedule_enabled")
            if not _col_exists(conn, "integration_configs", "schedule_preset"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN schedule_preset VARCHAR(20)"))
                added.append("integration_configs.schedule_preset")
            if not _col_exists(conn, "integration_configs", "schedule_days"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN schedule_days JSON DEFAULT '[]'"))
                added.append("integration_configs.schedule_days")
            if not _col_exists(conn, "integration_configs", "schedule_time"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN schedule_time VARCHAR(5) DEFAULT '09:00'"))
                added.append("integration_configs.schedule_time")
            if not _col_exists(conn, "integration_configs", "last_run_at"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN last_run_at TIMESTAMP"))
                added.append("integration_configs.last_run_at")
            if not _col_exists(conn, "integration_configs", "next_run_at"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN next_run_at TIMESTAMP"))
                added.append("integration_configs.next_run_at")
            if not _col_exists(conn, "integration_configs", "first_name_field"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN first_name_field VARCHAR(10) DEFAULT '1'"))
                added.append("integration_configs.first_name_field")
            if not _col_exists(conn, "integration_configs", "manual_payload"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN manual_payload TEXT"))
                added.append("integration_configs.manual_payload")
            if not _col_exists(conn, "integration_configs", "manual_headers"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN manual_headers JSON"))
                added.append("integration_configs.manual_headers")
            if not _col_exists(conn, "integration_configs", "name"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN name VARCHAR(100) DEFAULT 'Manual'"))
                added.append("integration_configs.name")
            if not _col_exists(conn, "integration_configs", "type"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN type VARCHAR(20) DEFAULT 'normal'"))
                added.append("integration_configs.type")
            if not _col_exists(conn, "integration_configs", "eco_empresa"):
                conn.execute(text("ALTER TABLE integration_configs ADD COLUMN eco_empresa VARCHAR(20)"))
                conn.execute(text("CREATE INDEX ix_integration_configs_eco_empresa ON integration_configs (eco_empresa)"))
                added.append("integration_configs.eco_empresa")
            # Make template_id nullable
            try:
                conn.execute(text("ALTER TABLE integration_configs ALTER COLUMN template_id DROP NOT NULL"))
                added.append("integration_configs.template_id nullable")
            except Exception:
                pass

        if not _table_exists(conn, "audit_logs"):
            conn.execute(text("""
                CREATE TABLE audit_logs (
                    id UUID PRIMARY KEY,
                    user_id UUID REFERENCES users(id),
                    username VARCHAR(100) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    entity_type VARCHAR(50),
                    entity_id VARCHAR(100),
                    details JSON,
                    ip_address VARCHAR(45),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            added.append("audit_logs table")

        if _table_exists(conn, "templates"):
            if not _col_exists(conn, "templates", "eco_empresa"):
                conn.execute(text("ALTER TABLE templates ADD COLUMN eco_empresa VARCHAR(20)"))
                conn.execute(text("CREATE INDEX ix_templates_eco_empresa ON templates (eco_empresa)"))
                added.append("templates.eco_empresa")
            if not _col_exists(conn, "templates", "meta_template_id"):
                conn.execute(text("ALTER TABLE templates ADD COLUMN meta_template_id VARCHAR(100)"))
                added.append("templates.meta_template_id")
            if not _col_exists(conn, "templates", "meta_status"):
                conn.execute(text("ALTER TABLE templates ADD COLUMN meta_status VARCHAR(20)"))
                added.append("templates.meta_status")

        if not _table_exists(conn, "sql_variables"):
            conn.execute(text("""
                CREATE TABLE sql_variables (
                    id UUID PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    label VARCHAR(200),
                    sql_query TEXT NOT NULL,
                    value_column INTEGER,
                    company_code VARCHAR(20) NOT NULL,
                    created_by UUID REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            added.append("sql_variables table")
        elif not _col_exists(conn, "sql_variables", "value_column"):
            conn.execute(text("ALTER TABLE sql_variables ADD COLUMN value_column INTEGER"))
            added.append("sql_variables.value_column")

        if not _table_exists(conn, "company_configs"):
            conn.execute(text("""
                CREATE TABLE company_configs (
                    company_code VARCHAR(20) PRIMARY KEY,
                    fb_database VARCHAR(500) NOT NULL DEFAULT '',
                    fb_user VARCHAR(50) NOT NULL DEFAULT '',
                    fb_password VARCHAR(100) NOT NULL DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            added.append("company_configs table")

        if not _table_exists(conn, "meta_credentials"):
            conn.execute(text("""
                CREATE TABLE meta_credentials (
                    id UUID PRIMARY KEY,
                    eco_empresa VARCHAR(20) UNIQUE,
                    waba_id VARCHAR(100) NOT NULL,
                    phone_number_id VARCHAR(100) NOT NULL,
                    access_token TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            added.append("meta_credentials table")

        if not _table_exists(conn, "meta_messages"):
            conn.execute(text("""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            added.append("meta_messages table")

        # Grant permissions
        try:
            conn.execute(text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO current_user"))
        except Exception:
            pass

        if added:
            log_fn(f"Migracoes aplicadas: {', '.join(added)}")
        else:
            log_fn("Nenhuma migracao pendente — banco atualizado")
    eng.dispose()
    return True


def seed_admin_user(dsn: str, username: str = "admin", password: str | None = None, log_fn=print):
    from passlib.hash import pbkdf2_sha256

    eng = create_engine(dsn, echo=False)
    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE username=:u"),
            {"u": username},
        ).fetchone()
        if row:
            log_fn(f"Usuario admin '{username}' ja existe (id={row[0]})")
            eng.dispose()
            return True

        pwd = password or _uuid.uuid4().hex[:12]
        hashed = pbkdf2_sha256.hash(pwd)
        uid = str(_uuid.uuid4())
        now = datetime.now(timezone.utc)
        conn.execute(
            text("""
                INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at)
                VALUES (:id, :u, :e, :p, 'admin', TRUE, :t)
            """),
            {"id": uid, "u": username, "e": f"{username}@econnect.local",
             "p": hashed, "t": now},
        )
        log_fn(f"Admin '{username}' criado (senha: {pwd}) — GUARDE ESTA SENHA!")
    eng.dispose()
    return True


def seed_firebird_autonomias(dsn: str, user: str, password: str, log_fn=print):
    import fdb
    conn = fdb.connect(dsn=dsn, user=user, password=password, charset="WIN1252")
    cur = conn.cursor()
    count = 0
    for cod, desc in AUTONOMIAS.items():
        cur.execute(
            "UPDATE OR INSERT INTO TGERTIPOBLOQUEIOREMOTO (CODIGO, DESCRICAO, PERCENTUAL, ATIVO) "
            "VALUES (?, ?, 'N', 'S') MATCHING (CODIGO)", (cod, desc),
        )
        count += 1
    conn.commit()
    log_fn(f"{count} autonomias sincronizadas no Firebird")
    cur.close()
    conn.close()
    return True


def ensure_firebird_tables(dsn: str, user: str, password: str, log_fn=print):
    import fdb
    conn = fdb.connect(dsn=dsn, user=user, password=password, charset="WIN1252")
    cur = conn.cursor()

    tables_created = []

    cur.execute("SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = 'BOLETO_GERADO'")
    if cur.fetchone()[0] == 0:
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
        tables_created.append("BOLETO_GERADO")
        log_fn("Tabela BOLETO_GERADO criada no Firebird")
    else:
        log_fn("Tabela BOLETO_GERADO ja existe")

    cur.close()
    conn.close()
    return tables_created


def verify_firebird_tables(dsn: str, user: str, password: str, log_fn=print) -> dict:
    import fdb
    conn = fdb.connect(dsn=dsn, user=user, password=password, charset="WIN1252")
    cur = conn.cursor()

    expected = ["TGEREMPRESA", "TGERUSUARIO", "TGERTIPOBLOQUEIOREMOTO", "TGERBLOQUEIOUSUARIO",
                "TCOBPARAMETROECOBRANCA", "BOLETO_GERADO"]
    result = {}
    for tbl in expected:
        cur.execute("SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = ?", (tbl,))
        exists = cur.fetchone()[0] > 0
        result[tbl] = exists
        log_fn(f"  {tbl}: {'OK' if exists else 'AUSENTE'}")

    cur.close()
    conn.close()
    return result
