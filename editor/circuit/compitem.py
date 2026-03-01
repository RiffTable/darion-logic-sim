from __future__ import annotations
from typing import Callable, cast, TYPE_CHECKING, Any
from core.QtCore import *
from core.LogicCore import *
from core.Enums import Facing, CompEdge, Prop
import core.grid as GRID

from editor.styles import Color, Font
from .pins import PinItem, InputPinItem, OutputPinItem

if TYPE_CHECKING:
	from .canvas import CircuitScene






class CompItem(QGraphicsItem):
	TAG: str
	ID: int    # Value assigned via `catalog.py`
	DESC: str
	NAME: str
	LOGIC: int
	def __init__(self, pos: QPointF, **kwargs):
		# Properties
		self.tag = self.TAG
		self.facing = Facing(kwargs.get("facing", Facing.EAST))
		self.isMirrored = kwargs.get("mirror", False)

		# isMirrored is for flipping the TOP-BOTTOM edges instead of the
		# INPUT-OUTPUT edges, as doing so will make the component
		# visually face the opposite way, ultimately making
		# self.facing sound STUPID!
		
		self._pinslist: dict[CompEdge, list[PinItem]] = {
			CompEdge.OUTPUT : [],
			CompEdge.BOTTOM : [],
			CompEdge.INPUT  : [],
			CompEdge.TOP    : [],
		}

		super().__init__()
		self.setPos(GRID.snapF(pos))
		self.setZValue(0)
		self.setFlags(
			GraphicsItemFlag.ItemIsMovable |
			GraphicsItemFlag.ItemIsSelectable |
			GraphicsItemFlag.ItemSendsGeometryChanges
			# GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self.setAcceptHoverEvents(True)

		# Behavior
		self._dirty = True
		self._rect = QRectF()
		self._cached_hitbox = QPainterPath()
		self._prop_change_listener: list[Callable[[], None]] = []

		self._unit = cast(Any, logic.getcomponent(self.LOGIC))
		self._unit.listener.append(self.unitStateChanged)

		self._setupDefaultPins = False if ("pinslist" in kwargs) else True
		if not self._setupDefaultPins:
			new_pinslist = cast(dict[str, list[dict]], kwargs.get("pinslist", {}))
			for _edge, pins in new_pinslist.items():
				edge = CompEdge(int(_edge))
				facing = self.edgeToFacing(edge)
				pinslist = self._pinslist[edge]
				for pin in pins:
					PinType = InputPinItem if pin["isInput"] else OutputPinItem
					newpin = PinType(self, QPointF(*pin["pos"]), facing)
					#? Logical Not Set Yet. Do that in the child classes
					pinslist.append(newpin)

		# Proxy & Hovering
		self._hover_count = 0
		self.hoverLeaveTimer = QTimer()
		self.hoverLeaveTimer.setSingleShot(True)
		self.hoverLeaveTimer.timeout.connect(self.betterHoverLeave)
		self.hoverLeaveTimer.setInterval(30)

		# How to Write Constructors for children of CompItem:
		# 1. Properties
		# 2. Pins Setup
		# 3. Pins Casting
		# 4. Setting Pin Logicals (For both regular constructor and deserialization)
		# 5. Final Setup
		# Methods to Override (Mandatory):
		#=> getRel Size/Padding, 
		# Methods to Override (Optional):
		#=> getData, get/set Properties, pinUpdate, proxyPin
		#=> betterHoverEnter, betterHoverLeave
		#=> draw
	

	@property
	def cscene(self): return cast('CircuitScene', self.scene())

	
	### Properties Data
	def getData(self):
		return {
			"id"       : self.ID,
			"pos"      : self.pos().toTuple(),
			"tag"      : self.tag,
			"facing"   : self.facing.value,
			"mirror"   : self.isMirrored,
			"pinslist" : {
				edge.value: [p.getData() for p in pins]
				for edge, pins in self._pinslist.items()
			},
		}


	def getProperties(self) -> dict[Prop, Any]:
		return {
			Prop.POS       : self.pos().toTuple(),
			Prop.TAG       : self.tag,
			Prop.FACING    : self.facing,
			Prop.MIRROR    : self.isMirrored,
		}
	
	def setProperty(self, prop: Prop, value) -> bool:
		if prop == Prop.TAG:
			self.tag = value
			self.PropertyChanged(); return True
		elif prop == Prop.FACING:
			self.setFacing(value)
			self.PropertyChanged(); return True
		elif prop == Prop.MIRROR:
			if self.isMirrored != value:
				self.mirror()
			self.PropertyChanged(); return True
		else:
			return False

	def addPropertyChangedListener(self, listener):
		self._prop_change_listener.append(listener)
	def removePropertyChangedListener(self, listener):
		self._prop_change_listener.remove(listener)
	
	def PropertyChanged(self):
		for listener in self._prop_change_listener:
			listener()


	def unitStateChanged(self, state: int):
		...    # ABSTRACT METHOD


	### Facing and Rotation
	def setFacing(self, facing: Facing):
		rotation = (facing - self.facing) % 4
		if rotation == 0: return

		w, h = self.getAbsSize()
		self.facing = facing
		new_w, new_h = self.getAbsSize()

		if rotation == 1:  
			# 90° CW
			rotator = lambda x, y: (
				(-y + 0.5) * new_w*GRID.SIZE,
				(+x + 0.5) * new_h*GRID.SIZE
			)
		elif rotation == 2:
			# 180° CW
			rotator = lambda x, y: (
				(-x + 0.5) * new_w*GRID.SIZE,
				(-y + 0.5) * new_h*GRID.SIZE
			)
		elif rotation == 3:
			# 270° CW
			rotator = lambda x, y: (
				(+y + 0.5) * new_w*GRID.SIZE,
				(-x + 0.5) * new_h*GRID.SIZE
			)
		
		for edge, pinlist in self._pinslist.items():
			fa = self.edgeToFacing(edge)
			for pin in pinlist:
				pin.facing = fa
				x, y = pin.pos().toTuple()

				dx = x / (w*GRID.SIZE) - 0.5
				dy = y / (h*GRID.SIZE) - 0.5

				new_dx, new_dy = rotator(dx, dy)
				pin.setPos(new_dx, new_dy)

		self.updateShape()
		self.PropertyChanged()

	def mirror(self):
		self.isMirrored = not self.isMirrored
		w, h = self.getAbsSize()

		if self.facing%2 == 0:
			mirrorer = lambda x, y: (x, h*GRID.SIZE-y)    # Horizontal
		else:
			mirrorer = lambda x, y: (w*GRID.SIZE-x, y)    # Vertical
		
		for edge, pinlist in self._pinslist.items():
			fa = self.edgeToFacing(edge)
			for pin in pinlist:
				pin.facing = fa
				x, y = pin.pos().toTuple()
				new_x, new_y = mirrorer(x, y)

				pin.setPos(new_x, new_y)

		self.updateShape()
		self.PropertyChanged()
	
	def flip(self):
		self.facing = Facing(self.facing+2)
		self.isMirrored = not self.isMirrored

		w, h = self.getAbsSize()

		if self.facing%2 == 0:
			flipper = lambda x, y: (w*GRID.SIZE-x, y)    # Horizontal
		else:
			flipper = lambda x, y: (x, h*GRID.SIZE-y)    # Vertical
		
		for edge, pinlist in self._pinslist.items():
			fa = self.edgeToFacing(edge)
			for pin in pinlist:
				pin.facing = fa
				x, y = pin.pos().toTuple()
				new_x, new_y = flipper(x, y)

				pin.setPos(new_x, new_y)
		
		self.updateShape()
		self.PropertyChanged()
	
	def rotate(self, clockwise: bool = True):
		self.setFacing(Facing(self.facing + (1 if clockwise else 3)))
	
	def edgeToFacing(self, edge: CompEdge) -> Facing:
		return Facing(self.facing + (-edge if self.isMirrored else edge))
	
	def facingToEdge(self, facing: Facing) -> CompEdge:
		return CompEdge((facing - self.facing) * (-1 if self.isMirrored else 1))


	### Pin Configuration
	def addInputPin(self, edge: CompEdge, index: int) -> InputPinItem:
		"""Call updateShape() afterwards if needed"""
		pinslist = self._pinslist[edge]

		fa, gen = self.getPinPosGenerator(edge)
		newpin = InputPinItem(self, gen(index), fa)
		pinslist.append(newpin)
		return newpin
	
	def addOutputPin(self, edge: CompEdge, index: int) -> OutputPinItem:
		"""Call updateShape() afterwards if needed"""
		pinslist = self._pinslist[edge]

		fa, gen = self.getPinPosGenerator(edge)
		newpin = OutputPinItem(self, gen(index), fa)
		pinslist.append(newpin)
		return newpin
	
	def removePin(self, edge: CompEdge, index: int):
		"""Call `updateShape()` afterwards if needed"""
		pinlist = self._pinslist[edge]
		pin = pinlist[index]
		pin.disconnect()
		
		pinlist.pop(index)
		pin.setParentItem(None)  # pyright: ignore[reportArgumentType]
		self.cscene.removeItem(pin)

	def getPinPosGenerator(self, edge: CompEdge) -> tuple[Facing, Callable[[int], QPointF]]:
		"""Set `facing` and `size` before calling"""
		# This was way too complicated then expected
		w, h = self.getAbsSize()
		M = self.isMirrored

		# Final Facing (fa)
		# A, B, C, D => E, S, W, N
		# A* = Edge facing East COUNTER-CLOCKWISE
		fa = Facing(self.facing + (-edge if M else edge))

		# Final Direction (fd): (False -> Clockwise), (True -> Counter-Clockwise)
		fd = M ^ (edge in (1, 2))
		# print((["A", "B", "C", "D", "A*", "B*", "C*", "D*"])[fa + (4 if fd else 0)])
		match fa + (4 if fd else 0):
			case 0: return ( fa, lambda i: QPointF(w  , i  ) * GRID.SIZE )    # A
			case 1: return ( fa, lambda i: QPointF(w-i, h  ) * GRID.SIZE )    # B
			case 2: return ( fa, lambda i: QPointF(0  , h-i) * GRID.SIZE )    # C
			case 3: return ( fa, lambda i: QPointF(i  , 0  ) * GRID.SIZE )    # D
			case 4: return ( fa, lambda i: QPointF(w  , h-i) * GRID.SIZE )    # A*
			case 5: return ( fa, lambda i: QPointF(i  , h  ) * GRID.SIZE )    # B*
			case 6: return ( fa, lambda i: QPointF(0  , i  ) * GRID.SIZE )    # C*
			case _: return ( fa, lambda i: QPointF(w-i, 0  ) * GRID.SIZE )    # D*

	def setPinPos(self, pin: PinItem, placement: QPointF):
		"""Set `pin.facing` before calling"""
		pin.setPos(placement)
		if pin._wire: pin._wire.updateShape()
	
	def cutConnections(self):
		list_of_pinlists = self._pinslist.values()
		pins = [pin for pinlist in list_of_pinlists for pin in pinlist]    # Funniest line ever
		for p in pins:
			p.disconnect()
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		...    # ABSTRACT METHOD


	### Smart Hover System
	def proxyPin(self) -> InputPinItem|None:
		"""The getter function for the proxy pin. If the proxy pin is stored as an index, then dereference it here"""
		return None    # ABSTRACT METHOD (defaults to None)
	
	def hoverEnterEvent(self, event): self._updateHoverStatus(True);  return super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event): self._updateHoverStatus(False); return super().hoverLeaveEvent(event)
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem|None = None):
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
	def betterHoverEnter(self):
		...    # ABSTRACT METHOD
	def betterHoverLeave(self):
		...    # ABSTRACT METHOD
	
	
	### Updating Overall Shape
	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
		# This part changes the bounding rect and "shape" of the compItem
		# For when you're changing number of pins. Edges without any pins will not have any "hitbox"
		self._rect = self.getRect()

		girth = GRID.SIZE
		hitbox_rect = self._rect.adjusted(
			-girth if len(self._pinslist[self.facingToEdge(Facing.WEST)])  > 0 else 0,
			-girth if len(self._pinslist[self.facingToEdge(Facing.NORTH)]) > 0 else 0,
			+girth if len(self._pinslist[self.facingToEdge(Facing.EAST)])  > 0 else 0,
			+girth if len(self._pinslist[self.facingToEdge(Facing.SOUTH)]) > 0 else 0
		)
		
		path = QPainterPath()
		path.addRect(hitbox_rect)
		self._cached_hitbox = path
	
	def shape(self) -> QPainterPath:
		return self._cached_hitbox
	def boundingRect(self) -> QRectF:
		return self._cached_hitbox.boundingRect()


	### Dimension
	def getRect(self):
		w, h = self.getAbsSize()
		dx, dy = self.getAbsPadding()
		return QRectF(-dx, -dy, w*GRID.SIZE + 2*dx, h*GRID.SIZE + 2*dy)

	def getRelSize(self) -> tuple[int, int]:
		"""Calculates relative size in GRID units regardless of facing: `(length, breadth)`"""
		...    # ABSTRACTE METHOD
	
	def getRelPadding(self) -> tuple[float, float]:
		"""Calculates relative padding regardless of facing: `(length, breadth)`"""
		...    # ABSTRACTE METHOD
	
	def getAbsSize(self) -> tuple[int, int]:
		"""Calculates absolute size in GRID units: `(width, height)`"""
		a, b = self.getRelSize()
		if self.facing%2 == 0: return (a, b)
		else:                  return (b, a)
	
	def getAbsPadding(self) -> tuple[float, float]:
		"""Calculates absolute padding: `(width, height)`"""
		a, b = self.getRelPadding()
		if self.facing%2 == 0: return (a, b)
		else:                  return (b, a)


	### Events
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemPositionChange:
			return GRID.snapF(value)

		return super().itemChange(change, value)
	
	def updateShape(self):
		"""No need to call `setHitbox()` afterwards"""
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	
	def draw(self, painter, option, widget):
		...    # ABSTRACT METHOD
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False


		if option.state & QStyle.StateFlag.State_Selected:
			painter.setPen(QPen(Color.hl_text_bg, 2, Qt.PenStyle.DashLine))
		else:
			painter.setPen(QPen(Color.outline, 2))
		painter.setBrush(Color.comp_body)

		self.draw(painter, option, widget)
		painter.drawRect(self._rect)


		painter.setPen(Color.text)
		painter.setFont(Font.default)
		painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self.tag)
