from core.QtCore import *
import editor.actions as Action

class BaseMenu(QMenu):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)

    def _add_checkable_action(self, text: str, shortcut=None, checked=False, slot=None):
        """Helper method to add a checkable action to the menu"""
        action = QAction(text, self.parent())
        action.setCheckable(True)
        action.setChecked(checked)
        if shortcut:
            if isinstance(shortcut, QKeySequence.StandardKey):
                action.setShortcut(shortcut)
            else:
                action.setShortcut(QKeySequence(shortcut))
        if slot:
            action.toggled.connect(slot)
        self.addAction(action)
        return action


class FileMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("File", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Action.get("new"))
        self.addAction(Action.get("open"))
        self.addSeparator()
        self.addAction(Action.get("save"))
        self.addAction(Action.get("save_as"))
        self.addSeparator()
        self.addAction(Action.get("exit"))


class EditMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Edit", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Action.get("undo"))
        self.addAction(Action.get("redo"))
        self.addSeparator()
        self.addAction(Action.get("cut"))
        self.addAction(Action.get("copy"))
        self.addAction(Action.get("paste"))


class ProjectMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Project", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction("Export as Image")


class SettingsMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Settings", parent)
        self.setup_menu()

    def setup_menu(self):
        self._add_checkable_action("Invert Mouse Scrolling")
        self._add_checkable_action("Disable Pins Peeking")
        self._add_checkable_action("Hide Grid")

        # Theme toggle
        self.theme_manager = self.parent().theme_manager if self.parent() else None
        
        initial_checked = self.theme_manager.current_theme == "dark" if self.theme_manager else True
        self.dark_theme_action = self._add_checkable_action(
            "Dark Theme", 
            checked=initial_checked
        )
        
        if self.theme_manager:
            self.dark_theme_action.triggered.connect(self.toggle_theme)
            self.theme_manager.theme_changed.connect(self.on_theme_changed)
    
    def toggle_theme(self, checked):
        if self.theme_manager:
            self.theme_manager.apply_theme("dark" if checked else "light")
    
    def on_theme_changed(self, theme_name):
        self.dark_theme_action.setChecked(theme_name == "dark")