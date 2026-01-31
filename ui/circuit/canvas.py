from __future__ import annotations
from typing import cast, TYPE_CHECKING
from functools import partial
from common.QtCore import *
from common.Enums import Facing, Rotation, CompEdge, EditorState

from ui.styles import Color, Font





# Grid size and snapping
class GRID:
	SIZE = 24

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
			size: QPoint,
			padding: QPointF = QPointF(0, 9)
		):
		x, y = GRID.snapF(pos).toTuple()
		w, h = size.toTuple()
		dx, dy = padding.toTuple()
		super().__init__(-dx, -dy, w*GRID.SIZE + 2*dx, h*GRID.SIZE + 2*dy)
		
		# Behavior
		self._dirty = True
		self.setPos(x, y)
		self.setZValue(0)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
			QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self._cached_hitbox = QPainterPath()
		self._cached_hitbox.addRect(self.rect())
		self._hover_count = 0

		# Properties
		self.size = size.toTuple()
		self.padding = padding.toTuple()
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

		# Label
		self.labelItem = QGraphicsTextItem(self.labelText, self)
		self.labelItem.setFont(Font.default)
		self.labelItem.setPos(5, 5)
	
	@property
	def cscene(self) -> CircuitScene: return self.scene()
	

	# Pin configuration
	def edgeToFacing(self, edge: CompEdge) -> Facing:
		# fuck
		return {
			CompEdge.INPUT : Facing.WEST,
			CompEdge.OUTPUT: Facing.EAST,
			CompEdge.TOP   : Facing.NORTH,
			CompEdge.BOTTOM: Facing.SOUTH
		}[edge]
	def facingToEdge(self, facing: Facing) -> CompEdge:
		# fuck
		return {
			Facing.WEST : CompEdge.INPUT,
			Facing.EAST : CompEdge.OUTPUT,
			Facing.NORTH: CompEdge.TOP,
			Facing.SOUTH: CompEdge.BOTTOM
		}[facing]
	
	def addPin(self, index: int, edge: CompEdge, type: InputPinItem | OutputPinItem) -> InputPinItem | OutputPinItem:
		"""Don't forget to call updateShape() afterwards."""
		pinslist = self._pinslist[edge]
		pin_facing = self.edgeToFacing(edge)

		pos = self.getPinPos(pin_facing, index)
		newpin = type(self, pos, pin_facing)
		pinslist.append(newpin)
		return newpin
	
	def getPinPos(self, pinFacing: Facing, index: int):
		w, h = self.size
		return {
			Facing.WEST:  QPointF(0, index*GRID.SIZE),
			Facing.EAST:  QPointF(w*GRID.SIZE, index*GRID.SIZE),
			Facing.NORTH: QPointF(index*GRID.SIZE, 0),
			Facing.SOUTH: QPointF(index*GRID.SIZE, h*GRID.SIZE)
		}[pinFacing]
	
	def setPinPos(self, pin: PinItem, index: int):
		pin.setPos(self.getPinPos(pin.facing, index))
		w = pin.getWire()
		if w: w.updateShape()
	
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
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		...    # ABSTRACT METHOD

	def setHitbox(self):
		"""Always call this after adding pins. Edges without any pins will not have any \"hitbox\""""
		# fucked up inefficient algorithm. and yes I mark my incomplete code with fuck
		self.prepareGeometryChange()
		path = QPainterPath()

		girth = GRID.SIZE
		rect = self.rect().adjusted(
			-girth if len(self._pinslist[self.facingToEdge(Facing.WEST)])  > 0 else 0,
			-girth if len(self._pinslist[self.facingToEdge(Facing.NORTH)]) > 0 else 0,
			+girth if len(self._pinslist[self.facingToEdge(Facing.EAST)])  > 0 else 0,
			+girth if len(self._pinslist[self.facingToEdge(Facing.SOUTH)]) > 0 else 0
		)
		
		path.addRect(rect)
		self._cached_hitbox = path

	# Events
	def hoverEnterEvent(self, event): self._updateHoverStatus(True);  return super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event): self._updateHoverStatus(False); return super().hoverLeaveEvent(event)
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem = None):
		...    # ABSTRACT METHOD
	
	def shape(self) -> QPainterPath:
		return self._cached_hitbox
	def boundingRect(self) -> QRectF:
		return self._cached_hitbox.boundingRect()
	
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemPositionChange:
			return GRID.snapF(value)

		return super().itemChange(change, value)
	
	def updateShape(self):
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False
		return super().paint(painter, option, widget)
	
	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
		w, h = self.size
		dx, dy = self.padding

		self.setRect(-dx, -dy, w*GRID.SIZE + 2*dx, h*GRID.SIZE + 2*dy)
		self.setHitbox()


