from __future__ import annotations
from typing import Callable
from core.QtCore import *
from core.Enums import Facing, Rotation, CompEdge, EditorState

from editor.styles import Color, Font





# Grid size and snapping
class GRID:
	SIZE = 12
	DSIZE = 2*SIZE

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



class LabelItem(QGraphicsTextItem):
	def __init__(self, text: str, parent: CompItem):
		super().__init__(text, parent)
		self.setFont(Font.default)
		



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
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
			# QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self._cached_hitbox = QPainterPath()
		self._cached_hitbox.addRect(self.rect())
		self._hover_count = 0

		# Properties
		self._size = size.toTuple()    # (Length, Width) independent of facing
		self.padding = padding.toTuple()
		self.state = False
		self.facing = Facing.EAST
		
		# isMirrored is for flipping the TOP-BOTTOM edges instead of the
		# INPUT-OUTPUT edges, as doing so will make the component
		# visually face the opposite way, ultimately making
		# self.facing sound STUPID!
		self.isMirrored = False
		self.labelText = "COMP"
		self._pinslist: dict[CompEdge, list[PinItem]] = {
			CompEdge.OUTPUT : [],
			CompEdge.BOTTOM : [],
			CompEdge.INPUT  : [],
			CompEdge.TOP    : [],
		}

		# Visual
		self.setPen(QPen(Color.outline, 2))
		self.setBrush(Color.comp_body)

		# Label
		self.labelItem = LabelItem(self.labelText, self)
		self.labelItem.setPos(5, 5)
	

	@property
	def cscene(self) -> CircuitScene: return self.scene()

	def setDimension(self, width: int, height: int):
		self._size = (width, height)
	def getDimension(self) -> tuple[int, int]:
		if self.facing%2 == 0:
			# Horizontal
			return self._size
		else:
			# Vertical
			return self._size[::-1]

	# Actions
	def rotate(self, clockwise: bool = True):
		"""Don't forget to run updateShape() afterwards"""
		self.setFacing(self.facing + (1 if clockwise else 3))
	def setFacing(self, facing: Facing):
		"""Don't forget to run updateShape() afterwards"""
		rot = Rotation(facing - self.facing)

		if rot == Rotation.FORWARD:
			return
		
		self.facing = facing
		self.updateOrientation()

	def mirror(self):
		"""Don't forget to run updateShape() afterwards"""
		self.isMirrored = not self.isMirrored
		self.updateOrientation()
	def flip(self):
		"""Don't forget to run updateShape() afterwards"""
		self.isMirrored = not self.isMirrored
		self.setFacing(Facing(self.facing+2))
	
	def updateOrientation(self):
		"""Don't forget to run updateShape() afterwards"""
		# print("---------------")
		for edge, pins in self._pinslist.items():
			# print(f"Edge {edge} facing to ", end="")
			fa, gen = self.getPinPosGenerator(edge)
			for i, pin in enumerate(pins):
				pin.facing = fa
				self.setPinPos(pin, gen(i))
	
	# Pin configuration
	def edgeToFacing(self, edge: CompEdge) -> Facing:
		mirrored = (edge%2 == 1) and self.isMirrored
		return Facing(edge + self.facing + (2 if mirrored else 0))

	def facingToEdge(self, facing: Facing) -> CompEdge:
		res = self.facing - facing
		mirrored = (res%2 == 1) and self.isMirrored
		
		return CompEdge(res + (2 if mirrored else 0))
	
	def addPin(self, index: int, edge: CompEdge, type: InputPinItem | OutputPinItem) -> InputPinItem | OutputPinItem:
		"""Don't forget to call updateShape() afterwards."""
		pinslist = self._pinslist[edge]

		fa, gen = self.getPinPosGenerator(edge)
		newpin = type(self, gen(index), fa)
		pinslist.append(newpin)
		return newpin

	def getPinPosGenerator(self, edge: CompEdge) -> tuple[Facing, Callable[[int], QPointF]]:
		"""Set `facing` and `size` before calling"""
		# fuck
		# This was way too complicated then expected
		w, h = self.getDimension()
		g = GRID.SIZE
		M = self.isMirrored

		# Final Facing
		# A, B, C, D => E, S, W, N
		# A* = Edge facing East COUNTER-CLOCKWISE
		fa = Facing(self.facing + (-edge if M else edge))

		# Final Direction: (False -> Default Rotation), (True -> Reverse Rotation)		
		fd = M ^ (edge in (1, 2))
		# print((["A", "B", "C", "D", "A*", "B*", "C*", "D*"])[fa + (4 if fd else 0)])
		match fa + (4 if fd else 0):
			case 0: return (fa, lambda i: QPointF(w*g, i*g))      # A
			case 1: return (fa, lambda i: QPointF((w-i)*g, h*g))  # B
			case 2: return (fa, lambda i: QPointF(0, (h-i)*g))    # C
			case 3: return (fa, lambda i: QPointF(i*g, 0))        # D
			case 4: return (fa, lambda i: QPointF(w*g, (h-i)*g))  # A*
			case 5: return (fa, lambda i: QPointF(i*g, h*g))      # B*
			case 6: return (fa, lambda i: QPointF(0, i*g))        # C*
			case 7: return (fa, lambda i: QPointF((w-i)*g, 0))    # D*

	
	def setPinPos(self, pin: PinItem, placement: QPointF):
		"""Set `pin.facing` before calling"""
		pin.setPos(placement)
		if pin._wire: pin._wire.updateShape()
	
	def addPins(self, index_edge_type: list[tuple[int, CompEdge, InputPinItem | OutputPinItem]]) -> None:
		for index, edge, type in index_edge_type:
			self.addPin(index, edge, type)
	
	def allPins(self):
		list_of_pinlists = self._pinslist.values()
		pins = [pin for pinlist in list_of_pinlists for pin in pinlist]    # Funniest line ever
		return pins
	
	def removePin(self, edge: CompEdge, index: int):
		"""Call `updateShape()` afterwards if needed"""
		pinlist = self._pinslist[edge]
		pin = pinlist[index]
		pin.disconnect()
		
		pinlist.pop(index)
		pin.setParentItem(None)
		self.cscene.removeItem(pin)
	
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
		if self.facing%2 == 0:
			# Horizontal
			w, h = self._size
			dx, dy = self.padding
		else:
			# Vertical
			h, w = self._size
			dy, dx = self.padding

		self.setRect(-dx, -dy, w*GRID.SIZE + 2*dx, h*GRID.SIZE + 2*dy)
		self.setHitbox()


