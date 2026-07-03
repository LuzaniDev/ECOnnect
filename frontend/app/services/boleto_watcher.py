import os
import re
import time
import threading
import subprocess
from datetime import datetime

_FILENAME_REGEX = re.compile(r"^(.+?)(\d+)_(\d+)\.pdf$")
_POLL_INTERVAL = 30


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


def _processar_pdf(caminho: str):
    nome = os.path.basename(caminho)
    parsed = _parse_filename(nome)
    if not parsed:
        return
    prefixo, num_boleto_raw, nosso_numero = parsed

    import fitz
    try:
        doc = fitz.open(caminho)
        texto = doc[0].get_text()
        doc.close()
    except Exception:
        return

    from frontend.app.services.boleto_pdf import _extrair_linha_do_texto, _linha_para_barcode
    linha = _extrair_linha_do_texto(texto)
    if not linha:
        return
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


def _diretorio_valido(p: str) -> bool:
    if not p or not p.strip():
        return False
    p = p.strip()
    if not (p[0].isalpha() and p[1:3] == ":\\"):
        return False
    return os.path.isdir(p)


def _listar_pdfs(diretorio: str) -> list[str]:
    pdfs = []
    for root, _, files in os.walk(diretorio):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fn))
    return pdfs


def executar_uma_vez():
    configs = _listar_configs()
    vistos = set()
    for row in configs:
        diretorio = str(row[2] or "")
        if not _diretorio_valido(diretorio):
            continue
        for caminho in _listar_pdfs(diretorio.strip()):
            if caminho in vistos:
                continue
            vistos.add(caminho)
            _processar_pdf(caminho)


class BoletoWatcher(threading.Thread):
    def __init__(self, interval: int = _POLL_INTERVAL):
        super().__init__(daemon=True)
        self._interval = interval
        self._vistos = set()

    def run(self):
        configs = _listar_configs()
        self._vistos.clear()
        for row in configs:
            diretorio = str(row[2] or "")
            if not _diretorio_valido(diretorio):
                continue
            for caminho in _listar_pdfs(diretorio.strip()):
                self._vistos.add(caminho)

        for caminho in list(self._vistos):
            _processar_pdf(caminho)

        while True:
            time.sleep(self._interval)
            configs = _listar_configs()
            for row in configs:
                diretorio = str(row[2] or "")
                if not _diretorio_valido(diretorio):
                    continue
                for caminho in _listar_pdfs(diretorio.strip()):
                    if caminho not in self._vistos:
                        self._vistos.add(caminho)
                        _processar_pdf(caminho)
