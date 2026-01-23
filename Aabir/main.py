import sys
from functools import partial

from QtCore import *

from styles import Color
from CircuitView import CircuitView
from Items import CompItem



class AppWindow(QMainWindow):
	def __init__(self):
		super().__init__()

		self.setWindowTitle("Not LogiSim")

		central = QWidget()
		self.setCentralWidget(central)
		layout_main = QHBoxLayout(central)
		
		
		###======= CIRCUIT VIEW =======###
		self.view = CircuitView()


		###======= SIDEBAR DRAG-N-DROP MENU =======###
		self.dragbar = QVBoxLayout()
		self.dragbar.setSpacing(10)
		gatelists = {
			"AND": CompItem,
			"OR": CompItem,
			"NOT": CompItem,
			"IN": CompItem,
			"BULB": CompItem,
		}
		for text, item in gatelists.items():
			btn = QPushButton(text)
			btn.setMinimumHeight(50)
			btn.clicked.connect(partial(self.view.scene.addComp, 0, 0, item))
			self.dragbar.addWidget(btn)
		self.dragbar.addStretch()
		
		layout_main.addLayout(self.dragbar)
		layout_main.addWidget(self.view)



if __name__ == "__main__":
	app = QApplication(sys.argv)

	###======= APP COLOR PALETTE =======###
	app.setStyle("Fusion")
	dark_palette = QPalette()
	Role = QPalette.ColorRole

	palette_colors = {
		Role.Window         : Color.secondary_bg,
		Role.WindowText     : Color.text,
		Role.Base           : Color.primary_bg,
		Role.AlternateBase  : Color.secondary_bg,
		Role.ToolTipBase    : Color.tooltip_bg,
		Role.ToolTipText    : Color.tooltip_text,
		Role.Text           : Color.text,
		Role.Button         : Color.button,
		Role.ButtonText     : Color.text,
		Role.Highlight      : Color.hl_text_bg,
		Role.HighlightedText: Color.text,
	}
	for role, color in palette_colors.items():
		dark_palette.setColor(QPalette.ColorGroup.All, role, color)
	app.setPalette(dark_palette)


	###======= APP WINDOW =======###
	window = AppWindow()
	window.resize(1000, 600)
	window.show()

	window.view.scene.addComp(100, 100, CompItem)

	sys.exit(app.exec())