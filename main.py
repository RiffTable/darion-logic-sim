import sys
from functools import partial

from core.QtCore import *
from core.LogicCore import *

from editor.styles import Color
from editor.circuit.viewport import CircuitView
from editor.tools.properties import PropertiesPanel




class AppWindow(QMainWindow):
	def __init__(self):
		super().__init__()

		self.setWindowTitle("Not LogiSim")

		central = QWidget()
		self.setCentralWidget(central)
		layout_main = QHBoxLayout(central)
		

		###======= CIRCUIT =======###
		self.view = CircuitView()
		self.scene = self.view.scene()

		###======= PROPERTIES PANEL =======###
		self.props_panel = PropertiesPanel()
		self.scene.selectionChanged.connect(
			lambda: self.props_panel.selectionChanged(self.scene.selectedItems())
		)


		###======= SIDEBAR DRAG-N-DROP MENU =======###
		self.dragbar = QVBoxLayout()
		self.dragbar.setSpacing(10)
		gatelists = {
			"NOT Gate": 0,
			"AND Gate": 1,
			"NAND Gate": 2,
			"OR Gate": 3,
			"NOR Gate": 4,
			"XOR Gate": 5,
			"XNOR Gate": 6,
			# "Input (Toggle)": 7,
			# "LED": 8,
		}

		for text, comp_id in gatelists.items():
			btn = QPushButton(text)
			btn.setMinimumHeight(50)
			btn.clicked.connect(partial(self.scene.addComp, 0, 0, comp_id))
			# btn.clicked.connect(lambda: self.scene().addComp(0, 0, comp_id))
			self.dragbar.addWidget(btn)
		self.dragbar.addStretch()
		
		layout_main.addLayout(self.dragbar)
		layout_main.addWidget(self.view)
		layout_main.addWidget(self.props_panel) 



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

	window.scene.addComp(100, 100, 5)
	# window.scene.addComp(100, 200, 7)

	sys.exit(app.exec())