import sys
import json
from pathlib import Path
from typing import cast

from core.Enums import Facing
from core.QtCore import *
from core.LogicCore import *
import PySide6.QtAsyncio as QtAsyncio

import editor.theme as theme
import editor.actions as Actions
from editor.circuit.viewport import CircuitView
from editor.tools.properties import PropertiesPanel
from editor.tools.menu import FileMenu, EditMenu, ViewMenu, ProjectMenu, SettingsMenu
from editor.tools.sidebar import ComponentSidebar
from editor.tools.ICdialog import ICSetupDialog
from editor.circuit.commands import AddCompCommand



class AppWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Darion Logic Sim")
		self.setMinimumSize(800, 500)

		central = QWidget()
		self.setCentralWidget(central)
		layout_main = QHBoxLayout(central)

		theme.theme_changed.connect(self.refresh_theme)


		###======= CIRCUIT =======###
		self.view = CircuitView()
		self.cscene = self.view.cscene
		self.current_file_path: str|None = None

		self.setupQActions()

		###======= MENUS =======###
		menubar: QMenuBar = self.menuBar()
		menubar.addMenu(FileMenu(self))
		menubar.addMenu(EditMenu(self))
		menubar.addMenu(ViewMenu(self))
		menubar.addMenu(ProjectMenu(self))
		menubar.addMenu(SettingsMenu(self))


		###======= PROPERTIES PANEL =======###
		self.props_panel = PropertiesPanel(self)
		self.cscene.selectionChanged.connect(
			lambda: self.props_panel.selectionChanged(self.cscene.selectedItems())
		)
		self.props_panel.setWindowFlags(
			Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
		)


		###======= SIDEBAR DRAG-N-DROP MENU =======###
		self.sidebar = ComponentSidebar(self, self, self.cscene)
		self.load_settings()

		layout_main.addWidget(self.sidebar)
		layout_main.addWidget(self.view)



	def refresh_theme(self):
		theme.apply_palette(cast(QApplication, QApplication.instance()))
		self.cscene.update()

	def update_props_position(self):
		panel_x = self.x() + self.width() - self.props_panel.width() - 15
		panel_y = self.y() + 65
		self.props_panel.move(panel_x, panel_y)
	
	
	###======= IC MANAGEMENT =======###
	def spawnComponent(self, comp_id: int):
		view_center = self.view.viewport().rect().center()
		pos = self.view.mapToScene(view_center)
		cmd = AddCompCommand(self.cscene, pos, comp_id)
		self.cscene.undo_stack.push(cmd)
	
	def spawnIC(self, ic_data):
		center = self.view.viewport().rect().center()
		pos = self.view.mapToScene(center)

		_, newCreated = self.cscene.addIC(*pos.toTuple(), ic_data)
		if newCreated:
			self.sidebar.refresh_IC_catagory.emit()
	
	def retrieve_IC_data(self):
		ic_list: dict[str, tuple[int|None, str|None]] = {}
		names: set[str] = set()
		
		for idx, stored_ic in enumerate(self.cscene.iclist):
			name = stored_ic[Const.CUSTOM_NAME]
			names.add(name)
			ic_list[name] = (idx, None)

		for file in ICPath.glob("*.json"):
			filename = str(file.resolve())    # Absolute path
			ic = logic.get_ic(filename)
			if ic is None: continue

			name = ic[Const.CUSTOM_NAME]
			if name in names: continue    # Excludes IC listed in canvas.iclist
			
			ic_list[name] = (None, filename)
		
		return ic_list
	
	###======= EVENTS =======###
	def moveEvent(self, event):
		super().moveEvent(event)
		self.update_props_position()
	
	def resizeEvent(self, event):
		super().resizeEvent(event)
		QSettings().setValue("main_window/geometry", self.saveGeometry())
		self.update_props_position()

	def closeEvent(self, event):
		# To make sure a runtime error isn't raised when closing the app
		try:
			self.cscene.selectionChanged.disconnect()
		except RuntimeError: pass
		super().closeEvent(event)



	###======= SETTINGS =======###
	def load_settings(self):
		settings = QSettings()
		self.setScrollInverted(bool(settings.value("settings/invert_scroll", False, type=bool)))
		self.setPeekingDisabled(bool(settings.value("settings/disable_peeking", False, type=bool)))
		self.cscene.setGridStyle(str(settings.value("settings/grid_style", "lines", type=str)))
	
	def setScrollInverted(self, inverted: bool):
		self.view.scroll_inverted = inverted
		
	def setPeekingDisabled(self, disabled: bool):
		self.cscene.peeking_disabled = disabled


	###======= ACTIONS =======###
	def setupQActions(self):
		QKS = QKeySequence
		SK = QKeySequence.StandardKey    # Default platform specific keybinds
		# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeySequence.html


		### Project functions
		Actions.add(self, "new",     "New",     self.newFile,    SK.New)    # Ctrl+N
		Actions.add(self, "save",    "Save",    self.saveFile,   SK.Save)   # Ctrl+S
		Actions.add(self, "open",    "Open",    self.loadFile,   SK.Open)   # Ctrl+O
		Actions.add(self, "save_as", "Save As", self.saveFileAs, SK.SaveAs) # Ctrl+Shift+S
		Actions.add(self, "exit",    "Exit",    self.close,      SK.Quit)

		Actions.addSettingsCheckable(self, "invert_scroll", "Invert Scroll", False, self.setScrollInverted)
		Actions.addSettingsCheckable(self, "disable_peeking", "Disable Pins Peeking", False, self.setPeekingDisabled)
		Actions.addSettingsCheckable(self, "dark_theme", "Dark Theme", True, theme.set_theme)
		
		# Adding componenets
		Actions.add(self, "load-ic", "Import IC", self.addICToProject, QKS("Ctrl+I"))
		Actions.add(self, "project-to-ic", "Convert Project to IC", self.convertProjectToIC, QKS("Ctrl+Shift+I"))
		# Actions.add(self, "selection-to-ic", "Convert Selection to IC", )
		

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
		Actions.createSubMenu(
			view, "grid_style", "Grid Style", "lines", scene.setGridStyle,
			{"hidden": "Hidden", "lines": "Grid Lines", "dots": "Dots"}
		)

		Actions.add(view, "select_none", "Select None", scene.selectNone, SK.Deselect) # Ctrl+A
		Actions.add(view, "select_all", "Select All", scene.selectAllComps, SK.SelectAll) # Ctrl+A
		Actions.add(view, "copy"      , "Copy",       scene.copyFromSelection, SK.Copy)   # Ctrl+C
		Actions.add(view, "paste"     , "Paste",      scene.pasteComps,     SK.Paste)     # Ctrl+V
		Actions.add(view, "cut"       , "Cut",        scene.cutComps,       SK.Cut)       # Ctrl+X

		Actions.add(view, "delete", "Delete", scene.removeFromSelection)\
			.setShortcuts([QKS("Del"), QKS("Backspace"), QKS("X")])
		
		# Orientation
		Actions.add(view, "rotate_cw", "Rotate Clockwise", scene.rotateSelectionCW, QKS("R"))
		Actions.add(view, "rotate_ccw", "Rotate Counter-clockwise", scene.rotateSelectionCCW, QKS("Shift+R"))
		Actions.add(view, "flip_horizontal", "Flip Horizontal", scene.flipSelectionHorizontal, QKS("F"))
		Actions.add(view, "flip_vertical", "Flip Vertical", scene.flipSelectionVertical, QKS("Shift+F"))
		Actions.add(view, "face_north", "Face North", lambda: scene.setFacingForSelected(Facing.NORTH), QKS("Ctrl+Up"))
		Actions.add(view, "face_east",  "Face East",  lambda: scene.setFacingForSelected(Facing.EAST),  QKS("Ctrl+Right"))
		Actions.add(view, "face_south", "Face South", lambda: scene.setFacingForSelected(Facing.SOUTH), QKS("Ctrl+Down"))
		Actions.add(view, "face_west",  "Face West",  lambda: scene.setFacingForSelected(Facing.WEST),  QKS("Ctrl+Left"))
		

		# Gate Inputs & Wiring
		Actions.add(view, "skip_wiring", "Stop Wiring", scene.skipWiring, QKS("Escape"))
		Actions.add(view, "inc_inputs", "Increase No. of Inputs", scene.increaseInputsForSelected) \
			.setShortcuts([QKS("="), QKS("+")])
		Actions.add(view, "dec_inputs", "Decrease No. of Inputs", scene.decreaseInputsForSelected) \
			.setShortcuts([QKS("-"), QKS("_")])



	def get_project_data(self) -> dict:
		t = self.view.transform()
		project = self.cscene.serialize() | {
			"iclist": self.cscene.iclist,
			"camera": (t.dx(), t.dy()),
			"zoom":   t.m11(),
		}
		return project
	
	def load_project_data(self, project: dict):
		dx, dy = project.pop("camera", (0, 0))
		m11 = project.pop("zoom", 1.0)

		self.cscene.clearCanvas()
		self.cscene.iclist = project.pop("iclist", [])
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
		logic.simulate(Const.SIMULATE)
	
	def saveFile(self, create_new_file: bool = False):
		if self.current_file_path and not create_new_file:
			# Don't ask if the project has a save file
			filename = self.current_file_path
		else:
			# Ask for file name
			filename, _ = QFileDialog.getSaveFileName(
				self,
				"Save Project",
				str(projectsPath),
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
			print("Failed to save:", e)    # TODO: why is it print?
	
	def saveFileAs(self):
		self.saveFile(True)
	
	def loadFile(self):
		# Always ask for file name
		filename, _ = QFileDialog.getOpenFileName(
			self,
			"Open Project",
			str(projectsPath),
			"JSON Files (*.json);;All Files (*)"
		)
		if not filename: return

		try:
			with open(filename, 'r') as file:
				project:dict = json.load(file)
			
			self.load_project_data(project)
			self.current_file_path = filename

		except Exception as e:
			QMessageBox.critical(
				self,
				"Load Error",
				f"Failed to load project: {os.path.basename(filename)}\n{str(e)}"
			)
	
	def addICToProject(self):
		"""Opens a dialog box"""
		ic_data_list = self.retrieve_IC_data()

		names = list(ic_data_list.keys())
		ic_name, ok = QInputDialog.getItem(
			self, "Select IC", "Add an IC to project:", names, 0, False
		)
		
		if not ok: return
		idx, filename = ic_data_list[ic_name]

		if filename:
			ic_data = logic.get_ic(filename)
		elif idx:
			ic_data = self.cscene.iclist[idx]
		
		if ic_data:
			self.spawnIC(ic_data)

	
	
	def convertProjectToIC(self):
		res = ICSetupDialog.showForm(self)
		if res["accepted"]:
			logic.reset()

			self.cscene.makeICfyable()
			filename = (ICPath / str(res["name"])).with_suffix(".json")
			logic.save_as_ic(
				str(filename),
				res["name"],
				res["tag"],
				res["desc"]
			)
			self.cscene.clearCanvas()
			logic.simulate(Const.SIMULATE)
			self.sidebar.refresh_IC_catagory.emit()



if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setOrganizationName("Darion")
	app.setApplicationName("Darion Logic Sim")


	### Paths
	docPath = QStandardPaths.writableLocation(StandardLocation.DocumentsLocation)
	appPath = QStandardPaths.writableLocation(StandardLocation.AppDataLocation)

	projectsPath = Path(docPath) / "Darion Logic Sim" / "Projects"
	projectsPath.mkdir(parents=True, exist_ok=True)

	ICPath = Path(appPath) / "IC"
	ICPath.mkdir(parents=True, exist_ok=True)


	### App Theme
	app.setStyle("Fusion")
	theme.apply_palette(app)


	### App Window
	window = AppWindow()
	
	settings = QSettings()
	if settings.contains("main_window/geometry"):
		window.restoreGeometry(settings.value("main_window/geometry"))
	else:
		window.resize(1000, 600)

	window.show()

	# Starts with an empty canvas
	QTimer.singleShot(100, window.update_props_position)
	app.aboutToQuit.connect(lambda: QSettings().setValue("main_window/geometry", window.saveGeometry()))
	QtAsyncio.run(handle_sigint=True)