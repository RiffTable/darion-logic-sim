from __future__ import annotations
from core.QtCore import *
from core.Enums import Facing, EditorState
import core.grid as GRID

from .items import CompItem, InputPinItem, OutputPinItem, WireItem, LabelItem
from .gates import GateItem, UnaryGateItem, InputItem, OutputItem





###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
COMPONENT_LOOKUP: list[tuple[int, type[CompItem], str]] = [
	(0,  UnaryGateItem, "NOT Gate"),
	(1,  GateItem,      "AND Gate"),
	(2,  GateItem,      "NAND Gate"),
	(3,  GateItem,      "OR Gate"),
	(4,  GateItem,      "NOR Gate"),
	(5,  GateItem,      "XOR Gate"),
	(6,  GateItem,      "XNOR Gate"),
	(7,  InputItem,     "Input (Toggle)"),
	(8,  OutputItem,    "LED"),

	(51, InputItem,     "Input (Hold)"),
	(52, InputItem,     "Rotary Switch"),
	(53, InputItem,     "Clock"),
	(54, InputItem,     "Constant"),

	(62, OutputItem,    "Oscilloscope"),
	(63, OutputItem,    "7-Segment Display"),
	(64, OutputItem,    "Hex Display"),
	# (11, "IC",        CompItem),
]

Name_to_ID    : dict[str, int] = {}
ID_to_Name    : dict[int, str] = {}
ID_to_Class   : dict[int, type[CompItem]] = {}
Class_to_ID   : dict[type[CompItem], int] = {}
Name_to_Class : dict[str, type[CompItem]] = {}
Class_to_Name : dict[type[CompItem], str] = {}

for id_, class_, name_ in COMPONENT_LOOKUP:
	Name_to_ID[name_]     = id_
	ID_to_Name[id_]       = name_
	ID_to_Class[id_]      = class_
	Class_to_ID[class_]   = id_
	Name_to_Class[name_]  = class_
	Class_to_Name[class_] = name_



