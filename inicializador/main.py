import sys
import os
import re
import uuid
import hashlib
import datetime
import subprocess
import json
import time
import queue
import threading
import concurrent.futures
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox,
    QGroupBox, QComboBox, QProgressBar, QTextEdit, QFrame, QScrollArea,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QByteArray
from PySide6.QtGui import QTextCursor, QFont, QPixmap, QPainter, QIcon, QColor
from PySide6.QtSvg import QSvgRenderer

_RESOLVED = {}
_LINHA_REGEX = re.compile(r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}")
_FILENAME_REGEX = re.compile(r"^(.+?)(\d[\d_]*)_(\d+)\.pdf$")


def _log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
        log_file = exe_dir / "inicializador.log"
        with open(str(log_file), "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {msg}\n")
            f.flush()
    except Exception:
        pass


def _resolve_paths():
    if getattr(sys, "frozen", False):
        parent = Path(sys.executable).parent.resolve()
    else:
        parent = Path(__file__).parent.parent / "dist"
    _RESOLVED["exe"] = parent
    _RESOLVED["env"] = parent / ".env"
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    for cand in [bundled / ".env.example", bundled / "backend" / ".env.example"]:
        if cand.exists():
            _RESOLVED["example"] = cand; break
    _RESOLVED["econnect_exe"] = parent / "ECOnnect.exe"
    if not _RESOLVED["econnect_exe"].exists():
        _RESOLVED["econnect_exe"] = parent.parent / "ECOnnect.exe"


def _read_env() -> dict:
    vals = {}
    env_path = _RESOLVED.get("env")
    if env_path and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                vals[k.strip()] = v.strip()
    return vals


# ── SVG Icons ────────────────────────────────────────────────────

def _make_icon(svg_str: str, size: int = 20) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


def _make_pixmap(svg_str: str, size: int = 20) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return pm


B = "#0e4f9c"
G = "#27ae60"
R = "#e74c3c"
O = "#f39c12"
W = "#ffffff"

_SVG_DB = f'''<svg viewBox="0 0 20 20"><ellipse cx="10" cy="3.5" rx="7" ry="2.5" fill="{B}"/><path d="M3 3.5v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-12" fill="none" stroke="{B}" stroke-width="1.4"/><path d="M3 7.5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" fill="none" stroke="{B}" stroke-width="1.4"/><path d="M3 11.5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" fill="none" stroke="{B}" stroke-width="1.4"/></svg>'''

_SVG_USER = f'''<svg viewBox="0 0 20 20"><circle cx="10" cy="6" r="3.5" fill="none" stroke="{B}" stroke-width="1.4"/><path d="M3 18c0-3.9 3.1-7 7-7s7 3.1 7 7" fill="none" stroke="{B}" stroke-width="1.4"/></svg>'''

_SVG_DOC = f'''<svg viewBox="0 0 20 20"><path d="M4 1.5h7.5L16 6v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2.5a1 1 0 0 1 1-1z" fill="none" stroke="{B}" stroke-width="1.4"/><path d="M11.5 1.5V6H16" fill="none" stroke="{B}" stroke-width="1.4"/><line x1="6" y1="10" x2="14" y2="10" stroke="{B}" stroke-width="1.2"/><line x1="6" y1="13" x2="14" y2="13" stroke="{B}" stroke-width="1.2"/><line x1="6" y1="16" x2="10" y2="16" stroke="{B}" stroke-width="1.2"/></svg>'''

_SVG_LOG = f'''<svg viewBox="0 0 20 20"><rect x="2" y="2" width="16" height="16" rx="2" fill="none" stroke="{B}" stroke-width="1.4"/><line x1="5" y1="6" x2="15" y2="6" stroke="{B}" stroke-width="1.2"/><line x1="5" y1="9" x2="15" y2="9" stroke="{B}" stroke-width="1.2"/><line x1="5" y1="12" x2="15" y2="12" stroke="{B}" stroke-width="1.2"/><line x1="5" y1="15" x2="11" y2="15" stroke="{B}" stroke-width="1.2"/></svg>'''

_SVG_PLUG = f'''<svg viewBox="0 0 20 20"><path d="M14 2v4M6 2v4M4 8h12v2a6 6 0 0 1-12 0V8z" fill="none" stroke="{B}" stroke-width="1.4" stroke-linejoin="round"/><line x1="10" y1="14" x2="10" y2="18" stroke="{B}" stroke-width="1.4"/></svg>'''

_SVG_CHECK = f'''<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="none" stroke="{G}" stroke-width="1.6"/><path d="M6 10l3 3 5-5" fill="none" stroke="{G}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'''

_SVG_PLAY = f'''<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="none" stroke="{B}" stroke-width="1.6"/><path d="M8 6l6 4-6 4V6z" fill="{B}"/></svg>'''

_SVG_TRASH = f'''<svg viewBox="0 0 20 20"><path d="M3 5h14M8 5V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2M5 5l1 12a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-12" fill="none" stroke="{B}" stroke-width="1.4" stroke-linejoin="round"/></svg>'''

_SVG_CANCEL = f'''<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="none" stroke="{R}" stroke-width="1.6"/><line x1="7" y1="7" x2="13" y2="13" stroke="{R}" stroke-width="1.8" stroke-linecap="round"/><line x1="13" y1="7" x2="7" y2="13" stroke="{R}" stroke-width="1.8" stroke-linecap="round"/></svg>'''

_SVG_SAVE = f'''<svg viewBox="0 0 20 20"><path d="M3 2h10l5 5v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" fill="none" stroke="{G}" stroke-width="1.4"/><path d="M13 2v6H5V2" fill="none" stroke="{G}" stroke-width="1.4"/><circle cx="10" cy="14" r="2.5" fill="none" stroke="{G}" stroke-width="1.4"/></svg>'''

