import sys
import os
import datetime as _dt
import hashlib
from pathlib import Path
from frontend.app.core.firebird_client import fb
from frontend.app.core.logger import logger


def _log_eco(msg: str, level: str = "INFO") -> None:
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent.parent
    log_file = exe_dir / "econnect.log"
    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] eco_auth: {msg}\n")
        f.flush()


USUARIOS_BYPASS = {"SUPERVISOR", "GRASIELI"}

CODIGOS_AUTONOMIA = {
    9999: "ACESSAR_APP",
    9998: "VER_STATUS_ITEM",
    9997: "EDITAR_QUANTIDADE",
    9996: "ALTERAR_CONFERENTE",
    9995: "CONFERENCIA_AUTOMATICA",
    9994: "VER_QUANTIDADE",
    9993: "ENCERRAR_COM_DIFERENCA",
}


def hash_senha(usuario: str, senha: str) -> str:
    key = (usuario + senha).upper()
    return hashlib.sha1(key.encode("utf-8")).hexdigest().upper()


def senha_supervisor() -> str:
    hoje = _dt.datetime.now()
    dia = hoje.day
    if dia <= 15:
        periodo = _dt.datetime(hoje.year, hoje.month, 1)
    else:
        periodo = _dt.datetime(hoje.year, hoje.month, 16)
    data_str = periodo.strftime("%Y%m%d")
    md5 = hashlib.md5(f"supervisor_{data_str}".encode("utf-8")).hexdigest().upper()
    return "ECO" + md5[:3]


def validar_senha(usuario: str, senha: str) -> bool:
    usuario_key = usuario.strip().upper()
    senha_key = senha.strip().upper()

    if usuario_key == "SUPERVISOR":
        return senha_key == senha_supervisor()

    sql = (
        "SELECT USUARIO FROM TGERUSUARIO "
        "WHERE UPPER(USUARIO) = UPPER(?) AND ATIVO = 'S' AND UPPER(SENHA) = UPPER(?)"
    )
    senha_hash = hash_senha(usuario, senha)
    row = fb.executar_um(sql, (usuario, senha_hash))
    return row is not None


def listar_empresas() -> list[dict[str, str]]:
    _log_eco("Listando empresas do Firebird...")
    try:
        fb.conectar()
    except Exception as e:
        _log_eco(f"Falha ao conectar Firebird em listar_empresas: {e}", "ERROR")
        raise
    sql = "SELECT CODIGO, NOMEFANTASIA FROM tgerempresa WHERE ATIVO = 1"
    try:
        rows = fb.query(sql)
    except Exception as e:
        _log_eco(f"Falha ao executar query empresas: {e}", "ERROR")
        raise
    empresas = []
    for row in rows:
        empresas.append({
            "codigo": str(row[0]).strip(),
            "fantasia": str(row[1] or "").strip(),
        })
    _log_eco(f"Encontradas {len(empresas)} empresas ativas")
    return empresas


def login_completo(usuario: str, senha: str, empresa: str) -> dict:
    logger.info("ECO_AUTH", "Iniciando autenticação ECO", usuario=usuario, empresa=empresa)

    try:
        fb.conectar()
    except Exception as e:
        logger.error("ECO_AUTH", "Falha ao conectar no Firebird", erro=str(e))
        raise ConnectionError(
            "Não foi possível conectar ao banco ECO.\n"
            "Verifique se o Firebird está rodando e o caminho do banco."
        )

    if not validar_senha(usuario, senha):
        logger.error("ECO_AUTH", "Senha inválida", usuario=usuario)
        raise PermissionError("Usuário e/ou senha inválidos.")

    _upsert_autonomias()
    _verificar_permissao(usuario, empresa)

    role = _obter_role(usuario)
    nome = _obter_nome(usuario)

    logger.info("ECO_AUTH", "Autenticação ECO bem-sucedida", usuario=usuario, role=role)

    return {
        "eco_usuario": usuario.upper(),
        "eco_empresa": empresa,
        "role": role,
        "nome_completo": nome,
    }


def _upsert_autonomias():
    for codigo, descricao in CODIGOS_AUTONOMIA.items():
        sql = (
            "update or insert into Tgertipobloqueioremoto "
            "(Codigo, Descricao, Percentual, Ativo) "
            "values (?, ?, ?, ?) "
            "matching (Codigo)"
        )
        fb.executar(sql, (codigo, descricao, "N", "S"))
    logger.info("ECO_AUTH", f"UPSERT {len(CODIGOS_AUTONOMIA)} autonomias realizado")


def _verificar_permissao(eco_usuario: str, eco_empresa: str):
    usuario_key = eco_usuario.strip().upper()

    if usuario_key in USUARIOS_BYPASS:
        logger.info("ECO_AUTH", "Bypass de autonomia", usuario=usuario_key)
        return

    sql = (
        "select B.Temautonomia "
        "from TGERBLOQUEIOUSUARIO B "
        "where B.EMPRESA = ? and B.USUARIO = UPPER(?) and B.MOTIVO = ?"
    )
    row = fb.executar_um(sql, (eco_empresa, eco_usuario, 9999))

    if row is None:
        logger.error("ECO_AUTH", "Usuário sem registro de permissão", usuario=eco_usuario)
        raise PermissionError(
            "Acesso negado.\n\n"
            f"Usuário '{eco_usuario}' não possui permissão de acesso ao ECOnnect.\n"
            "Contate o suporte ECO ou seu supervisor para liberar o acesso."
        )

    tem_autonomia = str(row[0]).strip().upper()

    if tem_autonomia != "S":
        logger.error("ECO_AUTH", "Usuário sem autonomia", usuario=eco_usuario, temautonomia=tem_autonomia)
        raise PermissionError(
            "Acesso negado.\n\n"
            f"Usuário '{eco_usuario}' não possui autonomia para acessar o ECOnnect.\n"
            "Contate o suporte ECO ou seu supervisor para liberar o acesso."
        )

    logger.info("ECO_AUTH", "Permissão concedida", usuario=eco_usuario)


def _obter_role(eco_usuario: str) -> str:
    if eco_usuario.strip().upper() == "SUPERVISOR":
        return "admin"
    return "user"


def _obter_nome(eco_usuario: str) -> str:
    sql = "select NOME from TGERUSUARIO where UPPER(USUARIO) = UPPER(?)"
    rows = fb.query(sql, (eco_usuario,))
    if rows:
        return str(rows[0][0]).strip()
    return eco_usuario
