from PySide6.QtGui import QColor, QFont

class Color:
	primary_bg     = QColor("#1e1e1e")
	secondary_bg   = QColor("#2b2b2b")
	text           = QColor("#ffffff")
	hl_text_bg     = QColor("#2f65ca")
	button         = QColor("#3c3f41")
	tooltip_bg     = QColor("#ffffff")
	tooltip_text   = QColor("#ff0000")
	gate_off       = QColor("#47494b")
	gate_on        = QColor("#2ecc71")
	LED_on         = QColor("#f1c40f")
	LED_off        = QColor("#e74c3c")
	outline        = QColor("#000000")

class Font:
	default        = QFont("Arial", 12, QFont.Weight.Bold)