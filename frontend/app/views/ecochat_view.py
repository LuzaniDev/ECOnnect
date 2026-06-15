from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QListWidget, QListWidgetItem,
    QSplitter, QSizePolicy,
)
from frontend.app.widgets.worker import run_in_thread
from frontend.app.api import meta_api
from frontend.app.core.theme import theme_manager, _hex_to_rgb


class ChatBubble(QFrame):
    def __init__(self, text: str, timestamp: str, direction: str, status: str = ""):
        super().__init__()
        self.setObjectName("chatBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        t = theme_manager.current()
        is_out = direction == "outgoing"
        bg = t.primary if is_out else t.surface_elevated
        text_color = t.selection_text if is_out else t.text
        align = Qt.AlignRight if is_out else Qt.AlignLeft

        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"font-size: 13px; color: {text_color}; background: transparent;"
        )
        layout.addWidget(msg_label)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)

        time_label = QLabel(timestamp)
        time_label.setStyleSheet(f"font-size: 10px; color: {text_color}; opacity: 0.7; background: transparent;")
        meta_layout.addWidget(time_label)

        if is_out:
            status_map = {
                "sent": "✓",
                "delivered": "✓✓",
                "read": "✓✓",
                "failed": "✗",
            }
            icon = status_map.get(status, "⏳")
            status_label = QLabel(icon)
            status_label.setStyleSheet(f"font-size: 10px; color: {text_color}; background: transparent;")
            meta_layout.addWidget(status_label)

        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        border_radius = "12px 4px 12px 12px" if is_out else "4px 12px 12px 12px"
        self.setStyleSheet(f"""
            QFrame#chatBubble {{
                background-color: {bg};
                border-radius: {border_radius};
                max-width: 320px;
            }}
        """)

        if is_out:
            pass
        self.setMaximumWidth(400)


class ContactItem(QFrame):
    def __init__(self, phone: str, last_msg: str, last_time: str, unread: int = 0):
        super().__init__()
        self.phone = phone
        self.setObjectName("contactItem")
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        avatar = QLabel("📞")
        avatar.setStyleSheet("font-size: 20px; background: transparent;")
        layout.addWidget(avatar)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = QLabel(phone)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
        info.addWidget(name_label)

        preview = QLabel(last_msg[:40] + "..." if len(last_msg) > 40 else last_msg)
        preview.setStyleSheet("font-size: 11px; color: gray; background: transparent;")
        info.addWidget(preview)
        layout.addLayout(info, 1)

        time_label = QLabel(last_time)
        time_label.setStyleSheet("font-size: 10px; color: gray; background: transparent;")
        layout.addWidget(time_label)

        t = theme_manager.current()
        self.setStyleSheet(f"""
            QFrame#contactItem {{
                background: transparent; border-bottom: 1px solid {t.border};
            }}
            QFrame#contactItem:hover {{
                background-color: {t.surface};
            }}
        """)


class ECOchatView(QWidget):
    def __init__(self):
        super().__init__()
        self._messages: list[dict] = []
        self._contacts: list[str] = []
        self._selected_phone: str | None = None
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        t = theme_manager.current()
        left_header = QLabel("Conversas")
        left_header.setStyleSheet(
            f"font-size: 14px; font-weight: 700; padding: 16px; "
            f"border-bottom: 1px solid {t.border};"
        )
        left_layout.addWidget(left_header)

        self.contact_list = QListWidget()
        self.contact_list.setFrameShape(QFrame.NoFrame)
        self.contact_list.currentItemChanged.connect(self._on_contact_selected)
        self.contact_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; }} "
            f"QListWidget::item {{ border: none; }} "
            f"QListWidget::item:selected {{ background-color: {t.surface}; }}"
        )
        left_layout.addWidget(self.contact_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.chat_header = QLabel("Selecione uma conversa")
        self.chat_header.setStyleSheet(
            f"font-size: 14px; font-weight: 700; padding: 16px; "
            f"border-bottom: 1px solid {t.border};"
        )
        right_layout.addWidget(self.chat_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        scroll.setWidget(self.chat_container)
        right_layout.addWidget(scroll, 1)

        input_bar = QFrame()
        input_bar.setStyleSheet(f"border-top: 1px solid {t.border};")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Número do cliente para filtrar...")
        self.phone_input.setStyleSheet(
            f"background-color: {t.bg}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 8px 12px; font-size: 12px; color: {t.text};"
        )
        input_layout.addWidget(self.phone_input, 1)

        self.btn_filter = QPushButton("Filtrar")
        self.btn_filter.setCursor(Qt.PointingHandCursor)
        self.btn_filter.clicked.connect(self._apply_filter)
        input_layout.addWidget(self.btn_filter)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._load_messages)
        input_layout.addWidget(self.btn_refresh)

        right_layout.addWidget(input_bar)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([250, 550])
        splitter.setHandleWidth(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def refresh(self):
        self._load_messages()

    def _load_messages(self):
        run_in_thread(
            meta_api.list_messages,
            self._on_messages,
            lambda e: None,
        )

    def _on_messages(self, messages: list[dict]):
        self._messages = messages
        self._rebuild_contacts()
        self._rebuild_chat()

    def _rebuild_contacts(self):
        self.contact_list.clear()
        phones = set()
        for msg in self._messages:
            phones.add(msg.get("from_phone", ""))
            phones.add(msg.get("to_phone", ""))
        phones.discard("")

        sorted_phones = sorted(phones)
        self._contacts = list(sorted_phones)
        for phone in sorted_phones:
            last = next(
                (m for m in reversed(self._messages) if m.get("from_phone") == phone or m.get("to_phone") == phone),
                None,
            )
            last_text = (last.get("body") or "") if last else ""
            last_time = (last.get("created_at") or "")[:16] if last else ""
            item = QListWidgetItem()
            contact = ContactItem(phone, last_text, last_time)
            item.setSizeHint(contact.sizeHint())
            self.contact_list.addItem(item)
            self.contact_list.setItemWidget(item, contact)

    def _on_contact_selected(self, current, previous):
        if not current:
            self._selected_phone = None
            return
        widget = self.contact_list.itemWidget(current)
        if hasattr(widget, "phone"):
            self._selected_phone = widget.phone
            self._rebuild_chat()

    def _rebuild_chat(self):
        for i in reversed(range(self.chat_layout.count())):
            item = self.chat_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        self.chat_layout.addStretch()

        if not self._selected_phone:
            self.chat_header.setText("Selecione uma conversa")
            return

        self.chat_header.setText(f"📱 {self._selected_phone}")

        phone_msgs = [
            m for m in self._messages
            if m.get("from_phone") == self._selected_phone or m.get("to_phone") == self._selected_phone
        ]
        phone_msgs.sort(key=lambda m: m.get("created_at", ""))

        for msg in phone_msgs:
            direction = msg.get("direction", "outgoing")
            body = msg.get("body", "")
            ts = (msg.get("created_at") or "")[11:16]
            status = msg.get("status", "")
            bubble = ChatBubble(body, ts, direction, status)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)

    def _apply_filter(self):
        phone = self.phone_input.text().strip()
        if phone:
            run_in_thread(
                meta_api.list_messages,
                self._on_messages,
                lambda e: None,
                phone=phone,
            )
        else:
            self._load_messages()

    def _poll(self):
        self._load_messages()