_SVG_BRUSH = f'''<svg viewBox="0 0 20 20"><path d="M3 15c0-2 2-4 4-4s4 2 4 4c0 1.5-1 3-3 3s-5-1-5-3z" fill="none" stroke="{B}" stroke-width="1.4"/><path d="M10 11l6-8 2 1-6 8" fill="none" stroke="{B}" stroke-width="1.4" stroke-linejoin="round"/></svg>'''

_SVG_WARN = f'''<svg viewBox="0 0 20 20"><path d="M10 2L1 18h18L10 2z" fill="none" stroke="{O}" stroke-width="1.4" stroke-linejoin="round"/><line x1="10" y1="8" x2="10" y2="12" stroke="{O}" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="15" r="0.8" fill="{O}"/></svg>'''

_SVG_KEY = f'''<svg viewBox="0 0 20 20"><circle cx="14" cy="6" r="4" fill="none" stroke="{B}" stroke-width="1.4"/><line x1="11" y1="9" x2="3" y2="17" stroke="{B}" stroke-width="1.4" stroke-linecap="round"/><line x1="5" y1="15" x2="7" y2="17" stroke="{B}" stroke-width="1.4" stroke-linecap="round"/></svg>'''

_SVG_EMPRESA = f'''<svg viewBox="0 0 20 20"><rect x="3" y="2" width="14" height="16" rx="1" fill="none" stroke="{B}" stroke-width="1.4"/><line x1="6" y1="6" x2="14" y2="6" stroke="{B}" stroke-width="1.2"/><line x1="6" y1="9" x2="14" y2="9" stroke="{B}" stroke-width="1.2"/><line x1="6" y1="12" x2="10" y2="12" stroke="{B}" stroke-width="1.2"/></svg>'''

_ICON_SPECS = [
    ("db", _SVG_DB, 20, "icon"),
    ("user", _SVG_USER, 20, "icon"),
    ("doc", _SVG_DOC, 20, "icon"),
    ("log", _SVG_LOG, 20, "icon"),
    ("plug", _SVG_PLUG, 16, "icon"),
    ("check", _SVG_CHECK, 16, "icon"),
    ("play", _SVG_PLAY, 16, "icon"),
    ("trash", _SVG_TRASH, 16, "icon"),
    ("cancel", _SVG_CANCEL, 16, "icon"),
    ("save", _SVG_SAVE, 16, "icon"),
    ("brush", _SVG_BRUSH, 16, "icon"),
    ("warn", _SVG_WARN, 16, "icon"),
    ("key", _SVG_KEY, 16, "icon"),
    ("empresa", _SVG_EMPRESA, 16, "icon"),
    ("db_20", _SVG_DB, 20, "pixmap"),
    ("doc_20", _SVG_DOC, 20, "pixmap"),
    ("user_20", _SVG_USER, 20, "pixmap"),
    ("log_20", _SVG_LOG, 20, "pixmap"),
]


# ── Firebird conexao ─────────────────────────────────────────────

class FirebirdConn:
    def __init__(self, dsn, user, password):
        self._dsn = dsn; self._user = user; self._password = password; self._conn = None

    def connect(self):
        import fdb
        if self._conn is not None:
            try:
                cur = self._conn.cursor()
                cur.execute("SELECT 1 FROM RDB$DATABASE")
                cur.close()
                return self._conn
            except Exception:
                self._conn = None
        self._conn = fdb.connect(dsn=self._dsn, user=self._user, password=self._password, charset="WIN1252")
        return self._conn

    def close(self):
        if self._conn:
            try: self._conn.close()
            except: pass
            self._conn = None

    def query(self, sql, params=None):
        conn = self.connect(); cur = conn.cursor()
        try:
            if params: cur.execute(sql, params)
            else: cur.execute(sql)
            rows = cur.fetchall(); conn.commit(); return rows
        except Exception:
            conn.rollback(); raise
        finally: cur.close()

    def executa(self, sql, params=None):
        conn = self.connect(); cur = conn.cursor()
        try:
            if params: cur.execute(sql, params)
            else: cur.execute(sql)
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: cur.close()

    def executa_batch(self, ops_list):
        conn = self.connect(); cur = conn.cursor()
        try:
            for sql, params in ops_list:
                cur.execute(sql, params or ())
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: cur.close()


# ── Funcoes de boleto ────────────────────────────────────────────

def _extrair_linha(texto: str) -> str | None:
    for linha in texto.splitlines():
        linha = linha.strip()
        if _LINHA_REGEX.match(linha):
            return linha
    return None


def _linha_para_barcode(linha: str) -> str:
    campos = linha.strip().split()
    if len(campos) != 5: return ""
    f1 = campos[0].replace(".", "")
    f2 = campos[1].replace(".", "")
    f3 = campos[2].replace(".", "")
    f4 = campos[3]
    f5 = campos[4]
    if not (len(f1) == 10 and len(f2) == 11 and len(f3) == 11 and len(f4) == 1 and len(f5) == 14):
        return ""
    return f1[:9] + f4 + f5 + f2[:10] + f3[:10]


def _chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ── Threads ──────────────────────────────────────────────────────

class TestFbThread(QThread):
    finished = Signal(bool, str)
    def __init__(self, dsn, user, password):
        super().__init__(); self.dsn = dsn; self.user = user; self.password = password
    def run(self):
        try:
            fb = FirebirdConn(self.dsn, self.user, self.password)
            fb.connect(); fb.query("SELECT 1 FROM RDB$DATABASE"); fb.close()
            self.finished.emit(True, f"Firebird conectado: {self.dsn}")
        except Exception as e:
            self.finished.emit(False, str(e))


