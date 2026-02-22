from __future__ import annotations
from typing import cast, TYPE_CHECKING
from core.QtCore import *
from core.Enums import Facing, EditorState
import core.grid as GRID

from editor.styles import Color

if TYPE_CHECKING:
	from .canvas import CircuitScene
	from .compitem import CompItem
	from .wireitem import WireItem

from engine import Const
from engine.Gates import Gate, InputPin, OutputPin





###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parentComp: CompItem|None, relpos: QPointF, facing: Facing):
		super().__init__(
			-GRID.SIZE, -GRID.SIZE,
			GRID.DSIZE, GRID.DSIZE,
			parentComp
		)
		self.setFlags(
			# GraphicsItemFlag.ItemIsSelectable |
			GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self.setPen(Qt.PenStyle.NoPen)
		self.setAcceptHoverEvents(True)
		self.setZValue(1)

		self.state: int = Const.LOW
		self._wire: WireItem|None = None
		self.isHighlighted = False
		self.proxyHighlight = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(relpos)
	
	@property
	def cscene(self):     return cast('CircuitScene', self.scene())
	@property
	def parentComp(self): return cast('CompItem', self.parentItem())
	
	def highlight(self, isHovered: bool) -> None:
		...    # ABSTRACT METHOD
	def disconnect(self):
		...    # ABSTRACT METHOD
	
	
	# Serialization
	def getData(self):
		return {
			"pos"     : self.pos().toTuple(),
			"wire"    : self.getWireID(),
			"isInput" : isinstance(self, InputPinItem)
		}

	# Wire configuration
	def setWire(self, wire: WireItem|None):
		"""Doesn't remove its reference from its wire. Use disconnect() then"""
		if self._wire is wire: return

		apcc = (1 if wire else 0) - (1 if self._wire else 0)
		self._wire = wire
		self.updateVisual()

		if self.parentComp:
			self.parentComp.pinUpdate(self, apcc)
	
	def getWire(self): return self._wire
	def hasWire(self): return self._wire != None
	def getWireID(self):
		if self._wire: return self._wire.getID()
		else:          return 0


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
			if self.state == Const.HIGH:
				self.setBrush(QBrush(Color.pin_on))
			else:
				self.setBrush(QBrush(Color.pin_off))





###======= INPUT PIN =======###
class InputPinItem(PinItem):
	def __init__(self, parent: CompItem|None, relpos: QPointF, facing: Facing):
		super().__init__(parent, relpos, facing)
		self.logical: tuple[Gate, int] | tuple[InputPin, int] | None = None

	def setLogical(self, input: Gate | InputPin, index: int = 0):
		if isinstance(input, InputPin):
			self.logical = (input, 0)
		else:
			self.logical = (input, index)

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





###======= OUTPUT PIN =======###
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: QPointF, facing: Facing):
		super().__init__(parent, relpos, facing)
		self.logical: Gate | OutputPin | None = None

	def setLogical(self, output: Gate | OutputPin):
		if not isinstance(input, (Gate, InputPin)):
			raise TypeError(f"Invalid logical value 'output' = {output}")
		self.logical = output
	
	def logicalStateChanged(self, state: int):
		self.state = state
		self.updateVisual()
		w = self._wire
		if w: w.setState(state)
	
	def disconnect(self):
		if not self._wire: return

		self.cscene.removeWire(self._wire)
	
	def highlight(self, isHovered: bool) -> None:
		self.isHighlighted = (
			(isHovered or self.proxyHighlight)
			and self.cscene.checkState(EditorState.NORMAL)
		)
		self.updateVisual()