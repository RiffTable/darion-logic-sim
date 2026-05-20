from __future__ import annotations
from typing import cast, Callable, Any
from core.QtCore import *
from core.LogicCore import *
from editor.styles import Val
import editor.theme as theme
from editor.circuit.catalog import LOOKUP, CATEGORIES
from editor.circuit.canvas import CircuitScene



class CategorySection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 0, 5, 0)
        self.main_layout.setSpacing(0)

        # Category Title
        self.toggle = QPushButton(title)
        self.toggle.setCheckable(True)
        
        # Category Contents List
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



    ### Items List
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

    ### Stylesheet and Themes
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

BTN_SIZE = 28

class DockTitleBar(QWidget):
    def __init__(self, sidebar: ComponentSidebar, parent=None):
        super().__init__(parent)
        self.sidebar = sidebar
        self.setMinimumHeight(BTN_SIZE)
        self.button_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.button_layout.setContentsMargins(8, 4, 4, 4)
        self.button_layout.setSpacing(0)

        # Hamburger Menu
        self.menu_btn = QPushButton("☰")
        self.menu_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.menu_btn.setToolTip("Menu")
        self.menu_btn.clicked.connect(self.open_menu)

        # Undo Button
        undo_stack = self.sidebar.cscene.undo_stack
        self.undo_btn = QPushButton("←")
        self.undo_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.undo_btn.setToolTip("Undo")
        self.undo_btn.clicked.connect(undo_stack.undo)
        undo_stack.canUndoChanged.connect(self.undo_btn.setEnabled)
        self.undo_btn.setEnabled(undo_stack.canUndo())

        # Redo Button
        self.redo_btn = QPushButton("→")
        self.redo_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.redo_btn.setToolTip("Redo")
        self.redo_btn.clicked.connect(undo_stack.redo)
        undo_stack.canRedoChanged.connect(self.redo_btn.setEnabled)
        self.redo_btn.setEnabled(undo_stack.canRedo())

        # Collapse/Expand Button
        self.collapse_btn = QPushButton("⊟")
        self.collapse_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.collapse_btn.setToolTip("Collapse")
        self.collapse_btn.clicked.connect(self.sidebar.toggle_collapse)

        theme.theme_changed.connect(self.apply_theme)
        self.apply_theme()
        self.sidebar.dockLocationChanged.connect(self.refresh_layout)
        # self.refresh_layout()

    def apply_theme(self):
        colors = theme.get_theme()
        button_style = f"""
            QPushButton {{
                background-color: {colors.secondary_bg.name()};
                color: {colors.text.name()};
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-family: 'JetBrains Mono', 'Monaco', monospace;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: {colors.button.name()};
                color: {colors.tooltip_bg.name()};
            }}
            QPushButton:disabled {{
                background-color: {colors.secondary_bg.name()};
                color: {colors.text_inactive.name()};
            }}
        """
        self.menu_btn.setStyleSheet(button_style)
        self.undo_btn.setStyleSheet(button_style)
        self.redo_btn.setStyleSheet(button_style)
        self.collapse_btn.setStyleSheet(button_style)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.secondary_bg.name()};
                color: {colors.text.name()};
                border-bottom: 1px solid #3d444d;
            }}
        """)

    def refresh_layout(self, dock_area: Qt.DockWidgetArea | None = None):
        parent = cast(QMainWindow, self.sidebar.parent())
        lay = self.button_layout

        # Find whether the sidebar is docked to Left or Right
        if parent is None:
            dock_area = None
        elif dock_area is None:
            dock_area = parent.dockWidgetArea(self.sidebar)

        # Clears all buttons
        while lay.count():
            item = lay.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Collapse/Expand
        if self.sidebar._collapsed:
            self.collapse_btn.setText("⊞")
            self.collapse_btn.setToolTip("Expand")
            lay.setDirection(QBoxLayout.Direction.TopToBottom)
        else:
            self.collapse_btn.setText("⊟")
            self.collapse_btn.setToolTip("Collapse")
            lay.setDirection(QBoxLayout.Direction.LeftToRight)
        
        # Ordering the buttons
        if dock_area == Qt.DockWidgetArea.RightDockWidgetArea and not self.sidebar._collapsed:
            lay.addWidget(self.collapse_btn)
            lay.addWidget(self.undo_btn)
            lay.addWidget(self.redo_btn)
            lay.addWidget(self.menu_btn)
        else:
            lay.addWidget(self.menu_btn)
            lay.addWidget(self.undo_btn)
            lay.addWidget(self.redo_btn)
            lay.addWidget(self.collapse_btn)

    def open_menu(self):
        parent = cast(QMainWindow, self.sidebar.parent())
        if parent is None: return

        DockArea = Qt.DockWidgetArea
        current_area = parent.dockWidgetArea(self.sidebar)
        menu = QMenu(self)

        def dock_left():
            parent.addDockWidget(DockArea.LeftDockWidgetArea, self.sidebar)

        def dock_right():
            parent.addDockWidget(DockArea.RightDockWidgetArea, self.sidebar)
        
        if current_area != DockArea.RightDockWidgetArea:
            action = menu.addAction("Dock to Right")
            action.triggered.connect(dock_right)
        if current_area != DockArea.LeftDockWidgetArea:
            action = menu.addAction("Dock to Left")
            action.triggered.connect(dock_left)

        #? Lackluster. Menu not streamable
        menu.exec(self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height())))



class ComponentSidebar(QDockWidget):
    refresh_IC_catagory = Signal()
    def __init__(self, theme_manager, parent, canvas: CircuitScene):
        super().__init__("Sidebar", parent)

        if parent:
            self.spawnComponent   = cast(Callable[[int], None], parent.spawnComponent)
            self.spawnIC          = cast(Callable[[Any], None], parent.spawnIC)
            self.retrieve_IC_data = cast(Callable[[], tuple[dict, dict]], parent.retrieve_IC_data)
        
        self.cscene = canvas

        # Configure dock widget
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setFloating(False)
        
        self.min_width = 200
        self.max_width = 800

        # Create custom title bar
        self.title_bar = DockTitleBar(self)
        self.setTitleBarWidget(self.title_bar)

        self.theme_manager = theme_manager
        self.sections: list[CategorySection] = []
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self.apply_filter)
        
        # Refresh IC list when project folder or IC list changes
        self.refresh_IC_catagory.connect(self.build_IC_category)
        self.ic_section = None
        
        # Create internal widget to hold all UI
        self.widget_container = QWidget()
        self.setWidget(self.widget_container)
        
        self.setup_ui()
        self._collapsed = False

        theme.theme_changed.connect(self.apply_theme)
        self.apply_theme()

    # Stylesheet functions
    def apply_theme(self):
        colors = theme.get_theme()
        
        self.search.setStyleSheet(self.get_search_style(colors))
        self.scroll_area.setStyleSheet(self.get_scroll_style())
        self.title_bar.apply_theme()

    def get_search_style(self, colors):
        return f"""
            QLineEdit {{
                background-color: {colors.primary_bg.name()};
                border: 1px solid #3d444d;
                border-radius: 4px;
                color: {colors.tooltip_bg.name()};
                padding: 8px;
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
        layout = QVBoxLayout(self.widget_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        ### Search Box
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 0, 5, 5)
        search_layout.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search components...")
        
        #! This button is invisible for some reason
        clear = QAction("🅧", self)
        self.search.addAction(clear, QLineEdit.ActionPosition.TrailingPosition)
        clear.triggered.connect(self.clear_search)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        
        search_layout.addWidget(self.search)
        layout.addLayout(search_layout)

        ### Categories
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.focusNextPrevChild = (lambda next: False)  # Disable horizontal scroll movement
        
        container = QWidget()
        self.menu = QVBoxLayout(container)
        self.menu.setContentsMargins(0, 0, 0, 0)
        self.menu.setSpacing(0)
        self.menu.setAlignment(Qt.AlignmentFlag.AlignTop)

        ## Creating all catagories
        for title, items in CATEGORIES.items():
            section = CategorySection(title)
            for comp_id in items:
                btn = section.add_item(LOOKUP[comp_id].NAME)
                btn.clicked.connect(lambda _, c=comp_id: self.spawnComponent(c))
            self.menu.addWidget(section)
            self.sections.append(section)

            # Expand category for "Gates" and "I/O"
            if title.lower() in ["gates", "i/o"]:
                section.toggle.setChecked(True)
        
        ## IC Catagory
        self.build_IC_category()

        ## Finishing
        self.scroll_area.setWidget(container)
        layout.addWidget(self.scroll_area)
        
        self.setMinimumWidth(self.min_width)
        self.setMaximumWidth(self.max_width)

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.title_bar.refresh_layout()

        if self._collapsed:
            self.search.hide()
            self.scroll_area.hide()
            self.setFixedWidth(BTN_SIZE)
        else:
            self.search.show()
            self.scroll_area.show()
            self.setMinimumWidth(self.min_width)
            self.setMaximumWidth(self.max_width)

    def apply_filter(self):
        text = self.search.text().strip()
        
        if not text:
            for section in self.sections:
                section.setVisible(True)
                for btn in section.buttons:
                    btn.show()
                section.toggle.setChecked(False)
            return
        
        for section in self.sections:
            visible = section.filter(text)
            section.setVisible(visible > 0)
            if visible > 0:
                section.toggle.setChecked(True)

    def clear_search(self):
        self.search.clear()
        self.apply_filter()
    
    def build_IC_category(self):
        isExpanded = False
        color = theme.get_theme()
        folder = str(QSettings().value(
            "settings/ic_dir",
            str(Val.Paths.ICs),
            type=str
        ))

        ### Remove IC Catagory
        if self.ic_section is not None:
            isExpanded = self.ic_section.toggle.isChecked()
            self.menu.removeWidget(self.ic_section)

            if self.ic_section in self.sections:
                self.sections.remove(self.ic_section)
            
            self.ic_section.setParent(None)
            self.ic_section.deleteLater()

        ### Recreate IC Category
        self.ic_section = CategorySection("IC")
        self.ic_section.add_item("Refresh List").clicked.connect(self.refresh_IC_catagory)

        inproject, infolder = self.retrieve_IC_data()

        ## Reading ICs stored in canvas.iclist
        # Header
        if len(inproject) > 0:
            label1 = QLabel("Used in the Project:")
            label1.setStyleSheet(f"color: {color.text_inactive.name()};")
            self.ic_section.content_layout.addWidget(label1)

        # List ICs
        for name, data in inproject.items():
            btn = self.ic_section.add_item(name)
            btn.clicked.connect(lambda _, d=data: self.spawnIC(d))
        
        
        ## Reading ICs stored in files
        # Header
        if len(infolder) > 0:
            label2 = QLabel("Saved in Folder:")
            label2.setStyleSheet(f"color: {color.text_inactive.name()};")
            label2.setToolTip(folder)
            self.ic_section.content_layout.addWidget(label2)
        
        # List ICs
        for name, location in infolder.items():
            btn = self.ic_section.add_item(name)
            btn.clicked.connect(lambda _, loc=location: self.import_IC(loc))

        # Makes sure the category doesn't randomly expand or collapse
        self.ic_section.toggle.setChecked(isExpanded)
        
        self.menu.addWidget(self.ic_section)
        self.sections.append(self.ic_section)

    # IC stuffs
    def import_IC(self, filename: str):
        ic = logic.get_ic(filename)
        if ic:
            self.spawnIC(ic)