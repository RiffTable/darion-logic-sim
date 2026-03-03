from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import QObject, Signal, QSettings

from editor.styles import LightColors, DarkColors


class ThemeManager(QObject):
    theme_changed = Signal(str)
    
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.settings = QSettings("NotLogiSim", "Theme")
        self.current_theme = "dark"
        self.colors = DarkColors
        
        
    def apply_palette(self, colors):
        palette = QPalette()
        Role = QPalette.ColorRole
        
        palette_colors = {
            Role.Window         : colors.secondary_bg,
            Role.WindowText     : colors.text,
            Role.Base           : colors.primary_bg,
            Role.AlternateBase  : colors.secondary_bg,
            Role.ToolTipBase    : colors.tooltip_bg,
            Role.ToolTipText    : colors.tooltip_text,
            Role.Text           : colors.text,
            Role.Button         : colors.button,
            Role.ButtonText     : colors.text,
            Role.Highlight      : colors.hl_text_bg,
            Role.HighlightedText: colors.text,
        }
        
        for role, color in palette_colors.items():
            palette.setColor(QPalette.ColorGroup.All, role, color)
        
        self.app.setPalette(palette)
        
    def apply_theme(self, theme_name: str):
        if theme_name == "light":
            self.colors = LightColors
            self.apply_palette(LightColors)
        else:
            self.colors = DarkColors
            self.apply_palette(DarkColors)
        
        self.current_theme = theme_name
        self.settings.setValue("dark_theme", theme_name == "dark")
        self.theme_changed.emit(theme_name)
    
    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(new_theme)
    
    def load_saved_theme(self):
        dark_theme = self.settings.value("dark_theme", True, type=bool)
        theme = "dark" if dark_theme else "light"
        self.apply_theme(theme)