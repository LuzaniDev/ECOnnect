from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QStackedLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from frontend.app.core.theme import theme_manager

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)


class WhatsWebView(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        t = theme_manager.current()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(_CHROME_UA)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        profile.setPersistentStoragePath("./whatsweb_profile")

        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        stack = QStackedLayout()
        layout.addLayout(stack)

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://web.whatsapp.com"))
        stack.addWidget(self.browser)

        self.loading_label = QLabel("Carregando WhatsApp Web...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet(
            f"font-size: 14px; color: {t.text_secondary}; padding: 20px;"
        )
        stack.addWidget(self.loading_label)

        stack.setCurrentWidget(self.loading_label)

        self.browser.loadFinished.connect(lambda: stack.setCurrentWidget(self.browser))
