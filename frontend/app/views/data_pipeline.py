import os
import json
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView


class DataPipelineView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.browser = QWebEngineView()
        self.browser.setStyleSheet("background: #0a0a1a;")

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        html_path = os.path.join(base_dir, "graphify-out", "graph-tech.html")
        json_path = os.path.join(base_dir, "graphify-out", "graph-enriched.json")

        if os.path.exists(html_path) and os.path.exists(json_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            with open(json_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
            graph_json = json.dumps(graph_data)
            html = html.replace("__GRAPH_DATA__", graph_json)
            self.browser.setHtml(html, QUrl.fromLocalFile(base_dir + "/"))
        else:
            self.browser.setHtml(
                "<body style='background:#0a0a1a;color:#c0c0e0;display:flex;"
                "align-items:center;justify-content:center;font-family:sans-serif;"
                "font-size:14px;'>Grafo nao encontrado. Execute graphify update primeiro.</body>"
            )

        layout.addWidget(self.browser)

    def refresh(self):
        self.browser.reload()
