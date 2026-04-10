from core.QtCore import *
import editor.theme as theme

class CircuitDialog(QDialog):
    """Base dialog for circuit information display"""
    def __init__(self, parent, title: str, text: str, min_width, min_height):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(min_width, min_height)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont("Segoe UI")
        self.text_edit.setTabStopDistance(40)
        self.text_edit.setPlainText(text)
        
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(self.text_edit)
        layout.addLayout(btn_layout)
        
        self.apply_theme()
        theme.theme_changed.connect(self.apply_theme)
    
    def apply_theme(self):
        colors = theme.get_theme()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.primary_bg.name()};
            }}
            QTextEdit {{
                background-color: {colors.secondary_bg.name()};
                color: {colors.text.name()};
                border: 1px solid {colors.outline.name()};
                font-family: "Courier New", "Monaco", monospace;
                font-size: 10pt;
            }}
            QPushButton {{
                background-color: {colors.button.name()};
                color: {colors.text.name()};
                padding: 5px 15px;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {colors.comp_active.name()};
            }}
        """)
    
    def copy_to_clipboard(self):
        QGuiApplication.clipboard().setText(self.text_edit.toPlainText())
        self.sender().setText("Copied!")
        QTimer.singleShot(1500, lambda: self.sender().setText("Copy to Clipboard"))


class TruthTableDialog(CircuitDialog):
    def __init__(self, parent, truth_table_text: str):
        super().__init__(parent, "Truth Table", truth_table_text, 700, 500)


class DiagnoseDialog(CircuitDialog):
    def __init__(self, parent, diagnose_text: str):
        super().__init__(parent, "Circuit Diagnosis", diagnose_text, 750, 650)