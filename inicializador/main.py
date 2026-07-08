import sys
import os
import re
import uuid
import hashlib
import datetime
import subprocess
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox,
    QGroupBox, QComboBox, QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal

_RESOLVED = {}
_LINHA_REGEX = re.compile(r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}")


def _log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
        log_file = exe_dir / "inicializador.log"
        with open(str(log_file), "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] INIC: {msg}\n")
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


# ── Firebird conexao (sem ping quebrado) ──────────────────────────

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


# ── Funcoes de boleto (extraidas do boleto_pdf.py + boleto_watcher.py) ──

_FILENAME_REGEX = re.compile(r"^(.+?)(\d[\d_]*)_(\d+)\.pdf$")


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


# ── Threads ──────────────────────────────────────────────────────────

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
            # Upsert autonomias
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


class BoletoScanThread(QThread):
    finished = Signal(bool, str)
    log_signal = Signal(str, str)
    progress_signal = Signal(int, int)

    def __init__(self, dsn, user, password):
        super().__init__()
        self.dsn = dsn; self.fb_user = user; self.fb_pass = password

    def _l(self, m, l="INFO"): self.log_signal.emit(m, l)
    def _p(self, cur, total): self.progress_signal.emit(cur, total)

    def run(self):
        try:
            fb = FirebirdConn(self.dsn, self.fb_user, self.fb_pass)
            fb.connect(); self._l("Firebird conectado para scan de boletos")

            # 1. Ensure BOLETO_GERADO table
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

            # 2. List configs
            configs = fb.query("""SELECT EMPRESA, PORTADOR, DIRETORIOGERACAOBOLETO, PREFIXONOMENCLATURA
                FROM TCOBPARAMETROECOBRANCA
                WHERE DIRETORIOGERACAOBOLETO IS NOT NULL AND PREFIXONOMENCLATURA IS NOT NULL""")
            self._l(f"{len(configs)} configs de boleto encontradas")

            import fitz

            total_pdfs = 0
            todos_pdfs = []

            for row in configs:
                diretorio = str(row[2] or "").strip()
                if not diretorio or not os.path.isdir(diretorio):
                    self._l(f"Diretorio invalido: {diretorio}", "WARNING")
                    continue
                prefixo = str(row[3] or "").strip()
                empresa = str(row[0] or "").strip()
                portador = str(row[1] or "").strip()
                for root, _, files in os.walk(diretorio):
                    for fn in files:
                        if fn.lower().endswith(".pdf"):
                            todos_pdfs.append((os.path.join(root, fn), empresa, portador, prefixo))
                total_pdfs += len([f for f in os.listdir(diretorio) if f.lower().endswith(".pdf")])

            total = len(todos_pdfs)
            self._l(f"{total} PDFs encontrados para processar")

            if total == 0:
                fb.close()
                self.finished.emit(True, "Nenhum PDF para processar")
                return

            processados = 0
            erros = 0
            pulados = 0

            for idx, (caminho, empresa, portador, prefixo) in enumerate(todos_pdfs):
                nome = os.path.basename(caminho)
                m = _FILENAME_REGEX.match(nome)
                if not m:
                    pulados += 1
                    self._p(idx + 1, total)
                    continue
                _, num_boleto_raw, nosso_numero = m.groups()

                # Check if already processed
                r = fb.query("SELECT COUNT(*) FROM BOLETO_GERADO WHERE EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?",
                             (empresa, portador, nosso_numero))
                if r and r[0][0] > 0:
                    pulados += 1
                    self._p(idx + 1, total)
                    continue

                # Process PDF
                try:
                    doc = fitz.open(caminho)
                    texto = doc[0].get_text()
                    doc.close()
                except Exception:
                    erros += 1
                    self._l(f"Erro ao ler PDF: {nome}", "WARNING")
                    self._p(idx + 1, total)
                    continue

                linha = _extrair_linha(texto)
                if not linha:
                    erros += 1
                    self._p(idx + 1, total)
                    continue

                bc = _linha_para_barcode(linha)
                if not bc:
                    erros += 1
                    self._p(idx + 1, total)
                    continue

                # Look up parcela info
                r2 = fb.query("SELECT FIRST 1 IDTRECPARCELA, NUMEROBOLETO FROM TRECBOLETO "
                              "WHERE EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?",
                              (empresa, portador, nosso_numero))
                id_parc = r2[0][0] if r2 else None
                num_bol = r2[0][1] if r2 else None

                # Delete old + insert
                fb.executa("DELETE FROM BOLETO_GERADO WHERE EMPRESA=? AND PORTADOR=? AND NOSSONUMERO=?",
                           (empresa, portador, nosso_numero))
                fb.executa("INSERT INTO BOLETO_GERADO (EMPRESA, PORTADOR, NOSSONUMERO, IDPARCELA, "
                           "NUMEROBOLETO, CODIGOBARRAS, LINHADIGITAVEL, CAMINHOPDF, DATAGERACAO) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (empresa, portador, nosso_numero, id_parc, num_bol, bc, linha, caminho, datetime.datetime.now()))
                processados += 1
                self._l(f"Processado: {nome}")
                self._p(idx + 1, total)

            fb.close()
            self._l(f"Concluido: {processados} processados, {pulados} ja existentes, {erros} erros de {total} total")
            self.finished.emit(True, f"{processados} boletos processados, {pulados} ja existiam, {erros} erros")

        except Exception as e:
            import traceback
            self._l(str(e), "ERROR")
            for line in traceback.format_exc().splitlines(): self._l(line, "ERROR")
            self.finished.emit(False, str(e))


# ── UI ───────────────────────────────────────────────────────────────

class InicializadorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECOnnect Inicializador")
        self.setMinimumSize(560, 680)
        self._threads = []
        self._build_ui()
        self._load_env()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        title = QLabel("<h2>ECOnnect — Preparacao de Ambiente</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ── Firebird ──
        fb = QGroupBox("Conexao Firebird")
        fb_l = QFormLayout(fb)
        self.fb_dsn = QLineEdit("C:\\ecosis\\dados\\ECODADOS.ECO")
        self.fb_dsn.setToolTip(
            "Formato correto para servidor remoto:\n"
            "  servidor:C:\\caminho\\completo\\banco.fdb\n"
            "  Ex: srvlubri:C:\\ecosis\\dados\\ECODADOS.ECO\n\n"
            "Para arquivo local:\n"
            "  C:\\caminho\\arquivo.fdb\n\n"
            "NAO use \\\\servidor\\compartilhamento\\arquivo (UNC).\n"
            "Firebird nao aceita caminhos UNC diretamente.")
        self.fb_user = QLineEdit("SYSDBA"); self.fb_pass = QLineEdit("masterkey")
        self.fb_pass.setEchoMode(QLineEdit.Password)
        fb_l.addRow("Database:", self.fb_dsn); fb_l.addRow("Usuario:", self.fb_user); fb_l.addRow("Senha:", self.fb_pass)
        self.btn_test_fb = QPushButton("Testar Conexao"); self.btn_test_fb.clicked.connect(self._test_fb)
        fb_l.addRow(self.btn_test_fb)
        self.fb_status = QLabel(""); self.fb_status.setWordWrap(True)
        fb_l.addRow(self.fb_status)
        layout.addWidget(fb)

        # ── Login ECO ──
        eco = QGroupBox("Autenticacao ECO")
        eco_l = QFormLayout(eco)
        self.eco_user = QLineEdit(); self.eco_user.setPlaceholderText("usuario ECO (ex: SUPERVISOR)")
        self.eco_pass = QLineEdit(); self.eco_pass.setEchoMode(QLineEdit.Password); self.eco_pass.setPlaceholderText("senha ECO")
        self.eco_empresa = QComboBox(); self.eco_empresa.setEnabled(False)
        eco_l.addRow("Usuario:", self.eco_user); eco_l.addRow("Senha:", self.eco_pass); eco_l.addRow("Empresa:", self.eco_empresa)
        er = QHBoxLayout()
        self.btn_list_emp = QPushButton("Listar Empresas"); self.btn_list_emp.clicked.connect(self._list_empresas); self.btn_list_emp.setEnabled(False)
        self.btn_eco_login = QPushButton("Validar Login"); self.btn_eco_login.clicked.connect(self._eco_login); self.btn_eco_login.setEnabled(False)
        er.addWidget(self.btn_list_emp); er.addWidget(self.btn_eco_login)
        eco_l.addRow(er)
        self.eco_status = QLabel(""); self.eco_status.setWordWrap(True)
        eco_l.addRow(self.eco_status)
        layout.addWidget(eco)

        # ── Boleto ──
        bol = QGroupBox("Processamento de Boletos")
        bol_l = QVBoxLayout(bol)
        bol_desc = QLabel(
            "Escaneia todos os PDFs de boleto nos diretorios configurados no Firebird\n"
            "(TCOBPARAMETROECOBRANCA) e registra em BOLETO_GERADO.\n"
            "Isso evita que o ECOnnect precise fazer esse processo pesado na inicializacao."
        )
        bol_desc.setWordWrap(True)
        bol_l.addWidget(bol_desc)

        bp = QHBoxLayout()
        self.btn_scan = QPushButton("INICIAR SCAN COMPLETO")
        self.btn_scan.clicked.connect(self._scan_boletos)
        self.btn_scan.setStyleSheet("QPushButton { padding: 10px 20px; font-weight: bold; font-size: 13px; }")
        self.btn_scan.setEnabled(False)
        self.btn_limpar = QPushButton("Limpar BOLETO_GERADO")
        self.btn_limpar.clicked.connect(self._limpar_boletos)
        self.btn_limpar.setEnabled(False)
        bp.addWidget(self.btn_scan); bp.addWidget(self.btn_limpar)
        bol_l.addLayout(bp)

        self.bol_bar = QProgressBar(); self.bol_bar.setVisible(False)
        bol_l.addWidget(self.bol_bar)
        self.bol_status = QLabel(""); self.bol_status.setWordWrap(True)
        bol_l.addWidget(self.bol_status)
        layout.addWidget(bol)

        # ── PostgreSQL ──
        pg = QGroupBox("PostgreSQL")
        pg_l = QFormLayout(pg)
        self.pg_host = QLineEdit("localhost"); self.pg_port = QLineEdit("5432")
        self.pg_user = QLineEdit("postgres"); self.pg_pass = QLineEdit(); self.pg_pass.setEchoMode(QLineEdit.Password)
        self.pg_db = QLineEdit("econnect_db")
        pg_l.addRow("Host:", self.pg_host); pg_l.addRow("Porta:", self.pg_port); pg_l.addRow("Usuario:", self.pg_user)
        pg_l.addRow("Senha:", self.pg_pass); pg_l.addRow("Database:", self.pg_db)
        self.btn_setup_pg = QPushButton("Configurar PostgreSQL"); self.btn_setup_pg.clicked.connect(self._setup_pg)
        pg_l.addRow(self.btn_setup_pg)
        self.pg_status = QLabel(""); self.pg_status.setWordWrap(True)
        pg_l.addRow(self.pg_status)
        layout.addWidget(pg)

        # ── Log ──
        self.progress = QProgressBar(); self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True); self.log_area.setMaximumHeight(150); self.log_area.setVisible(False)
        layout.addWidget(self.log_area)

        # ── Actions ──
        br = QHBoxLayout()
        self.btn_launch = QPushButton("Salvar e Abrir ECOnnect")
        self.btn_launch.clicked.connect(self._save_and_launch)
        self.btn_launch.setStyleSheet("QPushButton { padding: 10px 20px; font-weight: bold; font-size: 14px; }")
        br.addWidget(self.btn_launch)
        layout.addLayout(br)

        self.path_label = QLabel(""); self.path_label.setTextFormat(Qt.RichText); self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

    def _l(self, m, l="INFO"):
        self.log_area.setVisible(True); self.log_area.append(m); _log(m, l)

    def _set_enabled(self, en: bool):
        self.btn_test_fb.setEnabled(en); self.btn_list_emp.setEnabled(en and self.btn_list_emp.isEnabled())
        self.btn_eco_login.setEnabled(en and self.btn_eco_login.isEnabled())
        self.btn_scan.setEnabled(en and self.btn_scan.isEnabled())
        self.btn_limpar.setEnabled(en and self.btn_limpar.isEnabled())
        self.btn_setup_pg.setEnabled(en); self.btn_launch.setEnabled(en)
        self.progress.setVisible(not en)

    def _load_env(self):
        _resolve_paths()
        vals = _read_env()
        if vals.get("FB_DATABASE"): self.fb_dsn.setText(vals["FB_DATABASE"])
        if vals.get("FB_USER"): self.fb_user.setText(vals["FB_USER"])
        if vals.get("FB_PASSWORD"): self.fb_pass.setText(vals["FB_PASSWORD"])
        if vals.get("DB_HOST"): self.pg_host.setText(vals["DB_HOST"])
        if vals.get("DB_PORT"): self.pg_port.setText(vals["DB_PORT"])
        if vals.get("DB_USER"): self.pg_user.setText(vals["DB_USER"])
        if vals.get("DB_PASSWORD"): self.pg_pass.setText(vals["DB_PASSWORD"])
        if vals.get("DB_NAME"): self.pg_db.setText(vals["DB_NAME"])
        exe_path = _RESOLVED.get("econnect_exe"); env_path = _RESOLVED.get("env")
        parts = []
        if env_path: parts.append(f".env: <b>{env_path}</b> ({'EXISTE' if env_path.exists() else 'NAO EXISTE'})")
        if exe_path: parts.append(f"ECOnnect: <b>{exe_path}</b> ({'ENCONTRADO' if exe_path.exists() else 'NAO ENCONTRADO'})")
        self.path_label.setText("<br>".join(parts))

    # ── Firebird ──
    def _test_fb(self):
        self._set_enabled(False)
        self.fb_status.setText("Testando..."); self.fb_status.setStyleSheet("color: gray;")
        t = TestFbThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.finished.connect(lambda ok, m: (
            self._set_enabled(True), self.fb_status.setText(m),
            self.fb_status.setStyleSheet("color: green;" if ok else "color: red;"),
            self.btn_list_emp.setEnabled(ok), self.btn_scan.setEnabled(ok), self.btn_limpar.setEnabled(ok)))
        self._threads.append(t); t.start()

    def _list_empresas(self):
        self._set_enabled(False)
        self.eco_status.setText("Listando..."); self.eco_status.setStyleSheet("color: gray;")
        self.log_area.clear(); self.log_area.setVisible(True); self.log_area.append("[INFO] Listando empresas...")
        t = ListEmpresasThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.finished.connect(self._on_empresas)
        self._threads.append(t); t.start()

    def _on_empresas(self, ok, data):
        self._set_enabled(True)
        if ok:
            self.eco_empresa.clear()
            for e in data: self.eco_empresa.addItem(f"{e['codigo']} - {e['fantasia']}", e['codigo'])
            self.eco_empresa.setEnabled(True); self.btn_eco_login.setEnabled(True)
            self.eco_status.setText(f"{len(data)} empresas"); self.eco_status.setStyleSheet("color: green;")
            self.log_area.append(f"[INFO] {len(data)} empresas carregadas")
        else:
            self.eco_status.setText(f"Falha: {data}"); self.eco_status.setStyleSheet("color: red;")

    def _eco_login(self):
        self._set_enabled(False)
        self.eco_status.setText("Validando..."); self.eco_status.setStyleSheet("color: gray;")
        self.log_area.clear(); self.log_area.setVisible(True); self.log_area.append("[INFO] Autenticando...")
        t = LoginThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip(),
                        self.eco_user.text().strip(), self.eco_pass.text().strip(), self.eco_empresa.currentData() or "")
        t.log_signal.connect(lambda m, l: self.log_area.append(f"[{l}] {m}"))
        t.finished.connect(lambda ok, m: (
            self._set_enabled(True), self.eco_status.setText(m),
            self.eco_status.setStyleSheet("color: green;" if ok else "color: red;")))
        self._threads.append(t); t.start()

    # ── Boletos ──
    def _scan_boletos(self):
        self._set_enabled(False)
        self.bol_status.setText("Escaneando..."); self.bol_status.setStyleSheet("color: gray;")
        self.bol_bar.setValue(0); self.bol_bar.setVisible(True)
        self.log_area.clear(); self.log_area.setVisible(True); self.log_area.append("[INFO] Iniciando scan de boletos...")
        t = BoletoScanThread(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
        t.log_signal.connect(lambda m, l: self.log_area.append(f"[{l}] {m}"))
        t.progress_signal.connect(lambda cur, total: (
            self.bol_bar.setMaximum(total), self.bol_bar.setValue(cur),
            self.bol_status.setText(f"Processando: {cur}/{total}")))
        t.finished.connect(lambda ok, m: (
            self._set_enabled(True), self.bol_bar.setVisible(False),
            self.bol_status.setText(m), self.bol_status.setStyleSheet("color: green;" if ok else "color: red;")))
        self._threads.append(t); t.start()

    def _limpar_boletos(self):
        reply = QMessageBox.question(self, "Limpar BOLETO_GERADO",
            "Tem certeza que deseja apagar TODOS os registros de BOLETO_GERADO?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        self._set_enabled(False)
        self.bol_status.setText("Limpando..."); self.bol_status.setStyleSheet("color: gray;")
        self.log_area.clear(); self.log_area.setVisible(True)
        self.log_area.append("[INFO] Apagando BOLETO_GERADO...")
        try:
            fb = FirebirdConn(self.fb_dsn.text().strip(), self.fb_user.text().strip(), self.fb_pass.text().strip())
            fb.connect()
            fb.executa("DELETE FROM BOLETO_GERADO")
            fb.close()
            self.log_area.append("[INFO] BOLETO_GERADO limpo")
            self._set_enabled(True)
            self.bol_status.setText("Tabela BOLETO_GERADO limpa"); self.bol_status.setStyleSheet("color: green;")
        except Exception as e:
            self._set_enabled(True)
            self.bol_status.setText(f"Erro: {e}"); self.bol_status.setStyleSheet("color: red;")

    # ── PostgreSQL ──
    def _setup_pg(self):
        self._set_enabled(False)
        self.pg_status.setText("Configurando..."); self.pg_status.setStyleSheet("color: gray;")
        self.log_area.clear(); self.log_area.setVisible(True); self.log_area.append("[INFO] Configurando PostgreSQL...")
        import asyncio, asyncpg
        async def _setup():
            try:
                dsn = f"postgresql://postgres:{self.pg_pass.text().strip()}@{self.pg_host.text().strip()}:{self.pg_port.text().strip()}/postgres"
                conn = await asyncpg.connect(dsn, timeout=5)
                u = self.pg_user.text().strip(); p = self.pg_pass.text().strip(); d = self.pg_db.text().strip()
                for r in await conn.fetch("SELECT 1 FROM pg_roles WHERE rolname=$1", u):
                    pass
                if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", u):
                    await conn.execute(f'CREATE USER "{u}" WITH PASSWORD $1', p)
                    self.log_area.append(f"[INFO] Usuario '{u}' criado")
                else:
                    await conn.execute(f'ALTER USER "{u}" WITH PASSWORD $1', p)
                if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", d):
                    await conn.execute(f'CREATE DATABASE "{d}" OWNER "{u}"')
                    self.log_area.append(f"[INFO] Database '{d}' criado")
                await conn.close()
                self.log_area.append("[INFO] PostgreSQL OK")
                self._set_enabled(True)
                self.pg_status.setText("PostgreSQL configurado"); self.pg_status.setStyleSheet("color: green;")
            except Exception as e:
                self._set_enabled(True)
                self.pg_status.setText(f"Erro: {e}"); self.pg_status.setStyleSheet("color: red;")
        asyncio.run(_setup())

    # ── Save & Launch ──
    def _normalize_fb_path(self, path: str) -> str:
        path = path.strip()
        if path.startswith("\\\\") or path.startswith("//"):
            self.log_area.append(
                "[AVISO] Path UNC detectado! Firebird nao aceita \\\\server\\path.\n"
                "  Use servidor:C:\\path (ex: srvlubri:C:\\ecosis\\dados\\banco.fdb)\n"
                "  Ou caminho local (ex: C:\\ecosis\\dados\\banco.fdb)", "WARNING")
        return path.replace("\\\\", "\\").replace("\\", "/")

    def _save_env(self) -> bool:
        vals = {
            "FB_DATABASE": self._normalize_fb_path(self.fb_dsn.text()), "FB_USER": self.fb_user.text().strip(),
            "FB_PASSWORD": self.fb_pass.text().strip(), "DB_HOST": self.pg_host.text().strip(),
            "DB_PORT": self.pg_port.text().strip(), "DB_USER": self.pg_user.text().strip(),
            "DB_PASSWORD": self.pg_pass.text().strip(), "DB_NAME": self.pg_db.text().strip(),
        }
        existing = _read_env()
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


_ECO_STYLE = """
QMainWindow, QWidget { background-color: #f0f3f5; color: #1a1a2e; font-family: 'Segoe UI','Arial',sans-serif; font-size: 13px; }
QLabel { background: transparent; color: #1a1a2e; }
QLabel[heading="true"] { font-size: 20px; font-weight: 700; color: #00398a; }
QLabel[subheading="true"] { font-size: 13px; color: #5c88b7; }
QLineEdit { border: 1.5px solid #dce1e5; border-radius: 6px; padding: 7px 10px; background: #ffffff; color: #1a1a2e; font-size: 13px; }
QLineEdit:focus { border-color: #0e4f9c; }
QPushButton { border: none; border-radius: 6px; padding: 8px 18px; font-size: 13px; font-weight: 600; background-color: #0e4f9c; color: white; }
QPushButton:hover { background-color: #00398a; }
QPushButton:disabled { background-color: #b0c4de; color: #e0e0e0; }
QPushButton[accent="true"] { background-color: #fa8c20; color: white; }
QPushButton[accent="true"]:hover { background-color: #e07a10; }
QPushButton[ghost="true"] { background-color: transparent; color: #0e4f9c; border: 1.5px solid #0e4f9c; }
QPushButton[ghost="true"]:hover { background-color: #0e4f9c; color: white; }
QPushButton[success="true"] { background-color: #2ecc71; color: white; }
QGroupBox { font-size: 14px; font-weight: 600; color: #00398a; border: 1.5px solid #dce1e5; border-radius: 8px; margin-top: 12px; padding: 16px 12px 12px 12px; background: #ffffff; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; background: #ffffff; }
QProgressBar { border: none; border-radius: 6px; background-color: #dce1e5; height: 8px; text-align: center; }
QProgressBar::chunk { background-color: #0e4f9c; border-radius: 6px; }
QTextEdit { border: 1.5px solid #dce1e5; border-radius: 6px; padding: 8px; background: #ffffff; color: #1a1a2e; font-family: 'Consolas','Courier New',monospace; font-size: 12px; }
QComboBox { border: 1.5px solid #dce1e5; border-radius: 6px; padding: 7px 10px; background: #ffffff; color: #1a1a2e; }
QComboBox:focus { border-color: #0e4f9c; }
QComboBox::drop-down { border: none; width: 24px; }
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