### Gate Item
class GateItem(CompItem):
	def __init__(self, pos: QPointF | tuple[float, float]):
		super().__init__(pos, QPoint(4, 2))
		
		# Behavior
		self.setAcceptHoverEvents(True)

		# Pins
		self.addPin(0, CompEdge.INPUT, InputPinItem)
		self.addPin(2, CompEdge.INPUT, InputPinItem)
		self.inputPins: list[InputPinItem] = self._pinslist[CompEdge.INPUT]
		self.outputPin: OutputPinItem = self.addPin(1, CompEdge.OUTPUT, OutputPinItem)
		self.setHitbox()

		self.peekOffTimer = QTimer()
		self.peekOffTimer.setSingleShot(True)
		self.peekOffTimer.timeout.connect(self.peekOff)
		self.peekOffTimer.setInterval(30)

		self.activePin: int = 0

		# Properties
		self.breadth: int = self.size[0]


	# Input feedback
	def peekOut(self):
		# Peeks out the "Peeking Pin"
		# print(f"actPin = {self.activePin}")
		# print(f"pinNum = {len(self.inputPins)}")
		if self.activePin == len(self.inputPins) \
		and self.cscene.checkState(EditorState.WIRING):
			self.addPin(0, CompEdge.INPUT, InputPinItem)
			self.updateShape()
	
	def peekOff(self):
		# Removes the "Peeking Pin" if it has been created
		if self.activePin < len(self.inputPins) \
		and len(self.inputPins) > 2 \
		and self.cscene.checkState(EditorState.WIRING):
			peekingPin = self.inputPins.pop()
			self.cscene.removeItem(peekingPin)
			self.updateShape()
		# print("Hover Exit")
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		if isinstance(pin, InputPinItem):
			self.activePin += activePinCountChange

	# Events
	def updateShape(self):
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False
		return super().paint(painter, option, widget)
	
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem = None):
		self._hover_count += (+1 if hoverStatus else -1)

		if self._hover_count == 1 and hoverStatus:
			if not self.peekOffTimer.isActive():
				# Hover Enter
				self.peekOut()
				# print("Hover Enter")
			self.peekOffTimer.stop()
		
		elif self._hover_count == 0 and not hoverStatus:
			# Hover Exit
			self.peekOffTimer.start()
		
		# Enable proxyHighlight if only the gate is being hovered, not its pins
		print(f"S: {1 if hoverStatus else 0}, P: {"N" if hoveredPin == None else "P"}")
		pin = self.inputPins[self.activePin]
		pin.proxyHighlight = True if (hoverStatus and (hoveredPin == None)) else False
		pin.highlight(False)
	

	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
		n = len(self.inputPins)
		self.size = (self.breadth, (n//2) * 2)

		i = y = 0
		while i < n//2:  self.setPinPos(self.inputPins[i], y); i += 1; y += 1
		if n%2 == 0: y += 1
		while i < n:     self.setPinPos(self.inputPins[i], y); i += 1; y += 1
		
		self.setPinPos(self.outputPin, n//2)
		super()._updateShape()



class InputItem(CompItem):
	...
class OutputItem(CompItem):
	...
# endregion



# region: ###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parentComp: CompItem, relpos: QPointF, facing: Facing):
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
		self.proxyHighlight = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(relpos)
	
	@property
	def cscene(self) -> CircuitScene: return self.scene()
	@property
	def parentComp(self) -> CompItem: return self.parentItem()
	
	def highlight(self, isHovered: bool) -> None:
		...    # ABSTRACT METHOD
	def disconnect(self):
		...    # ABSTRACT METHOD
	
	
	# Wire configuration
	def setWire(self, wire: WireItem):
		if self._wire != wire:
			apcc = (1 if wire else 0) - (1 if self._wire else 0)
			self._wire = wire
			self.updateVisual()

			if self.parentComp:
				self.parentComp.pinUpdate(self, apcc)
	
	def getWire(self): return self._wire
	def hasWire(self): return self._wire != None


	# Events
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			if self._wire: self._wire.updateShape()
		
		return super().itemChange(change, value)

	def hoverEnterEvent(self, event):
		self.highlight(True);  self.parentComp._updateHoverStatus(True, self)
		super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event):
		self.highlight(False); self.parentComp._updateHoverStatus(False, self)
		super().hoverLeaveEvent(event)
	
	def paint(self, painter: QPainter, option, widget):
		# The HITBOX of the pin is larger (half of SIZE) than the visible radius
		r = 5

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))
	
	def updateVisual(self):
		if self.isHighlighted:
			self.setBrush(QBrush(Color.pin_hover))
		
		elif self._wire:
			self.setBrush(Qt.BrushStyle.NoBrush)
		
		else:
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
		self.isHighlighted = (
			(isHovered or self.proxyHighlight)
			and (not self._wire)
			and self.cscene.checkState(EditorState.WIRING)
		)
		self.updateVisual()


