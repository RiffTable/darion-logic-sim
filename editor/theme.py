from core.QtCore import *
from editor.styles import LightTheme, DarkTheme

class ThemeSignals(QObject):
    changed = Signal()

_signals = ThemeSignals()

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
    if is_dark() == dark:
        return
    _current_theme = DarkTheme if dark else LightTheme
    _settings.setValue("dark_theme", dark)
    _signals.changed.emit()

def is_dark():
    return get_theme() is DarkTheme

def apply_palette(app: QApplication):
    colors = get_theme()
    palette = QPalette()
    Role = QPalette.ColorRole
    
    palette_colors = {
        Role.Window: colors.secondary_bg,
        Role.WindowText: colors.text,
        Role.Base: colors.primary_bg,
        Role.AlternateBase: colors.secondary_bg,
        Role.ToolTipBase: colors.tooltip_bg,
        Role.ToolTipText: colors.tooltip_text,
        Role.Text: colors.text,
        Role.Button: colors.button,
        Role.ButtonText: colors.text,
        Role.Highlight: colors.hl_text_bg,
        Role.HighlightedText: colors.text,
    }
    
    for role, color in palette_colors.items():
        palette.setColor(QPalette.ColorGroup.All, role, color)
    
    app.setPalette(palette)

theme_changed = _signals.changed