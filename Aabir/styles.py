from PySide6.QtGui import QColor, QFont

class Color:
	text           = QColor("#ffffff")
	hl_text_bg     = QColor("#2f65ca")
	primary_bg     = QColor("#1e1e1e")
	secondary_bg   = QColor("#2b2b2b")
	tooltip_text   = QColor("#ff0000")
	tooltip_bg     = QColor("#ffffff")
	button         = QColor("#3c3f41")
	gate           = QColor("#47494b")
	signal_on      = QColor("#37D431")
	signal_off     = QColor("#3c3f41")
	pin_on         = QColor("#37D431")
	pin_off        = QColor("#656a6d")
	pin_hover      = QColor("#cccccc")
	LED_on         = QColor("#f1c40f")
	LED_off        = QColor("#e74c3c")

	outline        = QColor("#000000")

class Font:
	default        = QFont("Arial", 8, QFont.Weight.Bold)