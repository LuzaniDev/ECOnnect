import math
import random
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


COLORS = {"firebird": QColor("#4facfe"), "postgresql": QColor("#43e97b"),
          "api": QColor("#fa709a"), "code": QColor("#a78bfa")}
GROUP_NAMES = {"firebird": "Firebird", "postgresql": "PostgreSQL", "api": "API", "code": "Codigo"}


def _build_data():
    nodes = []
    links = []

    # Firebird tables
    fb_tables = [
        ("TRecParcela", "Parcelas do contas a receber"),
        ("TRecClienteGeral", "Dados cadastrais dos clientes"),
        ("TRecCliente", "Configuracoes por cliente"),
        ("TRecDocumento", "Documentos do contas a receber"),
        ("TRecTipoDocumento", "Tipos de documento (DUP, CHQ, BOL)"),
        ("TRECBOLETO", "Boletos registrados"),
        ("TRecParametro", "Parametros de cobranca"),
        ("TCOBPARAMETROECOBRANCA", "Configuracao de cobranca bancaria"),
        ("TBANCONTA", "Contas bancarias"),
        ("TGerEmpresa", "Empresas do sistema ECO"),
        ("TGerUsuario", "Usuarios do sistema ECO"),
        ("TRECTIPOCLIENTE", "Tipos de cliente"),
        ("BOLETO_GERADO", "Boletos processados pelo watcher"),
    ]
    for name, desc in fb_tables:
        nodes.append({"id": f"fb_{name.lower()}", "label": name, "group": "firebird",
                       "description": f"{desc} (Firebird)"})

    # PostgreSQL tables
    pg_tables = [
        ("users", "Usuarios do app"),
        ("templates", "Templates de mensagem"),
        ("requests", "Requisicoes de envio"),
        ("integration_configs", "Configuracoes de integracao"),
        ("audit_logs", "Logs de auditoria"),
        ("company_configs", "Config de conexao Firebird"),
        ("sql_variables", "Variaveis SQL"),
        ("meta_credentials", "Credenciais Meta/WhatsApp"),
        ("meta_messages", "Mensagens WhatsApp"),
    ]
    for name, desc in pg_tables:
        nodes.append({"id": f"pg_{name}", "label": name, "group": "postgresql",
                       "description": f"{desc} (PostgreSQL)"})

    # API endpoints
    endpoints = [
        ("/api/auth", "Autenticacao (login, eco-login)", "users"),
        ("/api/templates", "CRUD de templates", "templates"),
        ("/api/requests", "CRUD de requisicoes", "requests"),
        ("/api/integrations", "CRUD de integracoes", "integration_configs"),
        ("/api/users", "Gerenciamento de usuarios", "users"),
        ("/api/dashboard", "Metricas do dashboard", None),
        ("/api/audit", "Logs de auditoria", "audit_logs"),
        ("/api/company-config", "Config de conexao Firebird", "company_configs"),
        ("/api/sql-variables", "Variaveis SQL", "sql_variables"),
        ("/api/cobranca", "Verificacao de cobranca", "requests"),
        ("/api/meta", "Integracao WhatsApp", "meta_messages"),
        ("/webhook/meta", "Webhook WhatsApp", "meta_messages"),
    ]
    for path, desc, model in endpoints:
        eid = "api_" + path.strip("/").replace("/", "_")
        nodes.append({"id": eid, "label": path, "group": "api",
                       "description": f"{desc} (API)"})
        if model:
            links.append({"source": eid, "target": f"pg_{model}", "label": "acessa"})

    # Connections: Firebird -> API
    fb_api = {
        "fb_trecparcela": ["api_templates", "api_requests"],
        "fb_trecclientegeral": ["api_requests"],
        "fb_treccliente": ["api_requests"],
        "fb_tgerempresa": ["api_auth"],
        "fb_tgerusuario": ["api_auth"],
    }
    for fb_id, apis in fb_api.items():
        for api in apis:
            links.append({"source": fb_id, "target": api, "label": "alimenta"})

    return nodes, links


