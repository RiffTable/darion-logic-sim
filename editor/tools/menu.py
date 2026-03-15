from typing import cast
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
        self.addAction(Actions.get("save_as"))
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
        self.addAction(Actions.get("delete"))
        self.addSeparator()
        self.addAction(Actions.get("select_none"))
        self.addAction(Actions.get("select_all"))


class ViewMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("View", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("zoom_in"))
        self.addAction(Actions.get("zoom_out"))


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
        self.addAction(Actions.get("invert_scroll"))
        self.addAction(Actions.get("disable_peeking"))
        self.addAction(Actions.get("hide_grid"))
        self.addAction(Actions.get("dark_theme"))