### Output Pin
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def disconnect(self):
		if not self._wire: return

		self.cscene.removeWire(self._wire)
	
	def highlight(self, isHovered: bool) -> None:
		self.isHighlighted = (
			(isHovered or self.proxyHighlight)
			and self.cscene.checkState(EditorState.NORMAL)
		)
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
		self._dirty = False

		beg.setWire(self)
		end.setWire(self)

		# Properties
		self.state = False
		self.source = beg
		self.supplies: list[InputPinItem] = [end]

		self.updateShape()
	
	@property
	def cscene(self) -> CircuitScene: return self.scene()

	# Connection configuration
	def addSupply(self, pin: InputPinItem):
		if pin in self.supplies: return
		self.supplies.append(pin)
		pin.setWire(self)
		self.updateShape()
	
	def cutSupply(self, pin: InputPinItem):
		if not pin in self.supplies: return

		pin.setWire(None)
		self.supplies.remove(pin)

		# Check if wire has any supply left
		if len(self.supplies) == 0:
			self.cscene.removeWire(self)
		else:
			self.updateShape()
		
	def _disconnect(self):
		"""Don't forget to use `scene.removeItem` afterwards"""

		self.source.setWire(None)
		for supply in self.supplies:
			supply.setWire(None)
	
	# Events
	def updateVisual(self):
		color = Color.signal_on if self.state else Color.signal_off
		# if self.isSelected(): color = QColor("#f39c12")
		self.setPen(QPen(color, 3))
	
	def updateShape(self):
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False
		return super().paint(painter, option, widget)

	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
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
	("NOT Gate", 0, GateItem),
	("AND Gate", 1, GateItem),
	("NAND Gate", 2, GateItem),
	("OR Gate", 3, GateItem),
	("NOR Gate", 4, GateItem),
	("XOR Gate", 5, GateItem),
	("XNOR Gate", 6, GateItem),
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

		self._rmb_last_pos = QPointF()

		# Wiring logic
		self.ghostWire: WireItem = None
		self.ghostPin = InputPinItem(None, QPointF(), Facing.WEST)
		self.ghostPin.hide()
		self.ghostPin.setEnabled(False)
		self.ghostPin.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
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


	# Adding & Removing Components
	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y))
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

		# Wiring: Start!
		if self.checkState(EditorState.NORMAL):
			if isinstance(item, OutputPinItem) and event.button() == Qt.MouseButton.LeftButton:
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
		if self.checkState(EditorState.WIRING) and event.button() == Qt.MouseButton.LeftButton:
			target = self.itemAt(event.scenePos(), QTransform())
			
			if isinstance(target, InputPinItem) and not target.hasWire():
				# Wiring: Finish!
				wire = self.ghostWire

				# Swap supply pins
				wire.supplies.remove(self.ghostPin)
				self.ghostPin.setWire(None)
				wire.supplies.append(target)
				target.setWire(wire)

				wire.updateShape()
				# wire.setFlag(QGraphicsItem.ItemIsSelectable, True)

				if len(wire.supplies) == 1: self.wires.append(wire)
				# self.clearSelection()
				# wire.setSelected(True)  # Solo select the finished wire
				
				self.setState(EditorState.NORMAL)
				self.ghostWire = None
				# self.run_logic()
		
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