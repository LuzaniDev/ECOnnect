from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QAbstractItemView,
)
from frontend.app.core.theme import theme_manager


def _status_colors():
    t = theme_manager.current()
    return {
        "Pendente": t.warning,
        "Enviado": t.success,
        "Cancelado": t.danger,
    }


class HistoryDialog(QDialog):
    def __init__(self, phone: str, requests: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Histórico — {phone}")
        self.setMinimumSize(700, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_frame = QFrame()
        t = theme_manager.current()
        header_frame.setStyleSheet(
            f"QFrame {{ background-color: {t.surface}; border-bottom: 1px solid {t.border}; }}"
        )
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Histórico de envios")
        title.setObjectName("title")
        header_layout.addWidget(title)

        phone_label = QLabel(f"Número: {phone}")
        phone_label.setObjectName("phone_label")
        header_layout.addWidget(phone_label)

        layout.addWidget(header_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Data/Hora", "Usuário", "Template", "Tag", "Status"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.table.horizontalHeader().setStyleSheet(
            "font-size: 12px;"
        )

        self.table.setRowCount(len(requests))
        for i, r in enumerate(requests):
            created = (r.get("created_at") or "")[:19].replace("T", " ")
            user = r.get("created_by_username", "")
            template = r.get("template_name", "")
            tag = r.get("tag") or "—"
            status_map = {
                "pending": "Pendente",
                "sent": "Enviado",
                "cancelled": "Cancelado",
            }
            status = status_map.get(r.get("status", ""), r.get("status", ""))

            self.table.setItem(i, 0, QTableWidgetItem(created))
            self.table.setItem(i, 1, QTableWidgetItem(user))
            self.table.setItem(i, 2, QTableWidgetItem(template))
            self.table.setItem(i, 3, QTableWidgetItem(tag))
            self.table.setItem(i, 4, QTableWidgetItem(status))

            for col in range(5):
                item = self.table.item(i, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)

            status_item = self.table.item(i, 4)
            if status_item:
                colors = _status_colors()
                color = colors.get(status, theme_manager.current().text_secondary)
                status_item.setForeground(QColor(color))

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Fechar")
        close_btn.setProperty("primary", True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.setContentsMargins(16, 12, 16, 12)
        layout.addLayout(btn_layout)
