from pathlib import Path
from typing import cast, Callable, Any
from core.QtCore import *
from core.LogicCore import *
import editor.theme as theme
from editor.circuit.catalog import LOOKUP, CATEGORIES
from editor.circuit.canvas import CircuitScene



class CategorySection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.toggle = QPushButton(title)
        self.toggle.setCheckable(True)
        
        self.content = QFrame()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 5, 0, 10)
        self.content_layout.setSpacing(0)
        self.content.setVisible(False)
        
        self.buttons = []
        self.main_layout.addWidget(self.toggle)
        self.main_layout.addWidget(self.content)
        self.toggle.toggled.connect(self.content.setVisible)
        
        theme.theme_changed.connect(self.apply_theme)
        self.apply_theme()

    # Stylesheet functions
    def apply_theme(self):
        colors = theme.get_theme()

        self.toggle.setStyleSheet(self.get_toggle_style(colors))
        self.content.setStyleSheet(self.get_content_style(colors))

        for btn in self.buttons:
            btn.setStyleSheet(self.get_button_style(colors))

    def get_toggle_style(self, colors):
        return f"""
            QPushButton {{
                background-color: {colors.secondary_bg.name()};
                color: {colors.text.name()};
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
                background-color: {colors.button.name()}; 
            }}
            QPushButton:checked {{
                background-color: {colors.sidebar_toggle.name()};
                border-bottom: none; 
                color: {colors.tooltip_bg.name()};
            }}"""

    def get_content_style(self, colors):
        return f"""
            background-color: {colors.primary_bg.name()}; 
            border: none;
        """

    def get_button_style(self, colors):
        return f"""
            QPushButton {{
                color: {colors.text.name()};
                padding: 8px 30px;
                text-align: left;
                border: none;
                font-size: 12px;
                font-family: 'Segoe UI', 'Monaco', monospace;
            }}
            QPushButton:hover {{ 
                color: {colors.tooltip_bg.name()}; 
                background-color: {colors.button.name()}; 
            }}"""

    def add_item(self, text: str):
        colors = theme.get_theme()
        btn = QPushButton(text)
        # btn.setProperty("comp_id", comp_id)
        btn.setStyleSheet(self.get_button_style(colors))
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
    refresh_IC_catagory = Signal()
    def __init__(self, theme_manager, parent, canvas: CircuitScene):
        super().__init__(parent)
        if parent:
            self.spawnComponent = cast(Callable[[int], None], parent.spawnComponent)
            self.spawnIC = cast(Callable[[Any], None], parent.spawnIC)
        self.cscene = canvas

        self.theme_manager = theme_manager
        self.setFixedWidth(200)
        self.sections = []
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self.apply_filter)
        
        # TODO: updateUI to (just IC needs to be refreshed)
        # self.refresh_IC_catagory.connect(self.updateUI)
        
        self.setup_ui()

        theme.theme_changed.connect(self.apply_theme)
        self.apply_theme()

    # Stylesheet functions
    def apply_theme(self):
        colors = theme.get_theme()
        
        self.search.setStyleSheet(self.get_search_style(colors))
        self.scroll_area.setStyleSheet(self.get_scroll_style())

    def get_search_style(self, colors):
        return f"""
            QLineEdit {{
                background-color: {colors.primary_bg.name()};
                border: 1px solid #3d444d;
                border-radius: 4px;
                color: {colors.tooltip_bg.name()};
                padding: 8px;
                margin: 15px;
                font-family: 'Segoe UI', 'Monaco', monospace;
            }}
            QLineEdit:focus {{ 
                border: 1px solid {colors.hl_text_bg.name()}; 
            }}
            QLineEdit QPushButton {{
                color: {colors.text.name()};
                border: none;
                background: none;
                font-weight: bold;
                padding-right: 5px;
            }}
            QLineEdit QPushButton:hover {{
                color: {colors.tooltip_bg.name()}; 
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
        self.search.addAction(clear, QLineEdit.ActionPosition.TrailingPosition)
        clear.triggered.connect(self.clear_search)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        layout.addWidget(self.search)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        container = QWidget()
        self.menu = QVBoxLayout(container)
        self.menu.setContentsMargins(0, 0, 0, 0)
        self.menu.setSpacing(0)
        self.menu.setAlignment(Qt.AlignmentFlag.AlignTop)

        ### Catagories
        for title, items in CATEGORIES.items():
            section = CategorySection(title)
            for comp_id in items:
                btn = section.add_item(LOOKUP[comp_id].NAME)
                btn.clicked.connect(lambda _, c=comp_id: self.spawnComponent(c))
            self.menu.addWidget(section)
            self.sections.append(section)
        
        ### IC Catagory
        ic_list = self.retrieve_IC_files()
        self.ic_section = CategorySection("IC")
        names: set[str] = set()
        self.ic_section.add_item("Refresh List").clicked.connect(self.refresh_IC_catagory)

        # For ICs stored in canvas.iclist
        # TODO: Add a separator or label here
        for stored_ic in self.cscene.iclist:
            name = stored_ic[Const.CUSTOM_NAME]
            names.add(name)

            btn = self.ic_section.add_item(name)
            btn.clicked.connect(lambda _, d=stored_ic: self.spawnIC(d))
        
        # For ICs stored in files
        # TODO: Add a separator or label here
        for name, comp_id in ic_list:
            if name in names: continue    # Excludes IC listed in canvas.iclist

            btn = self.ic_section.add_item(name)
            btn.clicked.connect(lambda _, loc=comp_id: self.import_IC(loc))
        
        self.menu.addWidget(self.ic_section)
        self.sections.append(self.ic_section)

        ### Finishing
        self.scroll_area.setWidget(container)
        layout.addWidget(self.scroll_area)

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
    
    # IC stuffs
    def import_IC(self, filename: str):
        ic = logic.get_ic(filename)
        if ic:
            self.spawnIC(ic)
    
    def retrieve_IC_files(self) -> list[tuple[str, str]]:
        res: list[tuple[str, str]] = []
        for file in Path("exports/IC").glob("*.json"):
            filename = str(file.resolve())    # Absolute path
            ic = logic.get_ic(filename)
            if ic:
                res.append((ic[Const.CUSTOM_NAME], filename))
        
        return res