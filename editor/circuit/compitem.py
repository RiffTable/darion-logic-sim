from __future__ import annotations
from typing import Callable, TYPE_CHECKING
from core.QtCore import *
from core.Enums import Facing, CompEdge
import core.grid as GRID

from editor.styles import Color, Font

if TYPE_CHECKING:
	from .canvas import CircuitScene
	from .pins import PinItem, InputPinItem, OutputPinItem





class LabelItem(QGraphicsTextItem):
	def __init__(self, text: str, parent: CompItem):
		super().__init__(text, parent)
		self.setFont(Font.default)
		


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
			GraphicsItemFlag.ItemIsMovable |
			GraphicsItemFlag.ItemIsSelectable |
			GraphicsItemFlag.ItemSendsGeometryChanges
			# GraphicsItemFlag.ItemSendsScenePositionChanges
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


	# Facing and Rotation
	def setFacing(self, facing: Facing):
		"""Don't forget to run updateShape() afterwards"""
		if facing == self.facing:
			return
		
		self.facing = facing
		self.updateOrientation()

	def rotate(self, clockwise: bool = True):
		"""Don't forget to run updateShape() afterwards"""
		self.setFacing(self.facing + (1 if clockwise else 3))
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
	
	def edgeToFacing(self, edge: CompEdge) -> Facing:
		mirrored = (edge%2 == 1) and self.isMirrored
		return Facing(edge + self.facing + (2 if mirrored else 0))

	def facingToEdge(self, facing: Facing) -> CompEdge:
		res = self.facing - facing
		mirrored = (res%2 == 1) and self.isMirrored
		
		return CompEdge(res + (2 if mirrored else 0))


	# Pin Configuration
	def addPin(self, index: int, edge: CompEdge, type: InputPinItem | OutputPinItem) -> InputPinItem | OutputPinItem:
		"""Don't forget to call updateShape() afterwards."""
		pinslist = self._pinslist[edge]

		fa, gen = self.getPinPosGenerator(edge)
		newpin = type(self, gen(index), fa)
		pinslist.append(newpin)
		return newpin

	def getPinPosGenerator(self, edge: CompEdge) -> tuple[Facing, Callable[[int], QPointF]]:
		"""Set `facing` and `size` before calling"""
		# This was way too complicated then expected
		w, h = self.getDimension()
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
			case 7: return ( fa, lambda i: QPointF(w-i, 0  ) * GRID.SIZE )    # D*

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