from core.QtCore import *


class CategorySection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.toggle = QPushButton(title)
        self.toggle.setCheckable(True)
        
        self.content = QFrame()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 5, 0, 10)
        self.content_layout.setSpacing(0)
        self.content.setVisible(False)
        
        self.buttons = []
        self.layout.addWidget(self.toggle)
        self.layout.addWidget(self.content)
        self.toggle.toggled.connect(self.content.setVisible)
        
        self.toggle.setStyleSheet(self.get_toggle_style())
        self.content.setStyleSheet(self.get_content_style())

    # Stylesheet functions
    def get_toggle_style(self):
        return f"""
            QPushButton {{
                background-color: #1a1d23;
                color: #d1d5db;
                text-align: left;
                padding: 15px;
                border: none;
                border-bottom: 1px solid #3d444d;
                font-family: 'Segoe UI', 'Monaco', monospace;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
            }}
            QPushButton:hover {{ 
                background-color: #24292f; 
            }}
            QPushButton:checked {{
                border-bottom: none; 
                color: #ffffff;
            }}"""

    def get_content_style(self):
        return f"""
            background-color: #0d1117; 
            border: none;
        """

    def get_button_style(self):
        return f"""
            QPushButton {{
                color: #8b949e;
                padding: 8px 30px;
                text-align: left;
                border: none;
                font-size: 12px;
                font-family: 'Segoe UI', 'Monaco', monospace;
            }}
            QPushButton:hover {{ 
                color: white; 
                background-color: #161b22; 
            }}"""

    def add_item(self, text, comp_id):
        btn = QPushButton(text)
        btn.setProperty("comp_id", comp_id)
        btn.setStyleSheet(self.get_button_style())
        self.content_layout.addWidget(btn)
        self.buttons.append(btn)
        return btn

    def filter(self, text):
        if not text:
            for btn in self.buttons:
                btn.show()
            return len(self.buttons)
        
        visible = 0
        for btn in self.buttons:
            if text.lower() in btn.text().lower():
                btn.show()
                visible += 1
            else:
                btn.hide()
        return visible


class ComponentSidebar(QWidget):
    componentSpawnRequested = Signal(int)

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setFixedWidth(200)
        self.sections = []
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self.apply_filter)
        
        self.setup_ui()

        self.setStyleSheet(self.get_main_style())
        self.search.setStyleSheet(self.get_search_style())
        self.scroll.setStyleSheet(self.get_scroll_style())

    # Stylesheet functions
    def get_main_style(self):
        return f"""
            ComponentSidebar {{
                background-color: #1a1d23;
                border-right: 1px solid #3d444d;
            }}"""

    def get_search_style(self):
        return f"""
            QLineEdit {{
                background-color: #0d1117;
                border: 1px solid #3d444d;
                border-radius: 4px;
                color: white;
                padding: 8px;
                margin: 15px;
                font-family: 'Segoe UI', 'Monaco', monospace;
            }}
            QLineEdit:focus {{ 
                border: 1px solid #58a6ff; 
            }}
            QLineEdit QPushButton {{
                color: #8b949e;
                border: none;
                background: none;
                font-weight: bold;
                padding-right: 5px;
            }}
            QLineEdit QPushButton:hover {{
                color: white; 
            }}"""

    def get_scroll_style(self):
        return f"""
            QScrollArea {{ 
                border: none; 
                background-color: transparent;
            }}"""

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search components...")
        
        clear = QAction("✕", self)
        self.search.addAction(clear, QLineEdit.TrailingPosition)
        clear.triggered.connect(self.clear_search)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        layout.addWidget(self.search)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        container = QWidget()
        self.menu = QVBoxLayout(container)
        self.menu.setContentsMargins(0, 0, 0, 0)
        self.menu.setSpacing(0)
        self.menu.setAlignment(Qt.AlignTop)

        categories = [
            ("Gates", [("NOT",0), ("AND",1), ("NAND",2), ("OR",3), ("NOR",4), ("XOR",5), ("XNOR",6)]),
            ("I/O", [("Input", 11), ("LED", 21)]),
            ("Misc",[]),
            ("IC",[])
        ]

        for title, items in categories:
            section = CategorySection(title)
            for name, cid in items:
                btn = section.add_item(name, cid)
                btn.clicked.connect(lambda _, c=cid: self.componentSpawnRequested.emit(c))
            self.menu.addWidget(section)
            self.sections.append(section)

        self.scroll.setWidget(container)
        layout.addWidget(self.scroll)

    def apply_filter(self):
        text = self.search.text().strip()
        
        if not text:
            for section in self.sections:
                section.setVisible(True)
                for btn in section.buttons:
                    btn.show()
                section.content.setVisible(False)
                section.toggle.setChecked(False)
            return
        
        for section in self.sections:
            visible = section.filter(text)
            section.setVisible(visible > 0)
            if visible > 0:
                section.content.setVisible(True)
                section.toggle.setChecked(True)

    def clear_search(self):
        self.search.clear()
        self.apply_filter()