### Gate Item
class GateItem(CompItem):
	def __init__(self, pos: QPointF | tuple[float, float]):
		super().__init__(pos, QPoint(6, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "GATE"
		self.labelItem.setPlainText(self.labelText)

		# Pins
		self.addPin(0, CompEdge.INPUT, InputPinItem)
		self.addPin(2, CompEdge.INPUT, InputPinItem)
		self.inputPins: list[InputPinItem] = self._pinslist[CompEdge.INPUT]
		self.outputPin: OutputPinItem = self.addPin(1, CompEdge.OUTPUT, OutputPinItem)
		self.setHitbox()

		self.hoverLeaveTimer = QTimer()
		self.hoverLeaveTimer.setSingleShot(True)
		self.hoverLeaveTimer.timeout.connect(self.betterHoverLeave)
		self.hoverLeaveTimer.setInterval(30)

		self.proxyIndex = 0    # Always the first unconnected pin or the peeking pin
		self.peekingPin: PinItem = None
		self.minInput = 2
		self.maxInput = 69


	# Proxying
	def proxyPin(self):
		if self.proxyIndex < len(self.inputPins):
			return self.inputPins[self.proxyIndex]
		else: return None
	
	def setInputCount(self, size: int) -> bool:
		if size > self.maxInput or size < self.minInput:
			return False
		n = len(self.inputPins)
		if size >= n:
			for _ in range(size-n):
				self.addPin(0, CompEdge.INPUT, InputPinItem)
		else:
			left = n - size

			for i in range(n-1, -1, -1):
				if left == 0: break
				pin = self.inputPins[i]

				# Only attempt to delete if not connected to a wire
				if not pin.hasWire():
					self.removePin(CompEdge.INPUT, i)
					left -= 1

					# Check the special "Proxy" constraint
					if i <= self.proxyIndex:
						self.proxyIndex = size + left
						break
		self.updateShape()
		return True

	# Input feedback
	# All events regarding "pin peeking":
	# 1. Peek Out (betterHoverEnter)
	# 2. Peek Off (betterHoverLeave)
	# 3. Default/Proxy Connection

	def betterHoverEnter(self):
		# "Peek Out": Peeks out the "Peeking Pin"
		if self.proxyIndex == len(self.inputPins) \
		and len(self.inputPins) < self.maxInput \
		and self.cscene.checkState(EditorState.WIRING):
			self.peekingPin = self.addPin(0, CompEdge.INPUT, InputPinItem)
			self.updateShape()
	
	def betterHoverLeave(self):
		# "Peek Off": Removes the "Peeking Pin" if it has been created
		if self.peekingPin and not self.peekingPin.hasWire():
			self.removePin(CompEdge.INPUT, self.proxyIndex)
			self.updateShape()
		self.peekingPin = None
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		if (activePinCountChange == +1) and pin is self.proxyPin():
			for i, p in enumerate(self.inputPins):
				if not p.hasWire():
					self.proxyIndex = i
					break
			else:
				self.proxyIndex = len(self.inputPins)
		
		if (activePinCountChange == -1) and pin in self.inputPins:
			index = self.inputPins.index(pin)
			self.proxyIndex = min(self.proxyIndex, index)

	# Events
	def updateShape(self):
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False
		return super().paint(painter, option, widget)
	
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem = None):
		self._hover_count += (+1 if hoverStatus else -1)
		# _hover_count = 0:    Not hovering component
		# _hover_count = 1:    Hovering the component
		# _hover_count = 2:    Hovering its pins
		# print(self._hover_count)

		if self._hover_count == 1 and hoverStatus:
			if not self.hoverLeaveTimer.isActive():
				self.betterHoverEnter()
			self.hoverLeaveTimer.stop()
		
		elif self._hover_count == 0 and not hoverStatus:
			self.hoverLeaveTimer.start()
		
		# Enable proxyHighlight if only the gate is being hovered, not its pins
		proxy = self.proxyPin()
		if proxy:
			proxy.proxyHighlight = True if (self._hover_count == 1) else False
			proxy.highlight(proxy is hoveredPin)
	

	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
		n = len(self.inputPins)
		w = 0
		if   n < 5:  w = 6
		elif n < 10: w = 8
		else:        w = 10
		h = 2*(n-1) if n > 3 else 4
		m = h/(n-1)
		self.setDimension(w, h)

		fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
		for i, p in enumerate(self.inputPins):
			p.facing = fa
			self.setPinPos(p, gen(m*i))
		
		opin = self.outputPin
		fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
		opin.facing = fa
		self.setPinPos(opin, gen(h/2))
		super()._updateShape()



### Gate Item
class UnaryGateItem(CompItem):
	def __init__(self, pos: QPointF | tuple[float, float]):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "NOT"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)

		# Pins
		self.inputPin: InputPinItem   = self.addPin(1, CompEdge.INPUT, InputPinItem)
		self.outputPin: OutputPinItem = self.addPin(1, CompEdge.OUTPUT, OutputPinItem)
		self.setHitbox()

		# Properties
		self.minInput = 1
		self.maxInput = 1



