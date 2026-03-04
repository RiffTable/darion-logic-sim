from core.QtCore import *
import editor.actions as Actions

class BaseMenu(QMenu):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)



class FileMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("File", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("new"))
        self.addAction(Actions.get("open"))
        self.addSeparator()
        self.addAction(Actions.get("save"))
        self.addAction(Actions.get("save-as"))
        self.addSeparator()
        self.addAction(Actions.get("exit"))


class EditMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Edit", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("undo"))
        self.addAction(Actions.get("redo"))
        self.addSeparator()
        self.addAction(Actions.get("cut"))
        self.addAction(Actions.get("copy"))
        self.addAction(Actions.get("paste"))


class ProjectMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Project", parent)
        self.setup_menu()

    def setup_menu(self):
        ...
        # self.addAction("Export as Image")


class SettingsMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Settings", parent)
        self.setup_menu()

    def setup_menu(self):
        # Theme toggle
        self.theme_manager = self.parent().theme_manager if self.parent() else None  # type: ignore
        initial_checked = self.theme_manager.current_theme == "dark" if self.theme_manager else True
        
        Actions.addCheckable(self, "invert-scroll", "Invert Mouse Scrolling")
        Actions.addCheckable(self, "disable-peeking", "Disable Pins Peeking")
        Actions.addCheckable(self, "hide-grid", "Hide Grid")
        Actions.addCheckable(self, "dark-theme", "Dark Theme", initial_checked, self.toggle_theme)

        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self.on_theme_changed)
    
    def toggle_theme(self, checked):
        if self.theme_manager:
            self.theme_manager.apply_theme("dark" if checked else "light")
    
    def on_theme_changed(self, theme_name):
        Actions.get("dark-theme").setChecked(theme_name == "dark")