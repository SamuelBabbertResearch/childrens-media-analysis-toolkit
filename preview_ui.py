import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QComboBox, QLineEdit, QTabWidget, QGroupBox, 
    QLabel, QFormLayout
)

app = QApplication(sys.argv)

# Load the QSS file
with open("GeminiPipeline.qss", "r") as f:
    app.setStyleSheet(f.read())

window = QMainWindow()
window.setWindowTitle("CMAT Desktop Preview")
window.resize(500, 380)

central = QWidget()
layout = QVBoxLayout(central)

# 1. Path Display Label
path_row = QHBoxLayout()
path_row.addWidget(QLabel("Root folder:"))
path_lbl = QLabel(r"C:\Users\Project\Shows")
path_lbl.setObjectName("pathDisplay")  # Applies monospace inset styling
path_row.addWidget(path_lbl)
layout.addLayout(path_row)

# 2. Tab Bar System
tabs = QTabWidget()
tab1 = QWidget()
tab1_layout = QVBoxLayout(tab1)

# 3. GroupBox Fieldset
group = QGroupBox("Sensory Load Weights")
form = QFormLayout(group)
form.addRow("Pacing:", QLineEdit("25.0 %"))
form.addRow("Preset:", QComboBox())
tab1_layout.addWidget(group)

# 4. Buttons (Standard Gray vs. Aqua Blue)
btn_row = QHBoxLayout()
btn_row.addStretch()

btn_standard = QPushButton("Back")
btn_aqua = QPushButton("Create Pipeline")
btn_aqua.setProperty("aqua", True)  # Triggers the blue Aqua gradient!

btn_row.addWidget(btn_standard)
btn_row.addWidget(btn_aqua)
tab1_layout.addLayout(btn_row)

tabs.addTab(tab1, "Pipeline")
tabs.addTab(QWidget(), "Library")
tabs.addTab(QWidget(), "Settings")

layout.addWidget(tabs)

# 5. Status Bar
window.setCentralWidget(central)
window.statusBar().showMessage("Status: Ready")

window.show()
sys.exit(app.exec())