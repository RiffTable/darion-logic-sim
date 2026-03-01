import sys
import json
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
		self.cscene = self.view.cscene
		self.projectFile: str|None = None

		###======= PROPERTIES PANEL =======###
		self.props_panel = PropertiesPanel()
		self.cscene.selectionChanged.connect(
			lambda: self.props_panel.selectionChanged(self.cscene.selectedItems())
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
			"INPUT": 11,
			"LED": 21,
		}

		for text, comp_id in gatelists.items():
			btn = QPushButton(text)
			btn.setMinimumHeight(50)
			btn.clicked.connect(partial(self.cscene.addComp, 0, 0, comp_id))
			# btn.clicked.connect(lambda: self.scene().addComp(0, 0, comp_id))
			self.dragbar.addWidget(btn)
		self.dragbar.addStretch()
		
		layout_main.addLayout(self.dragbar)
		layout_main.addWidget(self.view)
		layout_main.addWidget(self.props_panel)

		self.setupQActions()



	###======= ACTIONS =======###
	def setupQActions(self):
		self.save_action = QAction("Save Project", self)
		self.save_action.setShortcut(QKeySequence.StandardKey.Save)
		self.save_action.triggered.connect(self.saveProject)
		self.addAction(self.save_action)

		self.open_action = QAction("Open Project", self)
		self.open_action.setShortcut(QKeySequence.StandardKey.Open)
		self.open_action.triggered.connect(self.loadProject)
		self.addAction(self.open_action)
	
	def saveProject(self):
		filename, _ = QFileDialog.getSaveFileName(
			self,
			"Save Project",
			"exports/project",
			"JSON Files (*.json);;All Files (*)"
		)
		if not filename: return

		t = self.view.transform()
		project = self.cscene.serialize() | {
			"camera": (t.dx(), t.dy()),
			"zoom":   t.m11()
		}

		# Saving to file
		try:
			with open(filename, 'w') as file:
				json.dump(project, file)
		except Exception as e:
			print("Failed to save:", e)
	
	def loadProject(self):
		# with open(location, 'rb') as file:
		# 	circuit = json.loads(file.read())
	
		filename, _ = QFileDialog.getOpenFileName(
			self,
			"Open Project",
			"exports/project",
			"JSON Files (*.json);;All Files (*)"
		)
		if not filename: return

		try:
			with open(filename, 'r') as file:
				project = json.load(file)

			dx, dy = project.pop("camera", (0, 0))
			m11 = project.pop("zoom", 1.0)

			self.cscene.clearCanvas()
			self.cscene.deserialize(project)

			self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
			self.view.setTransform(QTransform(m11, 0, 0, m11, dx, dy))
			self.view.viewScale = m11
			self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

		except Exception as e:
			print("Failed to load:", e)



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

	window.cscene.addComp(100, 100, 5)
	window.cscene.addComp(100, 200, 11)

	sys.exit(app.exec())