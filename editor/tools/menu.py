from core.QtCore import *
import editor.actions as Actions
import editor.theme as theme

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


class ViewMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("View", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("select-all"))
        self.addAction(Actions.get("delete"))
        self.addAction(Actions.get("zoom-in"))
        self.addAction(Actions.get("zoom-out"))


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
        initial_checked = theme.is_dark()
        
        main_window = self.parent()
        
        Actions.addCheckable(self, "invert-scroll", "Invert Mouse Scrolling",
                           self.is_scroll_inverted(), 
                           lambda checked: main_window.setScrollInverted(checked))
        Actions.addCheckable(self, "disable-peeking", "Disable Pins Peeking")
        Actions.addCheckable(self, "hide-grid", "Hide Grid")
        Actions.addCheckable(self, "dark-theme", "Dark Theme", initial_checked, self.toggle_theme)

    def is_scroll_inverted(self):
        settings = QSettings()
        return settings.value("settings/invert_scroll", False, type=bool)

    def toggle_theme(self, checked):
        theme.set_theme(checked)  