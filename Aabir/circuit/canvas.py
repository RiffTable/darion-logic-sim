from __future__ import annotations
from typing import cast, TYPE_CHECKING
from enum import IntEnum
from QtCore import *

from styles import Color, Font
from Enums import Facing, CompEdge, Rotation, EditorState





# Grid size and snapping
class GRID:
	SIZE = 12

	@staticmethod
	def snapF(point: QPointF) -> QPointF:
		s = GRID.SIZE
		return QPointF(
			round(point.x()/s)*s,
			round(point.y()/s)*s
		)
	
	@staticmethod
	def snapT(tup: tuple[float, float]) -> tuple[float, float]:
		s = GRID.SIZE
		return (
			round(tup[0]/s)*s,
			round(tup[1]/s)*s
		)



# region: ###======= COMPONENT ITEM =======###
class CompItem(QGraphicsRectItem):
	def __init__(
			self,
			pos: QPointF | tuple[float, float],
			size: QPoint | tuple[int, int],
			padding: QPointF | tuple[float, float] = QPointF(0, 3)
		):
		x, y = GRID.snapF(pos).toTuple()
		w, h = size.toTuple()
		dx, dy = padding.toTuple()
		super().__init__(-dx, -dy, w*GRID.SIZE + 2*dx, h*GRID.SIZE + 2*dy)
		
		# Behavior
		self.setPos(x, y)
		self.setZValue(0)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
			QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)

		# Properties
		self.size = size if isinstance(size, tuple) else size.toTuple()
		self.padding = padding if isinstance(padding, tuple) else padding.toTuple()
		self.state = False
		self.facing = Facing.EAST
		self.labelText = "COMP"
		self._pinslist: dict[CompEdge, list[PinItem]] = {
			CompEdge.INPUT  : [],
			CompEdge.OUTPUT : [],
			CompEdge.TOP    : [],
			CompEdge.BOTTOM : [],
		}

		# Visual
		self.setPen(QPen(Color.outline, 2))
		self.setBrush(Color.gate)

		# fuck
		self.addPins([
			(1, CompEdge.INPUT, InputPinItem),
			(3, CompEdge.INPUT, InputPinItem),
			(2, CompEdge.OUTPUT, OutputPinItem)
		])


		# Label
		self.labelItem = QGraphicsTextItem(self.labelText, self)
		self.labelItem.setFont(Font.default)
		self.labelItem.setPos(5, 10)
	
	def edgeFacing(self, edge: CompEdge) -> Facing:
		# fuck
		return {
			CompEdge.INPUT : Facing.WEST,
			CompEdge.OUTPUT: Facing.EAST,
			CompEdge.TOP   : Facing.NORTH,
			CompEdge.BOTTOM: Facing.SOUTH
		}[edge]
	
	def addPin(self, index: int, edge: CompEdge, type: InputPinItem | OutputPinItem) -> InputPinItem | OutputPinItem:
		pinslist = self._pinslist[edge]
		pin_facing = self.edgeFacing(edge)

		w, h = self.size
		pos = {
			Facing.WEST:  (0, index*GRID.SIZE),
			Facing.EAST:  (w*GRID.SIZE, index*GRID.SIZE),
			Facing.NORTH: (index*GRID.SIZE, 0),
			Facing.SOUTH: (index*GRID.SIZE, h*GRID.SIZE)
		}[pin_facing]
		newpin = type(self, pos, pin_facing)
		pinslist.append(newpin)
		return newpin
	
	def addPins(self, index_edge_type: list[tuple[int, CompEdge, InputPinItem | OutputPinItem]]) -> None:
		for index, edge, type in index_edge_type:
			self.addPin(index, edge, type)
	
	def allPins(self):
		list_of_pinlists = self._pinslist.values()
		pins = [pin for pinlist in list_of_pinlists for pin in pinlist]    # Funniest line ever
		return pins
	
	def cutConnections(self):
		for p in self.allPins():
			p.disconnect()
	
	def pinUpdate(self, pin: PinItem):
		...    # ABSTRACT METHOD

	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemPositionChange:
			return GRID.snapF(value)

		return super().itemChange(change, value)
	
	def updateVisual(self):
		...
	
	# def mouseReleaseEvent(self, event):
	# 	return super().mouseReleaseEvent(event)