class ListEmpresasThread(QThread):
    finished = Signal(bool, object)
    def __init__(self, dsn, user, password):
        super().__init__(); self.dsn = dsn; self.user = user; self.password = password
    def run(self):
        try:
            fb = FirebirdConn(self.dsn, self.user, self.password)
            rows = fb.query("SELECT CODIGO, NOMEFANTASIA FROM TGEREMPRESA WHERE ATIVO = 1")
            fb.close()
            empresas = [{"codigo": str(r[0]).strip(), "fantasia": str(r[1] or "").strip()} for r in rows]
            self.finished.emit(True, empresas)
        except Exception as e:
            self.finished.emit(False, str(e))


class LoginThread(QThread):
    finished = Signal(bool, str); log_signal = Signal(str, str)
    def __init__(self, dsn, user, password, eco_user, eco_pass, empresa):
        super().__init__()
        self.dsn = dsn; self.fb_user = user; self.fb_pass = password
        self.eco_user = eco_user; self.eco_pass = eco_pass; self.empresa = empresa
    def _l(self, m, l="INFO"): self.log_signal.emit(m, l)
    def run(self):
        try:
            fb = FirebirdConn(self.dsn, self.fb_user, self.fb_pass)
            fb.connect(); self._l("Firebird conectado")
            eco_key = self.eco_user.strip().upper()
            senha_hash = hashlib.sha1((eco_key + self.eco_pass.upper()).encode("utf-8")).hexdigest().upper()
            row = fb.query("SELECT USUARIO FROM TGERUSUARIO WHERE UPPER(USUARIO)=UPPER(?) AND ATIVO='S' AND UPPER(SENHA)=UPPER(?)",
                           (self.eco_user, senha_hash))
            if not row:
                self.finished.emit(False, "Usuario ou senha invalidos"); fb.close(); return
            self._l(f"Usuario {eco_key} autenticado")
            codigos = {9999: "ACESSAR_APP", 9998: "VER_STATUS_ITEM", 9997: "EDITAR_QUANTIDADE",
                       9996: "ALTERAR_CONFERENTE", 9995: "CONFERENCIA_AUTOMATICA",
                       9994: "VER_QUANTIDADE", 9993: "ENCERRAR_COM_DIFERENCA"}
            for cod, desc in codigos.items():
                fb.executa("UPDATE OR INSERT INTO TGERTIPOBLOQUEIOREMOTO (CODIGO, DESCRICAO, PERCENTUAL, ATIVO) "
                           "VALUES (?, ?, 'N', 'S') MATCHING (CODIGO)", (cod, desc))
            self._l(f"{len(codigos)} autonomias sincronizadas")
            row = fb.query("SELECT B.TEMAUTONOMIA FROM TGERBLOQUEIOUSUARIO B "
                           "WHERE B.EMPRESA=? AND B.USUARIO=UPPER(?) AND B.MOTIVO=?",
                           (self.empresa, eco_key, 9999))
            if not row:
                self.finished.emit(False, f"Usuario '{eco_key}' sem permissao"); fb.close(); return
            if str(row[0][0]).strip().upper() != "S":
                self.finished.emit(False, f"Usuario '{eco_key}' sem autonomia"); fb.close(); return
            self._l(f"Acesso autorizado: {eco_key} / {self.empresa}")
            fb.close()
            self.finished.emit(True, f"Login OK - {eco_key} / {self.empresa}")
        except Exception as e:
            import traceback
            self._l(str(e), "ERROR")
            for line in traceback.format_exc().splitlines(): self._l(line, "ERROR")
            self.finished.emit(False, str(e))


# ── Contador atomico ─────────────────────────────────────────────

class AtomicCounter:
    def __init__(self, initial=0):
        self._value = initial
        self._lock = threading.Lock()
    def inc(self, delta=1):
        with self._lock:
            self._value += delta
            return self._value
    @property
    def value(self):
        with self._lock:
            return self._value


# ── Scan de Boletos Otimizado ────────────────────────────────────