# region: ###======= CIRCUIT SCENE =======###
class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.SIZE = 12
		self.comps: list[CompItem] = []
		self.wires: list[WireItem] = []
		self._state = EditorState.NORMAL

		self._rmb_last_pos = QPointF()

		# Wiring logic
		self.ghostWire: WireItem = None
		self.ghostPin = InputPinItem(None, QPointF(), Facing.WEST)

		self.ghostPin.hide()    # These three lines does the same thing but still...
		self.ghostPin.setEnabled(False)    # You can never be too sure
		self.ghostPin.setAcceptedMouseButtons(MouseBtn.NoButton)

		self.addItem(self.ghostPin)


	# Editor State Management
	def checkState(self, st: EditorState) -> bool:
		return self.getState() == st
	
	def getState(self):
		return self._state
		# if self.ghostWire: return EditorState.WIRING
		# return EditorState.NORMAL
	
	def setState(self, st: EditorState):
		self._state = st
		...
	
	def skipWiring(self):
		self.setState(EditorState.NORMAL)
		gwire = self.ghostWire
		self.ghostWire = None
		if gwire:
			if len(gwire.supplies) == 1:
				gwire._disconnect()
				self.removeItem(gwire)
			else:
				gwire.supplies.remove(self.ghostPin)
				self.ghostPin.setWire(None)
				gwire.updateShape()


	# Components Management
	def addComp(self, x: float, y:float, comp_id: int):
		comp_type = ID_to_Class[comp_id]
		comp = comp_type(QPointF(x, y))

		if comp_type == GateItem:
			tags = {
				0: "NOT",
				1: "AND",
				2: "NAND",
				3: "OR",
				4: "NOR",
				5: "XOR",
				6: "XNOR",
			}
			comp.labelItem.setPlainText(tags[comp_id])
		
		self.addItem(comp)
		self.comps.append(comp)
		# run_logic()
	
	def removeComp(self, comp: CompItem):
		if comp not in self.comps: return
		comp.cutConnections()

		self.comps.remove(comp)
		self.removeItem(comp)
		# run_logic()
	
	# Wires	Management
	def finishWiring(self, target: QGraphicsItem, modifiers: KeyMod):
		g_wire = self.ghostWire
		g_pin = self.ghostPin
		finishing = False

		# Wiring: Finish!
		if isinstance(target, CompItem) and hasattr(target, "proxyPin"):
			# Proxying: Wire is connected to the gate's *favorite* pin
			target = target.proxyPin()
			if target is None: return
		
		if isinstance(target, InputPinItem):
			if target.hasWire():
				# Swap Connections
				t_wire = target.getWire()
				g_wire.supplies.remove(g_pin); g_wire.supplies.append(target)
				t_wire.supplies.append(g_pin); t_wire.supplies.remove(target)
				
				g_pin.setWire(t_wire);  g_wire.updateShape()
				target.setWire(g_wire); t_wire.updateShape()
				self.ghostWire = t_wire
				
				if len(g_wire.supplies) == 1: self.wires.append(g_wire)
				finishing = False
			else:
				finishing = True
		
		if finishing:
			if len(g_wire.supplies) == 1: self.wires.append(g_wire)

			if not (modifiers & KeyMod.ShiftModifier):
				g_wire.supplies.remove(g_pin);  g_pin.setWire(None)
				self.setState(EditorState.NORMAL)
				self.ghostWire = None
			
			g_wire.supplies.append(target); target.setWire(g_wire)
			g_wire.updateShape()
			target.highlight(False)
			
			# wire.setFlag(QGraphicsItem.ItemIsSelectable, True)
			# self.clearSelection()
			# wire.setSelected(True)  # Solo select the finished wire
			# self.run_logic()

	def removeWire(self, wire: WireItem):
		# Works for both ghost wires and regular wires
		if (wire not in self.wires) and wire is self.ghostWire:
			return
		
		wire._disconnect()

		if not (wire is self.ghostWire): self.wires.remove(wire)
		self.removeItem(wire)
		# run_logic()

	###======= MOUSE/KEY EVENTS =======###
	def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
		item = self.itemAt(event.scenePos(), QTransform())

		# Wiring: Start!
		if self.checkState(EditorState.NORMAL):
			if isinstance(item, OutputPinItem) and event.button() == MouseBtn.LeftButton:
				if event.button() == Qt.LeftButton:
					self.setState(EditorState.WIRING)
					if not item.hasWire():
						self.ghostWire = WireItem(item, self.ghostPin)
						# self.ghostWire.setFlag(QGraphicsItem.ItemIsSelectable, False)
						self.addItem(self.ghostWire)
					else:
						self.ghostWire = item.getWire()
						self.ghostWire.addSupply(self.ghostPin)
		
		return super().mousePressEvent(event)

	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		# This event only takes place after the CircuitView handles its!
		# RMB drag has been handled
		btn = event.button()
		target = self.itemAt(event.scenePos(), QTransform())
		if isinstance(target, LabelItem): target = target.parentItem()

		if self.checkState(EditorState.WIRING):
			# Wiring: Finish?
			if btn == MouseBtn.LeftButton:
				self.finishWiring(target, event.modifiers())

			# Wiring: Skip!
			if btn == MouseBtn.RightButton:   # RMB click
				self.skipWiring()
		
		super().mouseReleaseEvent(event)

	def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
		self.ghostPin.setPos(GRID.snapF(event.scenePos()))
		return super().mouseMoveEvent(event)
	
	def keyPressEvent(self, event: QKeyEvent):
		key = event.key()
		if key in (Key.Key_Delete, Key.Key_Backspace, Key.Key_X):
			for item in self.selectedItems():
				if isinstance(item, WireItem):
					if item in self.wires: self.removeWire(item)
				
				elif isinstance(item, CompItem):
					if item in self.comps: self.removeComp(item)
			
			# self.run_logic()
		
		if self.checkState(EditorState.WIRING) and (event.key() == Key.Key_Escape):
			self.skipWiring()
		
		if key in (Key.Key_Plus, Key.Key_Equal, Key.Key_Minus, Key.Key_Underscore):
			for item in self.selectedItems():
				if isinstance(item, GateItem):
					is_plus = event.key() in (Key.Key_Plus, Key.Key_Equal)
					new_size = len(item.inputPins) + (1 if is_plus else -1)
					item.setInputCount(new_size)
		
		# if key == Key.Key_M:
		# 	for item in self.selectedItems():
		# 		if isinstance(item, CompItem):
		# 			item.mirror()
		# 			item.updateShape()
		
		if key == Key.Key_F:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.flip()
					item.updateShape()
		
		if key == Key.Key_R:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.rotate(not event.modifiers() & KeyMod.ShiftModifier)
					item.updateShape()
		
		if key in (Key.Key_Right, Key.Key_Down, Key.Key_Left, Key.Key_Up) \
		and event.modifiers() & KeyMod.ControlModifier:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					match key:
						case Key.Key_Right: item.setFacing(Facing.EAST)
						case Key.Key_Down:  item.setFacing(Facing.SOUTH)
						case Key.Key_Left:  item.setFacing(Facing.WEST)
						case Key.Key_Up:    item.setFacing(Facing.NORTH)
					item.updateShape()

		super().keyPressEvent(event)
	
# endregion