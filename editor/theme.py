from core.QtCore import *
from editor.styles import LightTheme, DarkTheme


_settings = QSettings("Darion", "Darion Logic Sim")
_current_theme = None

def get_theme():
    global _current_theme
    if _current_theme is None:
        dark = _settings.value("dark_theme", True, type=bool)
        _current_theme = DarkTheme if dark else LightTheme
    return _current_theme

def set_theme(dark: bool):
    global _current_theme
    _current_theme = DarkTheme if dark else LightTheme
    _settings.setValue("dark_theme", dark)

def is_dark():
    return get_theme() is DarkTheme

def load_saved_theme():
    dark = _settings.value("dark_theme", True, type=bool)
    set_theme(dark)
    return get_theme()


class ThemeManager(QObject):
    theme_changed = Signal()
    
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.apply_palette()
    
    def apply_palette(self):
        colors = get_theme()
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
    
    def load_saved_theme(self):
        load_saved_theme()
        self.apply_palette()
        self.theme_changed.emit()
    
    def toggle_theme(self):
        set_theme(not is_dark())
        self.apply_palette()
        self.theme_changed.emit()