from __future__ import annotations
from typing import Callable, cast, TYPE_CHECKING
from core.QtCore import *
from core.Enums import Facing, CompEdge
import core.grid as GRID

from editor.styles import Color, Font

if TYPE_CHECKING:
	from .canvas import CircuitScene
	from .pins import PinItem, InputPinItem, OutputPinItem

from engine.Gates import Gate





class CompItem(QGraphicsItem):
	def __init__(
			self,
			pos: QPointF
		):
		
		# Properties
		self.tag = "COMP"
		self.state = False
		self.facing = Facing.EAST
		self.isMirrored = False

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

		x, y = GRID.snapF(pos).toTuple()
		super().__init__()
		
		# Behavior
		self.setPos(x, y)
		self.setZValue(0)
		self.setFlags(
			GraphicsItemFlag.ItemIsMovable |
			GraphicsItemFlag.ItemIsSelectable |
			GraphicsItemFlag.ItemSendsGeometryChanges
			# GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self.setAcceptHoverEvents(True)
		self._dirty = True
		self._rect = self.getRect()
		self._cached_hitbox = QPainterPath()
		self._cached_hitbox.addRect(self._rect)
		self._hover_count = 0
		self._unit: Gate|None = None

		# Proxy & Hovering
		self.hoverLeaveTimer = QTimer()
		self.hoverLeaveTimer.setSingleShot(True)
		self.hoverLeaveTimer.timeout.connect(self.betterHoverLeave)
		self.hoverLeaveTimer.setInterval(30)

		self.updateShape()
	

	@property
	def cscene(self): return cast('CircuitScene', self.scene())

	def setUnit(self, unit: Gate):
		self._unit = unit
	def getUnit(self):
		return self._unit

	
	### Properties Data
	def getData(self):
		return {
			"pos"      : self.pos().toTuple(),
			"tag"      : self.tag,
			"facing"   : self.facing.value,
			"mirror"   : self.isMirrored,
			"pinslist" : {
				edge.value: [p.getData() for p in pins]
				for edge, pins in self._pinslist.items()
			}
		}


	### Facing and Rotation
	def setFacing(self, facing: Facing):
		if facing == self.facing:
			return
		
		self.facing = facing
		self.updateOrientation()

	def rotate(self, clockwise: bool = True):
		self.setFacing(Facing(self.facing + (1 if clockwise else 3)))
	def mirror(self):
		self.isMirrored = not self.isMirrored
		self.updateOrientation()
	def flip(self):
		self.isMirrored = not self.isMirrored
		self.setFacing(Facing(self.facing+2))
	
	def updateOrientation(self):
		# print("---------------")
		for edge, pins in self._pinslist.items():
			# print(f"Edge {edge} facing to ", end="")
			fa, gen = self.getPinPosGenerator(edge)
			for i, pin in enumerate(pins):
				pin.facing = fa
				self.setPinPos(pin, gen(i))
		self.updateShape()
	
	def edgeToFacing(self, edge: CompEdge) -> Facing:
		mirrored = (edge%2 == 1) and self.isMirrored
		return Facing(edge + self.facing + (2 if mirrored else 0))

	def facingToEdge(self, facing: Facing) -> CompEdge:
		res = self.facing - facing
		mirrored = (res%2 == 1) and self.isMirrored
		
		return CompEdge(res + (2 if mirrored else 0))


	### Pin Configuration
	def addPin(self, index: int, edge: CompEdge, type: type[InputPinItem] | type[OutputPinItem]) -> InputPinItem | OutputPinItem:
		"""Don't forget to call updateShape() afterwards."""
		pinslist = self._pinslist[edge]

		fa, gen = self.getPinPosGenerator(edge)
		newpin = type(self, gen(index), fa)
		pinslist.append(newpin)
		return newpin

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
		pin.setParentItem(None)  # pyright: ignore[reportArgumentType]
		self.cscene.removeItem(pin)
	
	def cutConnections(self):
		for p in self.allPins():
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
	
	
	### Shape Updating
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
