from PySide6.QtGui import QColor, QFont

class Color:
	text           = QColor("#ffffff")
	hl_text_bg     = QColor("#2f65ca")
	primary_bg     = QColor("#1e1e1e")
	secondary_bg   = QColor("#2b2b2b")
	tooltip_text   = QColor("#ff0000")
	tooltip_bg     = QColor("#ffffff")
	button         = QColor("#3c3f41")

	comp_active    = QColor("#2fc51b")
	comp_body      = QColor("#47494b")

	signal_high    = QColor("#2fc51b")
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