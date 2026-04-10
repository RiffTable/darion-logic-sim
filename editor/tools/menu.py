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
        self.addAction(Actions.get("rotate_cw"))
        self.addAction(Actions.get("rotate_ccw"))
        self.addAction(Actions.get("flip_horizontal"))
        self.addAction(Actions.get("flip_vertical"))

        fm = self.addMenu("Set Facing")
        fm.addAction(Actions.get("face_north"))
        fm.addAction(Actions.get("face_east"))
        fm.addAction(Actions.get("face_south"))
        fm.addAction(Actions.get("face_west"))
        
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
        self.addAction(Actions.get("center_view"))
        self.addSeparator()
        self.addMenu(Actions.getMenu("grid_style"))
        self.addAction(Actions.get("dark_theme"))


class ProjectMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Project", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("load-ic"))
        self.addAction(Actions.get("project-to-ic"))
        self.addSeparator()
        self.addAction(Actions.get("truth_table"))
        self.addAction(Actions.get("diagnose"))
        self.addSeparator()
        self.addMenu(Actions.getMenu("simulation_mode"))


class SettingsMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__("Settings", parent)
        self.setup_menu()

    def setup_menu(self):
        self.addAction(Actions.get("invert_scroll"))
        self.addAction(Actions.get("disable_peeking"))