class BoletoScanThread(QThread):
    finished = Signal(bool, str)
    log_signal = Signal(str, str)
    progress_signal = Signal(int, int)
    phase_signal = Signal(str)

    def __init__(self, dsn, user, password):
        super().__init__()
        self.dsn = dsn; self.fb_user = user; self.fb_pass = password
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _l(self, m, l="INFO"): self.log_signal.emit(m, l)
    def _p(self, cur, total): self.progress_signal.emit(cur, total)
    def _ph(self, phase): self.phase_signal.emit(phase)

    def run(self):
        try:
            import fitz
            fb = FirebirdConn(self.dsn, self.fb_user, self.fb_pass)
            fb.connect()
            self._l("Firebird conectado")
            row = fb.query("SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = 'BOLETO_GERADO'")
            if row[0][0] == 0:
                fb.executa("""CREATE TABLE BOLETO_GERADO (
                    EMPRESA VARCHAR(10) NOT NULL, PORTADOR VARCHAR(10) NOT NULL,
                    NOSSONUMERO VARCHAR(30) NOT NULL, IDPARCELA INTEGER,
                    NUMEROBOLETO VARCHAR(30), CODIGOBARRAS VARCHAR(44),
                    LINHADIGITAVEL VARCHAR(60), CAMINHOPDF VARCHAR(500),
                    DATAGERACAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (EMPRESA, PORTADOR, NOSSONUMERO))""")
                self._l("Tabela BOLETO_GERADO criada")
            else:
                self._l("Tabela BOLETO_GERADO ja existe")
            configs = fb.query("""SELECT EMPRESA, PORTADOR, DIRETORIOGERACAOBOLETO, PREFIXONOMENCLATURA
                FROM TCOBPARAMETROECOBRANCA
                WHERE DIRETORIOGERACAOBOLETO IS NOT NULL AND PREFIXONOMENCLATURA IS NOT NULL""")
            self._l(f"{len(configs)} configs de boleto encontradas")

            self._ph("Descobrindo arquivos PDF...")
            all_pdfs = []
            for row in configs:
                if self._stop_event.is_set():
                    fb.close(); self.finished.emit(False, "Cancelado pelo usuario"); return
                diretorio = str(row[2] or "").strip()
                if not diretorio or not os.path.isdir(diretorio):
                    self._l(f"Diretorio invalido: {diretorio}", "WARNING"); continue
                prefixo = str(row[3] or "").strip()
                empresa = str(row[0] or "").strip()
                portador = str(row[1] or "").strip()
                for root, _, files in os.walk(diretorio):
                    for fn in files:
                        m = _FILENAME_REGEX.match(fn)
                        if m:
                            _, num_boleto_raw, nosso_numero = m.groups()
                            all_pdfs.append({
                                "caminho": os.path.join(root, fn),
                                "empresa": empresa, "portador": portador,
                                "prefixo": prefixo, "nosso_numero": nosso_numero,
                                "num_boleto_raw": num_boleto_raw,
                            })
            total_raw = len(all_pdfs)
            self._l(f"{total_raw} PDFs encontrados")
            if total_raw == 0:
                fb.close(); self.finished.emit(True, "Nenhum PDF para processar"); return

            self._ph("Verificando registros ja processados...")
            existing_set = set()
            for chunk in _chunk_list(all_pdfs, 300):
                if self._stop_event.is_set():
                    fb.close(); self.finished.emit(False, "Cancelado"); return
                conditions = []; params = []
                for p in chunk:
                    conditions.append("(EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?)")
                    params.extend([p["empresa"], p["portador"], p["nosso_numero"]])
                rows = fb.query(f"SELECT EMPRESA, PORTADOR, NOSSONUMERO FROM BOLETO_GERADO WHERE {' OR '.join(conditions)}", params)
                for r in rows:
                    existing_set.add((str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip()))
            to_process = [p for p in all_pdfs if (p["empresa"], p["portador"], p["nosso_numero"]) not in existing_set]
            already_done = total_raw - len(to_process)
            self._l(f"{len(to_process)} novos PDFs para processar ({already_done} ja existentes)")
            if not to_process:
                fb.close(); self.finished.emit(True, f"Todos os {total_raw} PDFs ja estao processados"); return

            self._ph("Consultando dados de parcela...")
            trec_cache = {}
            for chunk in _chunk_list(to_process, 300):
                conditions = []; params = []
                for p in chunk:
                    conditions.append("(EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?)")
                    params.extend([p["empresa"], p["portador"], p["nosso_numero"]])
                rows = fb.query(f"SELECT EMPRESA, PORTADOR, NOSSONUMERO, IDTRECPARCELA, NUMEROBOLETO FROM TRECBOLETO WHERE {' OR '.join(conditions)}", params)
                for r in rows:
                    trec_cache[(str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip())] = (r[3], r[4])
            self._l(f"{len(trec_cache)} registros de parcela carregados em cache")
            fb.close()

            total = len(to_process)
            self._ph(f"Processando {total} boletos...")
            result_queue = queue.Queue(maxsize=2000)
            counter = AtomicCounter()
            num_workers = min(16, (os.cpu_count() or 4) * 2)
            self._l(f"Iniciando pipeline paralelo com {num_workers} workers...")

            def db_writer():
                fb2 = FirebirdConn(self.dsn, self.fb_user, self.fb_pass)
                fb2.connect()
                batch_ops = []
                try:
                    while True:
                        try:
                            result = result_queue.get(timeout=2)
                            if result is None: break
                            batch_ops.append((
                                "DELETE FROM BOLETO_GERADO WHERE EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?",
                                (result["empresa"], result["portador"], result["nosso_numero"])
                            ))
                            batch_ops.append((
                                "INSERT INTO BOLETO_GERADO (EMPRESA,PORTADOR,NOSSONUMERO,IDPARCELA,"
                                "NUMEROBOLETO,CODIGOBARRAS,LINHADIGITAVEL,CAMINHOPDF,DATAGERACAO) "
                                "VALUES (?,?,?,?,?,?,?,?,?)",
                                (result["empresa"], result["portador"], result["nosso_numero"],
                                 result["id_parcela"], result["num_boleto"],
                                 result["codigo_barras"], result["linha_digitavel"],
                                 result["caminho"], datetime.datetime.now())
                            ))
                            if len(batch_ops) >= 200:
                                fb2.executa_batch(batch_ops); batch_ops = []
                        except queue.Empty:
                            if batch_ops:
                                fb2.executa_batch(batch_ops); batch_ops = []
                            if self._stop_event.is_set() and result_queue.empty(): break
                    if batch_ops: fb2.executa_batch(batch_ops)
                except Exception as e:
                    self._l(f"DB writer error: {e}", "ERROR")
                finally:
                    fb2.close()

            def pdf_worker(pdf_info):
                if self._stop_event.is_set(): return
                try:
                    doc = fitz.open(pdf_info["caminho"])
                    texto = doc[0].get_text(); doc.close()
                    linha = _extrair_linha(texto)
                    if not linha: counter.inc(); return
                    bc = _linha_para_barcode(linha)
                    if not bc: counter.inc(); return
                    key = (pdf_info["empresa"], pdf_info["portador"], pdf_info["nosso_numero"])
                    id_parc, num_bol = trec_cache.get(key, (None, None))
                    result_queue.put({
                        "empresa": pdf_info["empresa"], "portador": pdf_info["portador"],
                        "nosso_numero": pdf_info["nosso_numero"],
                        "id_parcela": id_parc, "num_boleto": num_bol,
                        "codigo_barras": bc, "linha_digitavel": linha,
                        "caminho": pdf_info["caminho"],
                    })
                    n = counter.inc()
                    if n % 50 == 0 or n == 1: self._p(n, total)
                    if n % 500 == 0: self._l(f"Processados: {n}/{total}")
                except Exception as e:
                    self._l(f"Erro: {os.path.basename(pdf_info.get('caminho','?'))}: {e}", "WARNING")
                    counter.inc()

            writer_thread = threading.Thread(target=db_writer, daemon=True)
            writer_thread.start()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                concurrent.futures.wait([executor.submit(pdf_worker, p) for p in to_process])
            result_queue.put(None); writer_thread.join()
            final_count = counter.value
            erro_count = total - final_count
            self._l(f"Concluido: {final_count} processados, {erro_count} erros")
            self.finished.emit(True, f"{final_count} boletos processados, {erro_count} erros")
        except Exception as e:
            import traceback
            self._l(str(e), "ERROR")
            for line in traceback.format_exc().splitlines(): self._l(line, "ERROR")
            self.finished.emit(False, str(e))


