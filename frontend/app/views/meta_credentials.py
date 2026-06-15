from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.widgets.dialogs import show_error, show_success
from frontend.app.api import meta_api
from frontend.app.core.theme import theme_manager, _hex_to_rgb


class MetaCredentialsView(QWidget):
    def __init__(self):
        super().__init__()
        self._dirty = False
        self._setup_ui()

    def _setup_ui(self):
        t = theme_manager.current()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Credenciais Meta")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text};")
        layout.addWidget(title)

        desc = QLabel(
            "Configure as credenciais da API do WhatsApp Business da Meta.\n"
            "Você precisa do WABA ID, Phone Number ID e um Access Token válido."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; padding-bottom: 8px;")
        layout.addWidget(desc)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        self.waba_input = QLineEdit()
        self.waba_input.setPlaceholderText("WhatsApp Business Account ID")
        self.waba_input.setStyleSheet(
            f"background-color: {t.bg}; border: 1px solid {t.border}; border-radius: 6px; "
            f"padding: 10px 14px; font-size: 13px; color: {t.text}; min-height: 18px;"
        )
        card_layout.addWidget(QLabel("WABA ID"))
        card_layout.addWidget(self.waba_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("ID do número de telefone")
        self.phone_input.setStyleSheet(
            f"background-color: {t.bg}; border: 1px solid {t.border}; border-radius: 6px; "
            f"padding: 10px 14px; font-size: 13px; color: {t.text}; min-height: 18px;"
        )
        card_layout.addWidget(QLabel("Phone Number ID"))
        card_layout.addWidget(self.phone_input)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Access Token permanente")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setStyleSheet(
            f"background-color: {t.bg}; border: 1px solid {t.border}; border-radius: 6px; "
            f"padding: 10px 14px; font-size: 13px; color: {t.text}; min-height: 18px;"
        )
        card_layout.addWidget(QLabel("Access Token"))
        card_layout.addWidget(self.token_input)

        layout.addWidget(card)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet(
            f"font-size: 12px; padding: 10px 14px; border-radius: 6px;"
        )
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_test = QPushButton("Testar Conexão")
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(self.btn_test)

        self.btn_save = QPushButton("Salvar")
        self.btn_save.setProperty("success", True)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def refresh(self):
        run_in_thread(
            meta_api.get_credentials,
            self._on_loaded,
            lambda e: None,
        )

    def _on_loaded(self, creds: dict | None):
        if creds:
            self.waba_input.setText(creds.get("waba_id", ""))
            self.phone_input.setText(creds.get("phone_number_id", ""))
            self.token_input.setText(creds.get("access_token", ""))
            if creds.get("is_verified"):
                self._set_status("✅ Credenciais conectadas e verificadas", "success")

    def _save(self):
        waba = self.waba_input.text().strip()
        phone = self.phone_input.text().strip()
        token = self.token_input.text().strip()

        if not waba or not phone or not token:
            show_error(self, "Erro", "Preencha todos os campos.")
            return

        self.btn_save.setEnabled(False)
        run_in_thread(
            meta_api.save_credentials,
            self._on_saved,
            self._on_error,
            {"waba_id": waba, "phone_number_id": phone, "access_token": token},
        )

    def _on_saved(self, result: dict):
        self.btn_save.setEnabled(True)
        self._dirty = True
        show_success(self, "OK", "Credenciais salvas com sucesso!")

    def _test_connection(self):
        waba = self.waba_input.text().strip()
        phone = self.phone_input.text().strip()
        token = self.token_input.text().strip()

        if not waba or not phone or not token:
            show_error(self, "Erro", "Preencha todos os campos para testar.")
            return

        self.btn_test.setEnabled(False)
        self._set_status("Testando conexão...", "info")
        run_in_thread(
            meta_api.test_connection,
            self._on_test_result,
            self._on_error,
            {"waba_id": waba, "phone_number_id": phone, "access_token": token},
        )

    def _on_test_result(self, result: dict):
        self.btn_test.setEnabled(True)
        if result.get("verified"):
            self._set_status("✅ " + result.get("message", "Conectado!"), "success")
        else:
            self._set_status("❌ " + result.get("message", "Falha na conexão"), "error")

    def _on_error(self, error: str):
        self.btn_test.setEnabled(True)
        self.btn_save.setEnabled(True)
        self._set_status("❌ " + error, "error")

    def _set_status(self, msg: str, kind: str):
        t = theme_manager.current()
        colors = {
            "success": f"color: {t.success}; background-color: rgba({_hex_to_rgb(t.success)}, 0.1); border: 1px solid rgba({_hex_to_rgb(t.success)}, 0.3);",
            "error": f"color: {t.danger}; background-color: rgba({_hex_to_rgb(t.danger)}, 0.1); border: 1px solid rgba({_hex_to_rgb(t.danger)}, 0.3);",
            "info": f"color: {t.info}; background-color: rgba({_hex_to_rgb(t.info)}, 0.1); border: 1px solid rgba({_hex_to_rgb(t.info)}, 0.3);",
        }
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"font-size: 12px; padding: 10px 14px; border-radius: 6px; {colors.get(kind, '')}")
        self.status_label.setVisible(True)