class InputItem(CompItem):
	def __init__(self, pos: QPointF | tuple[float, float]):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "IN"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)
		
		# Pins
		self.outputPin: OutputPinItem = self.addPin(1, CompEdge.OUTPUT, OutputPinItem)
		self.setHitbox()

		# Properties
	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == Qt.MouseButton.LeftButton:
			delta = event.scenePos() - event.buttonDownScenePos(Qt.MouseButton.LeftButton)
			if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
				self.state = not self.state
				self.updateVisual()
			return super().mouseReleaseEvent(event)
	
	def updateVisual(self):
		self.setPen(QPen(Color.outline, 2))
		if self.state: self.setBrush(Color.comp_on)
		else:          self.setBrush(Color.comp_body)



class OutputItem(CompItem):
	def __init__(self, pos: QPointF | tuple[float, float]):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "OUT"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)
		
		# Pins
		self.inputPin: InputPinItem = self.addPin(1, CompEdge.INPUT, InputPinItem)
		self.setHitbox()

		# Properties
	

	def updateVisual(self):
		self.setPen(QPen(Color.outline, 2))
		if self.state: self.setBrush(Color.LED_on)
		else:          self.setBrush(Color.LED_off)

# endregion



# region: ###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parentComp: CompItem, relpos: QPointF, facing: Facing):
		super().__init__(
			-GRID.SIZE, -GRID.SIZE,
			GRID.DSIZE, GRID.DSIZE,
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
		"""Doesn't remove its reference from its wire. Use disconnect() then"""
		if self._wire is wire: return

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

		# self.updateVisual()
		# self.updateShape()
	
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


	# Components Management
	def addComp(self, x: float, y:float, comp_id: int):
		comp_type = ID_to_Class[comp_id]
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
	
	# Wires	Management
	def finishWiring(self, target: QGraphicsItem, modifiers: Qt.KeyboardModifier):
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
			if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
				g_wire.supplies.remove(g_pin);  g_pin.setWire(None)
				self.setState(EditorState.NORMAL)
				self.ghostWire = None
			
			g_wire.supplies.append(target); target.setWire(g_wire)
			g_wire.updateShape()
			target.highlight(False)
			
			# wire.setFlag(QGraphicsItem.ItemIsSelectable, True)
			if len(g_wire.supplies) == 1: self.wires.append(g_wire)
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
		# This event only takes place after the CircuitView handles its!
		# RMB drag has been handled
		btn = event.button()
		target = self.itemAt(event.scenePos(), QTransform())
		if isinstance(target, LabelItem): target = target.parentItem()

		if self.checkState(EditorState.WIRING):
			# Wiring: Finish?
			if btn == Qt.MouseButton.LeftButton:
				self.finishWiring(target, event.modifiers())

			# Wiring: Skip!
			if btn == Qt.MouseButton.RightButton:   # RMB click
				self.skipWiring()
		
		super().mouseReleaseEvent(event)

	def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
		self.ghostPin.setPos(GRID.snapF(event.scenePos()))
		return super().mouseMoveEvent(event)
	
	def keyPressEvent(self, event: QKeyEvent):
		key = event.key()
		if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_X):
			for item in self.selectedItems():
				if isinstance(item, WireItem):
					if item in self.wires: self.removeWire(item)
				
				elif isinstance(item, CompItem):
					if item in self.comps: self.removeComp(item)
			
			# self.run_logic()
		
		if self.checkState(EditorState.WIRING) and (event.key() == Qt.Key.Key_Escape):
			self.skipWiring()
		
		if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
			for item in self.selectedItems():
				if isinstance(item, GateItem):
					is_plus = event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal)
					new_size = len(item.inputPins) + (1 if is_plus else -1)
					item.setInputCount(new_size)
		
		# if key == Qt.Key.Key_M:
		# 	for item in self.selectedItems():
		# 		if isinstance(item, CompItem):
		# 			item.mirror()
		# 			item.updateShape()
		
		if key == Qt.Key.Key_F:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.flip()
					item.updateShape()
		
		if key == Qt.Key.Key_R:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.rotate(not event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
					item.updateShape()
		
		if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Up) \
		and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					match key:
						case Qt.Key.Key_Right: item.setFacing(Facing.EAST)
						case Qt.Key.Key_Down:  item.setFacing(Facing.SOUTH)
						case Qt.Key.Key_Left:  item.setFacing(Facing.WEST)
						case Qt.Key.Key_Up:    item.setFacing(Facing.NORTH)
					item.updateShape()

		super().keyPressEvent(event)
	
# endregion