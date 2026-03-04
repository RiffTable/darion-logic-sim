import sys
import json
from functools import partial

from core.QtCore import *
from core.LogicCore import *

from editor.theme import ThemeManager
from editor.styles import LightTheme, DarkTheme
import editor.actions as Actions
from editor.circuit.viewport import CircuitView
from editor.tools.properties import PropertiesPanel
from editor.tools.menu import FileMenu, EditMenu, ProjectMenu, SettingsMenu




class AppWindow(QMainWindow):
	def __init__(self, theme_manager=None):
		super().__init__()
		self.theme_manager = theme_manager
		self.setWindowTitle("Not LogiSim")

		central = QWidget()
		self.setCentralWidget(central)
		layout_main = QHBoxLayout(central)
		

		###======= MENUS =======###
		menubar: QMenuBar = self.menuBar()
		menubar.addMenu(FileMenu(self))
		menubar.addMenu(EditMenu(self))
		menubar.addMenu(ProjectMenu(self))
		menubar.addMenu(SettingsMenu(self))

		###======= CIRCUIT =======###
		self.view = CircuitView()
		self.cscene = self.view.cscene
		self.current_file_path: str|None = None

		###======= PROPERTIES PANEL =======###
		self.props_panel = PropertiesPanel(self)
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

	def closeEvent(self, event):
		# To make sure a runtime error isn't raised when closing the app
		try:
			self.cscene.selectionChanged.disconnect()
		except RuntimeError:
			pass
			
		super().closeEvent(event)



	###======= ACTIONS =======###
	def setupQActions(self):
		SK = StandardKey    # Default platform specific keybinds
		QKS = QKeySequence
		# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeySequence.html


		### Project functions
		Actions.add(self, "new",     "New",     self.newFile,    SK.New)    # Ctrl+N
		Actions.add(self, "save",    "Save",    self.saveFile,   SK.Save)   # Ctrl+S
		Actions.add(self, "open",    "Open",    self.loadFile,   SK.Open)   # Ctrl+O
		Actions.add(self, "save_as", "Save As", self.saveFileAs, SK.SaveAs) # Ctrl+Shift+S
		

		### Viewport functions
		view = self.view
		Actions.add(view, "zoom_in", "Zoom In", view.zoomInOnMouse) \
			.setShortcuts([QKS("Ctrl+="), QKS("Ctrl++")])
		Actions.add(view, "zoom_out", "Zoom Out", view.zoomOutFromMouse) \
			.setShortcuts([QKS("Ctrl+-"), QKS("Ctrl+_")])
		Actions.add(view, "undo", "Undo", view.undo, SK.Undo)   # Ctrl+Z
		Actions.add(view, "redo", "Redo", view.redo) \
			.setShortcuts([QKS("Ctrl+Shift+Z"), QKS("Ctrl+Y")])
		

		### Canvas functions
		scene = self.cscene
		Actions.add(view, "select_all", "Select All", scene.selectAllComps, SK.SelectAll) # Ctrl+A
		Actions.add(view, "copy"      , "Copy",       scene.copyFromSelection, SK.Copy)   # Ctrl+C
		Actions.add(view, "paste"     , "Paste",      scene.pasteComps,     SK.Paste)     # Ctrl+V
		Actions.add(view, "cut"       , "Cut",        scene.cutComps,       SK.Cut)       # Ctrl+X

		Actions.add(view, "delete", "Delete", scene.removeFromSelection)\
			.setShortcuts([QKS("Del"), QKS("Backspace"), QKS("X")])
		Actions.add(view, "rotate_cw", "Rotate Clockwise", scene.rotateSelectionCW, QKS("R"))
		Actions.add(view, "rotate_ccw", "Rotate Counter-clockwise", scene.rotateSelectionCCW, QKS("Shift+R"))
		Actions.add(view, "flip_horizontal", "Flip Horizontal", scene.flipSelectionHorizontal, QKS("F"))
		Actions.add(view, "flip_vertical", "Flip Vertical", scene.flipSelectionVertical, QKS("Shift+F"))
		# Actions.add(self, "increase_input_size", "Increase Input Size", )



	def get_project_data(self) -> dict:
		t = self.view.transform()
		project = self.cscene.serialize() | {
			"camera": (t.dx(), t.dy()),
			"zoom":   t.m11(),
		}
		return project
	
	def load_project_data(self, project: dict):
		dx, dy = project.pop("camera", (0, 0))
		m11 = project.pop("zoom", 1.0)

		self.cscene.clearCanvas()
		self.cscene.deserialize(project)

		self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
		self.view.setTransform(QTransform(m11, 0, 0, m11, dx, dy))
		self.view.viewScale = m11
		self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
	


	def newFile(self):
		self.current_file_path = None

		self.cscene.clearCanvas()

		# Default values
		m11 = 1.0
		dx, dy = 0, 0
		self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
		self.view.setTransform(QTransform(m11, 0, 0, m11, dx, dy))
		self.view.viewScale = m11
		self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
	
	def saveFile(self, create_new_file: bool = False):
		if self.current_file_path and not create_new_file:
			# Don't ask if the project has a save file
			filename = self.current_file_path
		else:
			# Ask for file name
			filename, _ = QFileDialog.getSaveFileName(
				self,
				"Save Project",
				"exports/project",
				"JSON Files (*.json);;All Files (*)"
			)
			if not filename: return
			self.current_file_path = filename

		# Saving to file
		project = self.get_project_data()
		try:
			with open(filename, 'w') as file:
				json.dump(project, file)
		except Exception as e:
			print("Failed to save:", e)
	
	def saveFileAs(self):
		self.saveFile(True)
	
	def loadFile(self):
		# Always ask for file name
		filename, _ = QFileDialog.getOpenFileName(
			self,
			"Open Project",
			"exports/project",
			"JSON Files (*.json);;All Files (*)"
		)
		if not filename: return

		try:
			with open(filename, 'r') as file:
				project:dict = json.load(file)
			
			self.load_project_data(project)
			self.current_file_path = filename

		except Exception as e:
			print("Failed to load:", e)



if __name__ == "__main__":
	app = QApplication(sys.argv)

	###======= APP THEME =======###
	app.setStyle("Fusion")

	theme_manager = ThemeManager(app)
	theme_manager.load_saved_theme()


	###======= APP WINDOW =======###
	window = AppWindow(theme_manager)
	window.resize(1000, 600)
	window.show()

	window.cscene.addComp(100, 100, 5)
	window.cscene.addComp(100, 200, 11)

	sys.exit(app.exec())