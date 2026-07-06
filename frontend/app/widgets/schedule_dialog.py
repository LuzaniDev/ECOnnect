from PySide6.QtCore import Qt, QDateTime, QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QDateTimeEdit, QFrame, QDialogButtonBox,
    QGroupBox, QSpinBox, QCheckBox, QTimeEdit,
)


SCHEDULE_STYLE = ""


class ScheduleDialog(QDialog):
    def __init__(self, parent, client_count: int, template_name: str):
        super().__init__(parent)
        self.setWindowTitle("Agendar Envio")
        self.setMinimumSize(480, 520)
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

        # ── Agora ──
        self.radio_agora = QRadioButton("Enviar agora")
        self.radio_agora.setChecked(True)
        layout.addWidget(self.radio_agora)

        # ── Agendar ──
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

        # ── Recurrence ──
        self.repeat_group = QGroupBox("Recorrência")
        self.repeat_group.setEnabled(False)
        repeat_layout = QVBoxLayout(self.repeat_group)
        repeat_layout.setSpacing(8)

        self.repeat_none = QRadioButton("Não repetir")
        self.repeat_none.setChecked(True)
        repeat_layout.addWidget(self.repeat_none)

        hourly_row = QHBoxLayout()
        self.repeat_hourly = QRadioButton("A cada")
        self.repeat_hourly_spin = QSpinBox()
        self.repeat_hourly_spin.setMinimum(1)
        self.repeat_hourly_spin.setMaximum(168)
        self.repeat_hourly_spin.setValue(1)
        self.repeat_hourly_spin.setEnabled(False)
        hourly_row.addWidget(self.repeat_hourly)
        hourly_row.addWidget(self.repeat_hourly_spin)
        hourly_row.addWidget(QLabel("hora(s)"))
        hourly_row.addStretch()
        repeat_layout.addLayout(hourly_row)

        self.repeat_daily = QRadioButton("Diariamente")
        repeat_layout.addWidget(self.repeat_daily)

        weekly_wrap = QVBoxLayout()
        self.repeat_weekly = QRadioButton("Semanalmente")
        weekly_wrap.addWidget(self.repeat_weekly)
        days_row = QHBoxLayout()
        days_row.setContentsMargins(20, 0, 0, 0)
        self.day_checks = {}
        for day_name in ["Seg", "Ter", "Qua", "Qui", "Sex", "S\u00e1b", "Dom"]:
            cb = QCheckBox(day_name)
            cb.setEnabled(False)
            self.day_checks[day_name] = cb
            days_row.addWidget(cb)
        days_row.addStretch()
        weekly_wrap.addLayout(days_row)
        repeat_layout.addLayout(weekly_wrap)

        self.repeat_monthly = QRadioButton("Mensalmente")
        repeat_layout.addWidget(self.repeat_monthly)

        layout.addWidget(self.repeat_group)

        self.radio_agendar.toggled.connect(self._on_agendar_toggled)
        self.repeat_none.toggled.connect(self._on_repeat_changed)
        self.repeat_hourly.toggled.connect(self._on_repeat_changed)
        self.repeat_weekly.toggled.connect(self._on_repeat_changed)

        # ── Baseado no Vencimento ──
        self.radio_venc = QRadioButton("Baseado no Vencimento")
        layout.addWidget(self.radio_venc)

        venc_group = QGroupBox()
        venc_group.setEnabled(False)
        venc_layout = QVBoxLayout(venc_group)
        venc_layout.setSpacing(8)

        venc_antes_row = QHBoxLayout()
        self.radio_antes = QRadioButton()
        self.radio_antes.setChecked(True)
        self.spin_antes = QSpinBox()
        self.spin_antes.setMinimum(1)
        self.spin_antes.setMaximum(365)
        self.spin_antes.setValue(3)
        venc_antes_row.addWidget(self.radio_antes)
        venc_antes_row.addWidget(QLabel("dia(s) ANTES do vencimento"))
        venc_antes_row.addStretch()
        venc_layout.addLayout(venc_antes_row)

        self.radio_no_dia = QRadioButton("No dia do vencimento")
        venc_layout.addWidget(self.radio_no_dia)

        venc_depois_row = QHBoxLayout()
        self.radio_depois = QRadioButton()
        self.spin_depois = QSpinBox()
        self.spin_depois.setMinimum(1)
        self.spin_depois.setMaximum(365)
        self.spin_depois.setValue(3)
        venc_depois_row.addWidget(self.radio_depois)
        venc_depois_row.addWidget(QLabel("dia(s) APÓS o vencimento"))
        venc_depois_row.addStretch()
        venc_layout.addLayout(venc_depois_row)

        # Horario
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Horário de ativação:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(9, 0))
        time_row.addWidget(self.time_edit)
        time_row.addStretch()
        venc_layout.addLayout(time_row)

        layout.addWidget(venc_group)

        self.radio_venc.toggled.connect(venc_group.setEnabled)
        self.radio_antes.toggled.connect(lambda: self.spin_antes.setEnabled(True))
        self.radio_no_dia.toggled.connect(lambda: None)
        self.radio_depois.toggled.connect(lambda: self.spin_depois.setEnabled(True))

        # Ajustar spin enables
        self.spin_antes.setEnabled(True)
        self.spin_depois.setEnabled(False)

        self.radio_antes.toggled.connect(lambda e: self.spin_antes.setEnabled(e))
        self.radio_depois.toggled.connect(lambda e: self.spin_depois.setEnabled(e))

        layout.addStretch()

        # ── Buttons ──
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

    def _on_agendar_toggled(self, enabled):
        self.repeat_group.setEnabled(enabled)
        if enabled:
            self._on_repeat_changed()

    def _on_repeat_changed(self):
        self.repeat_hourly_spin.setEnabled(self.repeat_hourly.isChecked())
        for cb in self.day_checks.values():
            cb.setEnabled(self.repeat_weekly.isChecked())

    def get_schedule(self) -> dict:
        if self.radio_agora.isChecked():
            return {"mode": "now"}

        if self.radio_venc.isChecked():
            if self.radio_antes.isChecked():
                offset = -self.spin_antes.value()
            elif self.radio_no_dia.isChecked():
                offset = 0
            else:
                offset = self.spin_depois.value()
            return {
                "mode": "vencimento",
                "offset": offset,
                "time": self.time_edit.time().toString("HH:mm"),
            }

        repeat_type = "none"
        repeat_data = {}
        if self.repeat_hourly.isChecked():
            repeat_type = "hourly"
            repeat_data["interval"] = self.repeat_hourly_spin.value()
        elif self.repeat_daily.isChecked():
            repeat_type = "daily"
        elif self.repeat_weekly.isChecked():
            repeat_type = "weekly"
            days = []
            day_map = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "S\u00e1b": 5, "Dom": 6}
            for label, idx in day_map.items():
                if self.day_checks[label].isChecked():
                    days.append(idx)
            repeat_data["days"] = days if days else [0]
        elif self.repeat_monthly.isChecked():
            repeat_type = "monthly"

        return {
            "mode": "scheduled",
            "datetime": self.dt_picker.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "repeat": {
                "type": repeat_type,
                **repeat_data,
            },
        }
