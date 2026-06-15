from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QDateTimeEdit, QFrame, QDialogButtonBox,
)


SCHEDULE_STYLE = ""


class ScheduleDialog(QDialog):
    def __init__(self, parent, client_count: int, template_name: str):
        super().__init__(parent)
        self.setWindowTitle("Configurar Agendamento")
        self.setMinimumSize(480, 280)
        self.setStyleSheet(SCHEDULE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Agendar Envio")
        title.setStyleSheet("font-size: 20px; font-weight: 800;")
        layout.addWidget(title)

        info = QLabel(
            f"{client_count} cliente{'s' if client_count != 1 else ''} selecionado{'s' if client_count != 1 else ''} · "
            f"Template: {template_name or 'Nenhum'}"
        )
        info.setStyleSheet("font-size: 12px; padding-bottom: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.radio_agora = QRadioButton("Enviar agora")
        self.radio_agora.setChecked(True)
        layout.addWidget(self.radio_agora)

        self.radio_agendar = QRadioButton("Agendar para:")
        layout.addWidget(self.radio_agendar)

        self.dt_picker = QDateTimeEdit()
        self.dt_picker.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.dt_picker.setCalendarPopup(True)
        self.dt_picker.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_picker.setEnabled(False)
        self.dt_picker.setMinimumDateTime(QDateTime.currentDateTime())
        layout.addWidget(self.dt_picker)

        self.radio_agendar.toggled.connect(self.dt_picker.setEnabled)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("ghost", True)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("Confirmar")
        btn_confirm.setProperty("primary", True)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)

    def get_schedule(self) -> dict:
        if self.radio_agora.isChecked():
            return {"mode": "now"}
        return {
            "mode": "scheduled",
            "datetime": self.dt_picker.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
        }
