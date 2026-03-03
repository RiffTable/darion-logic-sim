from PySide6.QtGui import QColor, QFont

class LightColors:
    text           = QColor("#2f3b44")
    hl_text_bg     = QColor("#36b9e0")
    primary_bg     = QColor("#c1c1b8")
    secondary_bg   = QColor("#d6d6cd")
    tooltip_text   = QColor("#f5f5ed")
    tooltip_bg     = QColor("#4a4f4a")
    button         = QColor("#b2b2a8")
    
    comp_active    = QColor("#3fd226")
    comp_body      = QColor("#c8c8bf")

    signal_high    = QColor("#2abc20")
    signal_low     = QColor("#979e94")
    signal_error   = QColor("#bf6b6b")
    signal_unknown = QColor("#7f9fbf")

    pin_high       = QColor("#6f8c6a")
    pin_low        = QColor("#bf8f4a")
    pin_hover      = QColor("#6b8c9c")

    LED_on         = QColor("#ef911f")
    LED_off        = QColor("#c8c8bf")
    
    outline        = QColor("#6f6f66")

class DarkColors:
	text           = QColor("#ffffff")
	hl_text_bg     = QColor("#2f65ca")
	primary_bg     = QColor("#1e1e1e")
	secondary_bg   = QColor("#2b2b2b")
	tooltip_text   = QColor("#ff0000")
	tooltip_bg     = QColor("#ffffff")
	button         = QColor("#3c3f41")

	comp_active    = QColor("#2fc51b")
	comp_body      = QColor("#47494b")

	signal_high    = QColor("#229513")
	signal_low     = QColor("#5f6468")
	signal_error   = QColor("#dd2929")
	signal_unknown = QColor("#609ac9")

	pin_high       = QColor("#2fc51b")
	pin_low        = QColor("#c5591b")
	pin_hover      = QColor("#cccccc")

	LED_on         = QColor("#f1c40f")
	LED_off        = QColor("#47494b")

	outline        = QColor("#000000")

class Font:
	default        = QFont("Segoe UI", 12, QFont.Weight.Bold)