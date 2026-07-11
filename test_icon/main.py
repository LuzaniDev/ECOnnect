import sys
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

app = QApplication(sys.argv)
w = QWidget()
w.setWindowTitle("Teste Icone")
w.resize(300, 200)
layout = QVBoxLayout(w)
lbl = QLabel("Icone test app")
layout.addWidget(lbl)
w.show()
sys.exit(app.exec())