### Gate Item
class GateItem(CompItem):
	def __init__(
			self,
			pos: QPointF | tuple[float, float],
			size: QPoint | tuple[int, int]
		):
		super().__init__(pos, size)
		self.addPins([
			(1, CompEdge.INPUT, InputPinItem),
			(3, CompEdge.INPUT, InputPinItem),
			(2, CompEdge.OUTPUT, OutputPinItem),
		])
# endregion



# region: ###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parentComp: CompItem, relpos: tuple[float, float], facing: Facing):
		super().__init__(
			-GRID.SIZE/2, -GRID.SIZE/2,
			GRID.SIZE, GRID.SIZE,
			parentComp
		)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self.setPen(Qt.PenStyle.NoPen)
		self.setAcceptHoverEvents(True)
		self.setZValue(1)

		self.state = False
		self._wire: WireItem = None
		self.isHighlighted = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(*relpos)
	
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			if self._wire: self._wire.updatePath()
		
		return super().itemChange(change, value)
	
	def highlight(self, isHovered: bool) -> None:
		...    # ABSTRACT METHOD
	def disconnect(self):
		...    # ABSTRACT METHOD
	
	def setWire(self, wire: WireItem):
		self._wire = wire
		self.updateVisual()
		parent: CompItem = self.parentItem()
		if parent: parent.pinUpdate(self)

	def hoverEnterEvent(self, event): self.highlight(True);  super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event): self.highlight(False); super().hoverLeaveEvent(event)
	
	def paint(self, painter: QPainter, option, widget):
		# The HITBOX of the pin is larger (half of SIZE) than the visible radius
		r = 4

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))
	
	def updateVisual(self):
		if self.isHighlighted:
			self.setPen(QPen(Color.outline, 2))
			self.setBrush(QBrush(Color.pin_hover))
		
		elif self._wire:
			self.setPen(Qt.PenStyle.NoPen)
			self.setBrush(Qt.BrushStyle.NoBrush)
		
		else:
			self.setPen(QPen(Color.outline, 2))
			if self.state:
				self.setBrush(QBrush(Color.pin_on))
			else:
				self.setBrush(QBrush(Color.pin_off))


### Input Pin
class InputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)

	def disconnect(self):
		if not self._wire: return

		self._wire.cutSupply(self)
	
	def highlight(self, isHovered: bool) -> None:
		scene: CircuitScene = self.scene()
		self.isHighlighted = isHovered and scene.checkState(EditorState.WIRING)
		self.updateVisual()


### Output Pin
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def disconnect(self):
		if not self._wire: return

		scene: CircuitScene = self.scene()
		scene.removeWire(self._wire)
	
	def highlight(self, isHovered: bool) -> None:
		scene: CircuitScene = self.scene()
		self.isHighlighted = isHovered and scene.checkState(EditorState.NORMAL)
		self.updateVisual()
# endregion



# region: ###======= WIRE ITEM =======###
class WireItem(QGraphicsPathItem):
	MINWALK = 2
	def __init__(self, beg: OutputPinItem, end: InputPinItem):
		super().__init__()

		# Behavior
		self.setFlags(QGraphicsItem.ItemIsSelectable)
		self.setZValue(-1)

		beg.setWire(self)
		end.setWire(self)

		# Properties
		self.state = False
		self.source = beg
		self.supplies: list[InputPinItem] = [end]

		self.updatePath()
	
	def addSupply(self, pin: InputPinItem):
		if pin in self.supplies: return
		self.supplies.append(pin)
		pin.setWire(self)
		self.updatePath()
	
	def cutSupply(self, pin: InputPinItem):
		if not pin in self.supplies: return

		pin.setWire(None)
		self.supplies.remove(pin)

		# Check if wire has any supply left
		if len(self.supplies) == 0:
			scene: CircuitScene = self.scene()
			scene.removeWire(self)
		else:
			self.updatePath()
		
	def _disconnect(self):
		"""Don't forget to use `scene.removeItem` afterwards"""

		self.source.setWire(None)
		for supply in self.supplies:
			supply.setWire(None)
	
	def updateVisual(self):
		color = Color.signal_on if self.state else Color.signal_off
		# if self.isSelected(): color = QColor("#f39c12")
		self.setPen(QPen(color, 3))
	
	def updatePath(self):
		path = QPainterPath()
		p1 = self.source.scenePos()
		dx1, dy1 = self.source.facing.toTuple(50)

		for out in self.supplies:
			p2 = out.scenePos()
			dx2, dy2 = out.facing.toTuple(50)
			path.moveTo(p1)
			path.cubicTo(
				p1.x() + dx1, p1.y() + dy1,
				p2.x() + dx2, p2.y() + dy2,
				p2.x(), p2.y()
			)
			path.lineTo(p2)
		
		self.setPath(path)
		self.updateVisual()
