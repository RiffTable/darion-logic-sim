from PySide6.QtGui import QColor, QFont


class LightTheme:
    text           = QColor("#1f2c39")
    hl_text_bg     = QColor("#3677e0")
    primary_bg     = QColor("#cfd5db")
    secondary_bg   = QColor("#e1e6ec")
    bg_grid        = QColor("#e1e6ec")
    tooltip_text   = QColor("#f8fafc")
    tooltip_bg     = QColor("#263542")
    button         = QColor("#bcc3cb")
    
    comp_active    = QColor("#2fc51b")
    comp_body      = QColor("#d2d9e0")
    
    signal_high    = QColor("#00FF87")   
    signal_low     = QColor("#5f6468")   
    signal_error   = QColor("#FF1E1E")   
    signal_unknown = QColor("#00D4FF")   
    
    pin_high       = QColor("#00FF00")   
    pin_low        = QColor("#FF6B00")   
    pin_hover      = QColor("#45676b")   
    pin_hoverproxy = QColor("#FFDD57")   
    
    LED_on         = QColor("#FFEE00")   
    LED_off        = QColor("#d2d9e0")   # Original
    
    outline        = QColor("#6f7d8c")
    sidebar_toggle = QColor("#bac1ca")


class DarkTheme:
    text           = QColor("#d8dee6")
    hl_text_bg     = QColor("#2f65ca")
    primary_bg     = QColor("#03070c")
    secondary_bg   = QColor("#121c26")
    bg_grid        = QColor("#121c26")
    tooltip_text   = QColor("#ff0000")
    tooltip_bg     = QColor("#ffffff")
    button         = QColor("#1e2a36")
    
    comp_active    = QColor("#31ce1c")
    comp_body      = QColor("#17222d")
    
    signal_high    = QColor("#00FF87")
    signal_low     = QColor("#5f6468")
    signal_error   = QColor("#00D4FF")
    signal_unknown = QColor("#00D4FF")
    
    pin_high       = QColor("#00FF00")
    pin_low        = QColor("#FF6B00")
    pin_hover      = QColor("#6b8c9c")
    pin_hoverproxy = QColor("#ededed")

    LED_on         = QColor("#f1c40f")
    LED_off        = QColor("#17222d")
    
    outline        = QColor("#314152")
    sidebar_toggle = QColor("#07101f")


class Font:
    default        = QFont("Segoe UI", 12, QFont.Weight.Bold)


# List of "magic numbers"
class Val:
    # Animation Speed (in milliseconds)
    AnimSpeedLED = 140
    AnimSpeedPin = 125
    AnimSpeedWire = 125

    AlertUnsaved = True