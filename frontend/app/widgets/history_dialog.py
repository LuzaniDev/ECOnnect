from PySide6.QtCore import Qt
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


STATUS_COLORS = {
    "Pendente": "#f8891d",
    "Enviado": "#22c55e",
    "Cancelado": "#ef4444",
}


class HistoryDialog(QDialog):
    def __init__(self, phone: str, requests: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Histórico — {phone}")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0a1220;
                color: #f1f5f9;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: 700;
                color: #f1f5f9;
                padding: 20px 24px 4px 24px;
                
            }
            QLabel#phone_label {
                font-size: 13px;
                color: #64748b;
                padding: 0 24px 16px 24px;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background-color: #141d32; border-bottom: 1px solid #1e2d4a; }"
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

        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #0d1525;
                border: none;
                color: #f1f5f9;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 10px 14px;
                border-bottom: 1px solid #1a2640;
            }
            QTableWidget::item:selected {
                background-color: rgba(1, 73, 152, 0.3);
            }
            QTableWidget::item:alternate {
                background-color: #0a1220;
            }
            QHeaderView::section {
                background-color: #0a1220;
                color: #94a3b8;
                padding: 12px 14px;
                border: none;
                border-bottom: 2px solid #014998;
                font-weight: bold;
                font-size: 12px;
            }
        """
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
                color = STATUS_COLORS.get(status, "#64748b")
                status_item.setForeground(color)

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Fechar")
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #014998;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 28px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #025db8; }
        """
        )
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.setContentsMargins(16, 12, 16, 12)
        layout.addLayout(btn_layout)
