from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt


class StyledTable(QTableWidget):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)

    def add_row(self, row_data: list[str], user_data: object = None) -> int:
        row = self.rowCount()
        self.insertRow(row)
        for col, value in enumerate(row_data):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, col, item)
        if user_data is not None:
            for col in range(self.columnCount()):
                self.item(row, col).setData(Qt.UserRole, user_data)
        return row

    def clear_all(self):
        self.setRowCount(0)

    def selected_data(self) -> object | None:
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)