# endregion



###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
COMPONENT_LOOKUP: list[tuple[str, int, type[CompItem]]] = [
	("NOT Gate", 0, CompItem),
	("AND Gate", 1, CompItem),
	("NAND Gate", 2, CompItem),
	("OR Gate", 3, CompItem),
	("NOR Gate", 4, CompItem),
	("XOR Gate", 5, CompItem),
	("XNOR Gate", 6, CompItem),
]

Name_to_ID    : dict[str, int] = {}
ID_to_Name    : dict[int, str] = {}
ID_to_Class   : dict[int, type[CompItem]] = {}
Class_to_ID   : dict[type[CompItem], int] = {}
Name_to_Class : dict[str, type[CompItem]] = {}
Class_to_Name : dict[type[CompItem], str] = {}

for name_, id_, class_ in COMPONENT_LOOKUP:
	Name_to_ID[name_]     = {id_}
	ID_to_Name[id_]       = {name_}
	ID_to_Class[id_]      = {class_}
	Class_to_ID[class_]   = {id_}
	Name_to_Class[name_]  = {class_}
	Class_to_Name[class_] = {name_}



# region: ###======= CIRCUIT SCENE =======###
class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.SIZE = 12
		self.comps: list[CompItem] = []
		self.wires: list[WireItem] = []
		self._state = EditorState.NORMAL

		# Wiring logic
		self.ghostWire: WireItem = None
		self.ghostPin = InputPinItem(None, (0, 0), Facing.WEST)
		self.ghostPin.hide()
		self.ghostPin.setEnabled(False)
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
				gwire.updatePath()


	# Adding & Removing Components
	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y), QPoint(5, 4))
		self.addItem(comp)
		self.comps.append(comp)
		# run_logic()
	
	def removeComp(self, comp: CompItem):
		if comp not in self.comps: return
		comp.cutConnections()

		self.comps.remove(comp)
		self.removeItem(comp)
		# run_logic()
	
	# ~~Adding~~ Removing Wires	
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

		if self.checkState(EditorState.WIRING) and event.button() == Qt.MouseButton.RightButton:
			self.skipWiring()
		
		# Wiring: Start!
		if isinstance(item, OutputPinItem):
			if event.button() == Qt.LeftButton:
				self.setState(EditorState.WIRING)
				if not item._wire:
					self.ghostWire = WireItem(item, self.ghostPin)
					self.addItem(self.ghostWire)
				else:
					self.ghostWire = item._wire
					self.ghostWire.addSupply(self.ghostPin)
		
		return super().mousePressEvent(event)

	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		
		# Wiring: Finish?!
		if self.checkState(EditorState.WIRING):

			item = self.itemAt(event.scenePos(), QTransform())
			skipping = (item is None)
			connecting = False
			if isinstance(item, InputPinItem):
				if not item._wire: connecting = True

			if connecting:
				wire = self.ghostWire

				# Swap supply pins
				wire.supplies.remove(self.ghostPin)
				self.ghostPin.setWire(None)
				wire.supplies.append(item)
				item.setWire(wire)

				wire.updatePath()
				
				if len(wire.supplies) == 1: self.wires.append(wire)
				
				self.setState(EditorState.NORMAL)
				self.ghostWire = None
				# self.run_logic()
			
			if skipping: self.skipWiring()
		
		super().mouseReleaseEvent(event)

	def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
		self.ghostPin.setPos(GRID.snapF(event.scenePos()))
		return super().mouseMoveEvent(event)
	
	def keyPressEvent(self, event: QKeyEvent):
		if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_X):
			for item in self.selectedItems():
				if isinstance(item, WireItem):
					if item in self.wires: self.removeWire(item)
				
				elif isinstance(item, CompItem):
					if item in self.comps: self.removeComp(item)
			
			# self.run_logic()
		
		if self.checkState(EditorState.WIRING) and (event.key() == Qt.Key.Key_Escape):
			self.skipWiring()
			
		super().keyPressEvent(event)
# endregion