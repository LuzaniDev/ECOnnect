import os
import re
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

_FILENAME_REGEX = re.compile(r"^(.+?)(\d[\d_]*)_(\d+)\.pdf$")


def _ensure_table():
    from frontend.app.core.firebird_client import FirebirdClient
    fb = FirebirdClient()
    fb.conectar()
    try:
        row = fb.executar_um(
            "SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = 'BOLETO_GERADO'"
        )
        if row[0] == 0:
            fb.executar("""
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
    finally:
        fb.fechar()


def _parse_filename(filename: str) -> tuple[str, str, str] | None:
    m = _FILENAME_REGEX.match(filename)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _listar_configs() -> list[tuple]:
    from frontend.app.core.firebird_client import FirebirdClient
    fb = FirebirdClient()
    fb.conectar()
    try:
        return fb.query("""
            SELECT EMPRESA, PORTADOR, DIRETORIOGERACAOBOLETO,
                   PREFIXONOMENCLATURA
            FROM TCOBPARAMETROECOBRANCA
            WHERE DIRETORIOGERACAOBOLETO IS NOT NULL
              AND PREFIXONOMENCLATURA IS NOT NULL
        """)
    finally:
        fb.fechar()


def _processar_pdf(caminho: str) -> bool:
    nome = os.path.basename(caminho)
    parsed = _parse_filename(nome)
    if not parsed:
        return False
    prefixo, num_boleto_raw, nosso_numero = parsed

    import fitz
    try:
        doc = fitz.open(caminho)
        texto = doc[0].get_text()
        doc.close()
    except Exception:
        return False

    from frontend.app.services.boleto_pdf import _extrair_linha_do_texto, _linha_para_barcode
    linha = _extrair_linha_do_texto(texto)
    if not linha:
        return False
    bc = _linha_para_barcode(linha)

    from frontend.app.core.firebird_client import FirebirdClient
    fb = FirebirdClient()
    fb.conectar()
    try:
        dirs = fb.query("""
            SELECT EMPRESA, PORTADOR
            FROM TCOBPARAMETROECOBRANCA
            WHERE PREFIXONOMENCLATURA = ?
        """, (prefixo,))

        if not dirs:
            return False

        for emp, port in dirs:
            row = fb.query(
                "SELECT FIRST 1 IDTRECPARCELA, NUMEROBOLETO "
                "FROM TRECBOLETO "
                "WHERE EMPRESA = ? AND PORTADOR = ? AND NOSSONUMERO = ?",
                (emp, port, nosso_numero),
            )
            if not row:
                continue

            id_parc, num_bol = row[0][0], row[0][1]

            fb.executar(
                "DELETE FROM BOLETO_GERADO "
                "WHERE EMPRESA = ? AND PORTADOR = ? AND NOSSONUMERO = ?",
                (emp, port, nosso_numero),
            )

            fb.executar(
                "INSERT INTO BOLETO_GERADO "
                "(EMPRESA, PORTADOR, NOSSONUMERO, IDPARCELA, NUMEROBOLETO, "
                " CODIGOBARRAS, LINHADIGITAVEL, CAMINHOPDF, DATAGERACAO) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (emp, port, nosso_numero, id_parc, num_bol,
                 bc, linha, caminho, datetime.now()),
            )
    finally:
        fb.fechar()

    return True


def _diretorio_valido(p: str) -> bool:
    if not p or not p.strip():
        return False
    p = p.strip()
    # Aceita caminhos locais (C:\...) e UNC (\\servidor\...)
    if not (p.startswith("\\\\") or (p[0].isalpha() and p[1:3] == ":\\")):
        return False
    return os.path.isdir(p)


def _listar_pdfs(diretorio: str) -> list[str]:
    pdfs = []
    for root, _, files in os.walk(diretorio):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fn))
    return pdfs


def _ja_processado(caminho: str) -> bool:
    nome = os.path.basename(caminho)
    parsed = _parse_filename(nome)
    if not parsed:
        return True
    _, _, nosso_numero = parsed

    prefixo = parsed[0]
    from frontend.app.core.firebird_client import FirebirdClient
    fb = FirebirdClient()
    fb.conectar()
    try:
        dirs = fb.query(
            "SELECT EMPRESA, PORTADOR FROM TCOBPARAMETROECOBRANCA WHERE PREFIXONOMENCLATURA = ?",
            (prefixo,),
        )
        for emp, port in dirs:
            row = fb.executar_um(
                "SELECT COUNT(*) FROM BOLETO_GERADO WHERE EMPRESA = ? AND PORTADOR = ? AND NOSSONUMERO = ?",
                (emp, port, nosso_numero),
            )
            if row and row[0] > 0:
                return True
        return False
    finally:
        fb.fechar()


def executar_scan_completo(progress_callback=None) -> int:
    _ensure_table()
    configs = _listar_configs()
    total_pdfs = 0
    processados = 0
    erros = 0

    pdfs_por_config = []
    for row in configs:
        diretorio = str(row[2] or "")
        if not _diretorio_valido(diretorio):
            continue
        lista = _listar_pdfs(diretorio.strip())
        pdfs_por_config.append(lista)
        total_pdfs += len(lista)

    if total_pdfs == 0:
        return 0

    for lista in pdfs_por_config:
        for caminho in lista:
            if _ja_processado(caminho):
                continue
            try:
                if _processar_pdf(caminho):
                    processados += 1
                else:
                    erros += 1
            except Exception:
                erros += 1
            if progress_callback:
                progress_callback(processados, total_pdfs)

    return processados


class _BoletoHandler(FileSystemEventHandler):
    def __init__(self, dirs_observados: set[str]):
        super().__init__()
        self._dirs = dirs_observados

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        if not any(event.src_path.startswith(d) for d in self._dirs):
            return
        _processar_pdf(event.src_path)


class BoletoWatcher:
    def __init__(self):
        self._observer = None

    def start(self):
        _ensure_table()
        configs = _listar_configs()
        dirs_validos = set()
        for row in configs:
            d = str(row[2] or "").strip()
            if _diretorio_valido(d):
                dirs_validos.add(d)

        if not dirs_validos:
            return

        handler = _BoletoHandler(dirs_validos)
        self._observer = Observer()
        for d in dirs_validos:
            self._observer.schedule(handler, d, recursive=True)
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