class _GraphWidget(QWidget):
    def __init__(self, nodes, links):
        super().__init__()
        self._nodes = nodes
        self._links = links
        self._node_map = {n["id"]: n for n in nodes}
        self._link_list = []
        for l in links:
            s = l.get("source", ""); t = l.get("target", "")
            if isinstance(s, dict): s = s.get("id", "")
            if isinstance(t, dict): t = t.get("id", "")
            if s in self._node_map and t in self._node_map:
                self._link_list.append((self._node_map[s], self._node_map[t], l.get("label", "")))
        self._run_layout()
        self.setMouseTracking(True)
        self._hover = None
        self._ox = 0; self._oy = 0
        self._scale = 1.0
        self._drag = False
        self._dsx = 0; self._dsy = 0
        self._dox = 0; self._doy = 0

    def _run_layout(self):
        w, h = 1200, 800
        for n in self._nodes:
            n["_x"] = random.random() * w
            n["_y"] = random.random() * h
            n["_vx"] = 0; n["_vy"] = 0
        for _ in range(80):
            for n in self._nodes:
                fx = (w/2 - n["_x"]) * 0.001
                fy = (h/2 - n["_y"]) * 0.001
                for o in self._nodes:
                    if o is n: continue
                    dx = n["_x"] - o["_x"]; dy = n["_y"] - o["_y"]
                    d2 = dx*dx + dy*dy or 1
                    fx += dx / d2 * 4000; fy += dy / d2 * 4000
                for s, t, _ in self._link_list:
                    if s is n:
                        dx = t["_x"] - s["_x"]; dy = t["_y"] - s["_y"]
                        d = math.sqrt(dx*dx + dy*dy) or 1
                        f = (d - 100) * 0.005
                        fx += dx/d * f
                    if t is n:
                        dx = s["_x"] - t["_x"]; dy = s["_y"] - t["_y"]
                        d = math.sqrt(dx*dx + dy*dy) or 1
                        f = (d - 100) * 0.005
                        fx += dx/d * f
                n["_vx"] = (n["_vx"] + fx) * 0.85
                n["_vy"] = (n["_vy"] + fy) * 0.85
                n["_x"] += n["_vx"]; n["_y"] += n["_vy"]
                n["_x"] = max(20, min(w-20, n["_x"]))
                n["_y"] = max(20, min(h-20, n["_y"]))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0a0a1a"))
        p.translate(self._ox, self._oy)
        p.scale(self._scale, self._scale)

        sf = QFont("system-ui", 7)
        for s, t, label in self._link_list:
            col = QColor(79, 172, 254, 50) if label == "alimenta" else \
                  QColor(250, 112, 154, 40) if label == "acessa" else \
                  QColor(167, 139, 250, 20)
            p.setPen(QPen(col, 1.5 if label == "alimenta" else 0.8))
            p.drawLine(QPointF(s["_x"], s["_y"]), QPointF(t["_x"], t["_y"]))

        for n in self._nodes:
            g = n.get("group", "code")
            col = COLORS.get(g, QColor("#555577"))
            x, y = n["_x"], n["_y"]
            r = 8 if g == "firebird" else 7 if g == "postgresql" else 5
            is_hover = n is self._hover
            p.setBrush(col)
            p.setPen(QPen(QColor(255,255,255,80 if is_hover else 0), 1.2 if is_hover else 0))
            p.drawEllipse(QPointF(x, y), r * (1.5 if is_hover else 1), r * (1.5 if is_hover else 1))
            if g in ("firebird", "postgresql"):
                label = n.get("label", "")
                if len(label) > 22: label = label[:20] + ".."
                p.setFont(sf)
                p.setPen(QColor(192, 192, 224, 100))
                p.drawText(QPointF(x + r + 4, y + 3), label)

        if self._hover:
            p.resetTransform()
            n = self._hover
            g = n.get("group", "code")
            grp = GROUP_NAMES.get(g, g)
            p.setFont(QFont("system-ui", 10, QFont.Bold))
            p.setPen(QColor(224, 224, 240))
            p.drawText(10, 30, f"{n.get('label','')}  |  {grp}")
            desc = n.get("description", "")
            if desc:
                p.setFont(QFont("system-ui", 9))
                p.setPen(QColor(160, 160, 180))
                p.drawText(10, 48, desc)

        p.end()

    def mouseMoveEvent(self, event):
        mx = (event.position().x() - self._ox) / self._scale
        my = (event.position().y() - self._oy) / self._scale
        if self._drag:
            self._ox = self._dox + (event.position().x() - self._dsx)
            self._oy = self._doy + (event.position().y() - self._dsy)
            self.update(); return
        found = None
        for n in self._nodes:
            dx = mx - n["_x"]; dy = my - n["_y"]
            r = 8 if n.get("group") == "firebird" else 7 if n.get("group") == "postgresql" else 5
            if dx*dx + dy*dy < (r+5)*(r+5): found = n; break
        self._hover = found
        self.setCursor(Qt.PointingHandCursor if found else Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = True
            self._dsx = event.position().x()
            self._dsy = event.position().y()
            self._dox = self._ox; self._doy = self._oy

    def mouseReleaseEvent(self, event):
        self._drag = False

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        self._scale = max(0.3, min(5, self._scale * factor))
        self.update()


class DataPipelineView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._graph = None
        self._msg = QLabel("Carregando...")
        self._msg.setAlignment(Qt.AlignCenter)
        self._msg.setStyleSheet("background:#0a0a1a;color:#8888aa;font-size:13px;")
        layout.addWidget(self._msg)
        self._load_data()

    def _load_data(self):
        nodes, links = _build_data()
        if not nodes:
            self._msg.setText("Sem dados.")
            return
        if self._graph:
            self.layout().removeWidget(self._graph)
            self._graph.deleteLater()
        self._graph = _GraphWidget(nodes, links)
        self.layout().addWidget(self._graph)
        self._msg.hide()

    def refresh(self):
        self._load_data()
