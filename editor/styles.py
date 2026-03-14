from PySide6.QtGui import QColor, QFont

class LightTheme:
    text           = QColor("#1f2c39")
    hl_text_bg     = QColor("#3677e0")
    primary_bg     = QColor("#cfd5db")
    secondary_bg   = QColor("#e1e6ec")
    tooltip_text   = QColor("#f8fafc")
    tooltip_bg     = QColor("#263542")
    button         = QColor("#bcc3cb")
    
    comp_active    = QColor("#2fc51b")
    comp_body      = QColor("#d2d9e0")

    signal_high    = QColor("#229513")
    signal_low     = QColor("#5f6468")
    signal_error   = QColor("#dd2929")
    signal_unknown = QColor("#609ac9")

    pin_high       = QColor("#1fa110")
    pin_low        = QColor("#c5591b")
    pin_hover      = QColor("#45676b")

    LED_on         = QColor("#f1c40f")
    LED_off        = QColor("#d2d9e0")
    
    outline        = QColor("#6f7d8c")
    sidebar_toggle = QColor("#bac1ca")


class DarkTheme:
    text           = QColor("#d8dee6")
    hl_text_bg     = QColor("#2f65ca")
    primary_bg     = QColor("#03070c")
    secondary_bg   = QColor("#121c26")
    tooltip_text   = QColor("#ff0000")
    tooltip_bg     = QColor("#ffffff")
    button         = QColor("#1e2a36")

    comp_active    = QColor("#31ce1c")
    comp_body      = QColor("#17222d")

    signal_high    = QColor("#229513")
    signal_low     = QColor("#5f6468")
    signal_error   = QColor("#dd2929")
    signal_unknown = QColor("#609ac9")

    pin_high       = QColor("#229513")
    pin_low        = QColor("#c5591b")
    pin_hover      = QColor("#6b8c9c")

    LED_on         = QColor("#f1c40f")
    LED_off        = QColor("#17222d")
    
    outline        = QColor("#314152")
    sidebar_toggle = QColor("#07101f")


class Font:
    default        = QFont("Segoe UI", 12, QFont.Weight.Bold)