# ── UI ───────────────────────────────────────────────────────────

LOG_COLORS = {
    "INFO": "#3498db", "OK": "#27ae60", "SUCCESS": "#27ae60",
    "WARNING": "#f39c12", "ERROR": "#e74c3c",
}
LOG_LEVELS = {"INFO", "OK", "SUCCESS", "WARNING", "ERROR"}


class InicializadorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECOnnect Inicializador")
        self.setMinimumSize(580, 720)
        self._threads = []
        self._scan_thread = None
        self._icons = {}
        self._init_icons()
        self._build_ui()
        self._load_env()

    def _init_icons(self):
        for key, svg, size, kind in _ICON_SPECS:
            if kind == "icon":
                self._icons[key] = _make_icon(svg, size)
            else:
                self._icons[key] = _make_pixmap(svg, size)

    def _make_card(self, title, icon_key=""):
        card = QFrame(); card.setObjectName("card")
        cl = QVBoxLayout(card); cl.setContentsMargins(20, 16, 20, 16); cl.setSpacing(12)
        if title:
            hl = QHBoxLayout(); hl.setContentsMargins(0, 0, 0, 0)
            if icon_key:
                lbl = QLabel()
                lbl.setPixmap(self._icons.get(icon_key, self._icons.get("doc_20")).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                hl.addWidget(lbl)
                hl.addSpacing(8)
            tl = QLabel(title); tl.setObjectName("cardTitle")
            hl.addWidget(tl); hl.addStretch()
            cl.addLayout(hl)
        return card, cl

    def _make_status_row(self):
        row = QHBoxLayout(); row.setSpacing(8)
        dot = QLabel("o"); dot.setObjectName("statusDot")
        dot.setFixedWidth(16)
        status = QLabel(""); status.setObjectName("statusText"); status.setWordWrap(True)
        row.addWidget(dot); row.addWidget(status, 1)
        return row, dot, status

    def _set_status(self, dot, status, text, ok=None):
        status.setText(text)
        if ok is True:
            dot.setText("o"); dot.setStyleSheet("color: #27ae60; font-size: 16px; background: transparent; font-weight: bold;")
        elif ok is False:
            dot.setText("o"); dot.setStyleSheet("color: #e74c3c; font-size: 16px; background: transparent; font-weight: bold;")
        else:
            dot.setText("o"); dot.setStyleSheet("color: #bdc3c7; font-size: 16px; background: transparent;")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        header = QFrame(); header.setObjectName("header")
        hl = QVBoxLayout(header); hl.setContentsMargins(28, 24, 28, 20); hl.setSpacing(4)
        ht = QLabel("ECOnnect Inicializador"); ht.setObjectName("headerTitle")
        hl.addWidget(ht)
        hs = QLabel("Prepare seu ambiente para o sistema ECOnnect"); hs.setObjectName("headerSub")
        hl.addWidget(hs)
        root.addWidget(header)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")
        scroll_w = QWidget(); scroll_w.setObjectName("scrollContent")
        self._content = QVBoxLayout(scroll_w)
        self._content.setContentsMargins(24, 20, 24, 20); self._content.setSpacing(16)
        scroll.setWidget(scroll_w); root.addWidget(scroll, 1)

        fb_card, fb_cl = self._make_card("Conexao Firebird", "db_20")
        self.fb_dsn = QLineEdit("C:\\ecosis\\dados\\ECODADOS.ECO")
        self.fb_dsn.setToolTip("Servidor remoto: servidor:C:\\caminho\\arquivo.fdb\nLocal: C:\\caminho\\arquivo.fdb")
        self.fb_user = QLineEdit("SYSDBA")
        self.fb_pass = QLineEdit("masterkey"); self.fb_pass.setEchoMode(QLineEdit.Password)
        fm = QFormLayout(); fm.setSpacing(8)
        fm.addRow("Database:", self.fb_dsn); fm.addRow("Usuario:", self.fb_user); fm.addRow("Senha:", self.fb_pass)
        fb_cl.addLayout(fm)
        test_row = QHBoxLayout(); test_row.setSpacing(12)
        self.btn_test_fb = QPushButton(" Testar Conexao"); self.btn_test_fb.setIcon(self._icons["plug"])
        self.btn_test_fb.clicked.connect(self._test_fb)
        test_row.addWidget(self.btn_test_fb)
        fb_stat_row, self.fb_dot, self.fb_status = self._make_status_row()
        test_row.addLayout(fb_stat_row, 1)
        fb_cl.addLayout(test_row)
        self._content.addWidget(fb_card)

        eco_card, eco_cl = self._make_card("Autenticacao ECO", "user_20")
        self.eco_user = QLineEdit(); self.eco_user.setPlaceholderText("usuario ECO (ex: SUPERVISOR)")
        self.eco_pass = QLineEdit(); self.eco_pass.setEchoMode(QLineEdit.Password); self.eco_pass.setPlaceholderText("senha ECO")
        self.eco_empresa = QComboBox(); self.eco_empresa.setEnabled(False)
        em = QFormLayout(); em.setSpacing(8)
        em.addRow("Usuario:", self.eco_user); em.addRow("Senha:", self.eco_pass); em.addRow("Empresa:", self.eco_empresa)
        eco_cl.addLayout(em)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self.btn_list_emp = QPushButton(" Listar Empresas"); self.btn_list_emp.setIcon(self._icons["empresa"])
        self.btn_list_emp.clicked.connect(self._list_empresas); self.btn_list_emp.setEnabled(False)
        self.btn_eco_login = QPushButton(" Validar Login"); self.btn_eco_login.setIcon(self._icons["key"])
        self.btn_eco_login.clicked.connect(self._eco_login); self.btn_eco_login.setEnabled(False)
        btn_row.addWidget(self.btn_list_emp); btn_row.addWidget(self.btn_eco_login)
        eco_cl.addLayout(btn_row)
        eco_stat_row, self.eco_dot, self.eco_status = self._make_status_row()
        eco_cl.addLayout(eco_stat_row)
        self._content.addWidget(eco_card)

        bol_card, bol_cl = self._make_card("Processamento de Boletos", "doc_20")
        desc = QLabel(
            "Escaneia todos os PDFs de boleto nos diretorios configurados no Firebird "
            "(TCOBPARAMETROECOBRANCA) e registra em BOLETO_GERADO.\n"
            "Processamento paralelo com multiplos workers para alto desempenho."
        )
        desc.setWordWrap(True); desc.setObjectName("cardDesc")
        bol_cl.addWidget(desc)
        btn_bol_row = QHBoxLayout(); btn_bol_row.setSpacing(8)
        self.btn_scan = QPushButton(" INICIAR SCAN COMPLETO"); self.btn_scan.setIcon(self._icons["play"])
        self.btn_scan.clicked.connect(self._scan_boletos); self.btn_scan.setEnabled(False)
        self.btn_limpar = QPushButton(" Limpar BOLETO_GERADO"); self.btn_limpar.setIcon(self._icons["trash"])
        self.btn_limpar.clicked.connect(self._limpar_boletos); self.btn_limpar.setEnabled(False)
        self.btn_cancel_scan = QPushButton(" Cancelar"); self.btn_cancel_scan.setIcon(self._icons["cancel"])
        self.btn_cancel_scan.clicked.connect(self._cancel_scan); self.btn_cancel_scan.setVisible(False)
        btn_bol_row.addWidget(self.btn_scan); btn_bol_row.addWidget(self.btn_limpar); btn_bol_row.addWidget(self.btn_cancel_scan)
        bol_cl.addLayout(btn_bol_row)
        self.bol_bar = QProgressBar(); self.bol_bar.setVisible(False); self.bol_bar.setObjectName("bolBar")
        self.bol_bar.setTextVisible(True)
        bol_cl.addWidget(self.bol_bar)
        bol_stat_row, self.bol_dot, self.bol_status = self._make_status_row()
        bol_cl.addLayout(bol_stat_row)
        self._content.addWidget(bol_card)

        log_card, log_cl = self._make_card("Log de Atividades", "log_20")
        log_cl.setSpacing(8)
        log_toolbar = QHBoxLayout(); log_toolbar.setSpacing(8)
        log_toolbar.addStretch()
        self.btn_clear_log = QPushButton(" Limpar Log"); self.btn_clear_log.setObjectName("btnSmall")
        self.btn_clear_log.setIcon(self._icons["brush"])
        self.btn_clear_log.clicked.connect(lambda: self.log_area.clear())
        log_toolbar.addWidget(self.btn_clear_log)
        log_cl.addLayout(log_toolbar)
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True); self.log_area.setObjectName("logArea")
        log_cl.addWidget(self.log_area)
        self._content.addWidget(log_card)

        launch_card, launch_cl = self._make_card("", "")
        launch_cl.setContentsMargins(0, 0, 0, 0)
        self.btn_launch = QPushButton(" Salvar e Abrir ECOnnect"); self.btn_launch.setIcon(self._icons["save"])
        self.btn_launch.setObjectName("btnLaunch")
        self.btn_launch.clicked.connect(self._save_and_launch)
        launch_cl.addWidget(self.btn_launch)
        self._content.addWidget(launch_card)

        footer = QFrame(); footer.setObjectName("footer")
        fl = QVBoxLayout(footer); fl.setContentsMargins(24, 10, 24, 10)
        self.path_label = QLabel(""); self.path_label.setTextFormat(Qt.RichText)
        self.path_label.setWordWrap(True); self.path_label.setObjectName("pathLabel")
        fl.addWidget(self.path_label)
        root.addWidget(footer)

    def _log(self, message, level="INFO"):
        if level not in LOG_LEVELS: level = "INFO"
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(level, "#7f8c8d")
        html = f'<span style="color:#95a5a6;">[{ts}]</span> '
        html += f'<span style="color:{color};font-weight:600;">[{level}]</span> '
        html += f'<span style="color:#2c3e50;">{message}</span><br>'
        self.log_area.moveCursor(QTextCursor.End)
        self.log_area.insertHtml(html)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())
        _log(message, level)

    def _set_enabled(self, en: bool):
        self.btn_test_fb.setEnabled(en)
        self.btn_list_emp.setEnabled(en and bool(self.fb_dsn.text().strip()))
        self.btn_eco_login.setEnabled(en and self.eco_empresa.isEnabled())
        self.btn_scan.setEnabled(en)
        self.btn_limpar.setEnabled(en)
        self.btn_launch.setEnabled(en)

    def _load_env(self):
        _resolve_paths()
        vals = _read_env()
        if vals.get("FB_DATABASE"): self.fb_dsn.setText(vals["FB_DATABASE"])
        if vals.get("FB_USER"): self.fb_user.setText(vals["FB_USER"])
        if vals.get("FB_PASSWORD"): self.fb_pass.setText(vals["FB_PASSWORD"])
        exe_path = _RESOLVED.get("econnect_exe"); env_path = _RESOLVED.get("env")
        parts = []
        if env_path:
            exists = "EXISTE" if env_path.exists() else "NAO EXISTE"
            parts.append(f'.env: <span style="color:#555;">{env_path}</span> (<b>{exists}</b>)')
        if exe_path:
            found = "ENCONTRADO" if exe_path.exists() else "NAO ENCONTRADO"
            parts.append(f'ECOnnect: <span style="color:#555;">{exe_path}</span> (<b>{found}</b>)')
        self.path_label.setText("<br>".join(parts))

    def _test_fb(self):
        self._set_enabled(False)
        self._set_status(self.fb_dot, self.fb_status, "Testando...")
        t = TestFbThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.finished.connect(lambda ok, m: (
            self._set_enabled(True),
            self._set_status(self.fb_dot, self.fb_status, m, ok),
            self.btn_list_emp.setEnabled(ok),
            self.btn_scan.setEnabled(ok),
            self.btn_limpar.setEnabled(ok),
            self._log(m, "OK" if ok else "ERROR")))
        self._threads.append(t); t.start()

    def _list_empresas(self):
        self._set_enabled(False)
        self._set_status(self.eco_dot, self.eco_status, "Listando...")
        self._log("Listando empresas...")
        t = ListEmpresasThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.finished.connect(self._on_empresas)
        self._threads.append(t); t.start()

    def _on_empresas(self, ok, data):
        self._set_enabled(True)
        if ok:
            self.eco_empresa.clear()
            for e in data: self.eco_empresa.addItem(f"{e['codigo']} - {e['fantasia']}", e['codigo'])
            self.eco_empresa.setEnabled(True); self.btn_eco_login.setEnabled(True)
            self._set_status(self.eco_dot, self.eco_status, f"{len(data)} empresas carregadas", True)
        else:
            self._set_status(self.eco_dot, self.eco_status, f"Falha: {data}", False)

    def _eco_login(self):
        self._set_enabled(False)
        self._set_status(self.eco_dot, self.eco_status, "Validando...")
        self._log("Autenticando...")
        t = LoginThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip(),
                        self.eco_user.text().strip(), self.eco_pass.text().strip(), self.eco_empresa.currentData() or "")
        t.log_signal.connect(lambda m, l: self._log(m, l))
        t.finished.connect(lambda ok, m: (
            self._set_enabled(True),
            self._set_status(self.eco_dot, self.eco_status, m, ok)))
        self._threads.append(t); t.start()

    def _scan_boletos(self):
        self._set_enabled(False)
        self.btn_scan.setVisible(False); self.btn_cancel_scan.setVisible(True)
        self._set_status(self.bol_dot, self.bol_status, "Preparando...")
        self.bol_bar.setValue(0); self.bol_bar.setVisible(True)
        self.bol_bar.setFormat("Preparando...")
        self.log_area.clear()
        self._log("Iniciando scan otimizado de boletos...")
        self._scan_thread = BoletoScanThread(
            self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        self._scan_thread.log_signal.connect(self._log)
        self._scan_thread.phase_signal.connect(lambda ph: self.bol_bar.setFormat(ph))
        self._scan_thread.progress_signal.connect(lambda cur, total: (
            self.bol_bar.setMaximum(total), self.bol_bar.setValue(cur),
            self.bol_bar.setFormat(f"{cur}/{total}"),
            self._set_status(self.bol_dot, self.bol_status, f"Processando: {cur}/{total}")))
        self._scan_thread.finished.connect(self._on_scan_done)
        self._threads.append(self._scan_thread); self._scan_thread.start()

    def _cancel_scan(self):
        if self._scan_thread:
            self._log("Cancelando scan...", "WARNING")
            self._scan_thread.stop()

    def _on_scan_done(self, ok, msg):
        self._scan_thread = None
        self.btn_cancel_scan.setVisible(False); self.btn_scan.setVisible(True)
        self._set_enabled(True)
        self.bol_bar.setVisible(True)
        if ok:
            self.bol_bar.setValue(self.bol_bar.maximum())
            self.bol_bar.setFormat("Concluido!")
            self._set_status(self.bol_dot, self.bol_status, msg, True)
        else:
            self.bol_bar.setFormat("Erro")
            self._set_status(self.bol_dot, self.bol_status, f"Falha: {msg}", False)

    def _limpar_boletos(self):
        reply = QMessageBox.question(self, "Limpar BOLETO_GERADO",
            "Tem certeza que deseja apagar TODOS os registros de BOLETO_GERADO?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        self._set_enabled(False)
        self._set_status(self.bol_dot, self.bol_status, "Limpando...")
        self._log("Apagando BOLETO_GERADO...")
        try:
            fb = FirebirdConn(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
            fb.connect()
            fb.executa("DELETE FROM BOLETO_GERADO")
            fb.close()
            self._set_enabled(True)
            self._set_status(self.bol_dot, self.bol_status, "Tabela BOLETO_GERADO limpa", True)
            self._log("BOLETO_GERADO limpo com sucesso", "OK")
        except Exception as e:
            self._set_enabled(True)
            self._set_status(self.bol_dot, self.bol_status, f"Erro: {e}", False)
            self._log(str(e), "ERROR")

    def _normalize_fb_path(self, path: str) -> str:
        path = path.strip()
        if path.startswith("\\\\") or path.startswith("//"):
            self._log(
                "Path UNC detectado! Firebird nao aceita \\\\server\\path.\n"
                "Use servidor:C:\\path (ex: srvlubri:C:\\ecosis\\dados\\banco.fdb)\n"
                "Ou caminho local (ex: C:\\ecosis\\dados\\banco.fdb)", "WARNING")
        return path.replace("\\\\", "\\").replace("\\", "/")

    def _save_env(self) -> bool:
        existing = _read_env()
        vals = {
            "FB_DATABASE": self._normalize_fb_path(self.fb_dsn.text()),
            "FB_USER": self.fb_user.text().strip(),
            "FB_PASSWORD": self.fb_pass.text().strip(),
        }
        for k, v in existing.items():
            if k not in vals or not vals[k]: vals[k] = v
        if not vals.get("JWT_SECRET"):
            vals["JWT_SECRET"] = uuid.uuid4().hex + uuid.uuid4().hex
        _RESOLVED["env"].write_text("\n".join([f"{k}={v}" for k, v in vals.items()]) + "\n", encoding="utf-8")
        return True

    def _save_and_launch(self):
        if not self._save_env(): return
        eco_u = self.eco_user.text().strip(); emp = self.eco_empresa.currentData() or ""
        if eco_u and emp:
            cache = Path.home() / ".econnect"; cache.mkdir(parents=True, exist_ok=True)
            (cache / "eco_cache.json").write_text(
                json.dumps({"eco_usuario": eco_u, "eco_empresa": emp, "eco_nome": eco_u, "role": "user"}), encoding="utf-8")
        exe = _RESOLVED.get("econnect_exe")
        if exe and exe.exists():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            QApplication.quit()
        else:
            QMessageBox.warning(self, "ECOnnect nao encontrado", str(exe))

    def closeEvent(self, event):
        for t in self._threads:
            if hasattr(t, 'stop'): t.stop()
        event.accept()


# ── Stylesheet ────────────────────────────────────────────────────

_ECO_STYLE = """
QMainWindow { background-color: #f0f2f5; }
QWidget { font-family: 'Segoe UI','Arial',sans-serif; font-size: 13px; color: #1a1a2e; }

#header { background-color: #00398a; border-bottom: 3px solid #fa8c20; }
#headerTitle { font-size: 22px; font-weight: 700; color: #ffffff; background: transparent; }
#headerSub { font-size: 13px; color: #b0cce8; background: transparent; }

#card { background: #ffffff; border: 1px solid #e0e4e8; border-radius: 10px; }
#cardTitle { font-size: 15px; font-weight: 700; color: #00398a; background: transparent; }
#cardDesc { font-size: 12px; color: #5c5c7a; background: transparent; line-height: 1.4; }

QLineEdit { border: 1.5px solid #d0d5dd; border-radius: 6px; padding: 7px 10px; background: #ffffff; color: #1a1a2e; font-size: 13px; min-height: 18px; }
QLineEdit:focus { border-color: #0e4f9c; background: #fafcff; }
QLineEdit:disabled { background: #f5f5f5; color: #999; }

QComboBox { border: 1.5px solid #d0d5dd; border-radius: 6px; padding: 7px 10px; background: #ffffff; color: #1a1a2e; font-size: 13px; min-height: 18px; }
QComboBox:focus { border-color: #0e4f9c; }
QComboBox:disabled { background: #f5f5f5; color: #999; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { border: 1px solid #d0d5dd; border-radius: 4px; background: #ffffff; selection-background-color: #e8f0fe; selection-color: #00398a; }

QPushButton { border: none; border-radius: 6px; padding: 8px 18px; font-size: 13px; font-weight: 600; background-color: #0e4f9c; color: #ffffff; min-height: 18px; }
QPushButton:hover { background-color: #00398a; }
QPushButton:pressed { background-color: #002d6e; }
QPushButton:disabled { background-color: #b0c4de; color: #d0d8e0; }
#btnLaunch { font-size: 15px; font-weight: 700; padding: 12px 24px; background-color: #27ae60; color: #ffffff; border-radius: 8px; }
#btnLaunch:hover { background-color: #219a52; }
#btnLaunch:disabled { background-color: #a0d8b0; color: #e0e8e0; }
#btnSmall { font-size: 12px; padding: 4px 12px; background-color: #ecf0f1; color: #555; border: 1px solid #d0d5dd; }
#btnSmall:hover { background-color: #d5dbdb; }

#bolBar, QProgressBar { border: none; border-radius: 6px; background-color: #e8ecf0; height: 22px; text-align: center; font-size: 12px; font-weight: 600; color: #1a1a2e; }
QProgressBar::chunk { background-color: #0e4f9c; border-radius: 6px; }

#logArea { border: 1px solid #e0e4e8; border-radius: 6px; padding: 10px; background: #f8f9fb; color: #2c3e50; font-family: 'Consolas','Courier New','Cascadia Code',monospace; font-size: 12px; min-height: 120px; max-height: 250px; }

#footer { background: #e8ecf0; border-top: 1px solid #d0d5dd; }
#pathLabel { font-size: 12px; color: #666; background: transparent; }

#scrollArea { background: transparent; border: none; }
#scrollContent { background: transparent; }

#statusDot { font-size: 16px; background: transparent; }
#statusText { font-size: 12px; color: #555; background: transparent; }

QFormLayout > QLabel { font-size: 13px; color: #333; background: transparent; }
QLabel { background: transparent; }
"""


def main():
    _resolve_paths()
    app = QApplication(sys.argv); app.setApplicationName("ECOnnect Inicializador")
    app.setStyleSheet(_ECO_STYLE)
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    icon_p = bundled / "frontend" / "assets" / "app_icon.ico"
    if icon_p.exists():
        from PySide6.QtGui import QIcon; app.setWindowIcon(QIcon(str(icon_p)))
    window = InicializadorWindow(); window.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
