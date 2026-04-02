from __future__ import annotations
from typing import Self, cast, TYPE_CHECKING
from core.QtCore import *
from core.LogicCore import *
from core.Enums import Facing, EditorState
import core.grid as GRID

import editor.theme as theme

if TYPE_CHECKING:
	from .canvas import CircuitScene
	from .compitem import CompItem
	from .wireitem import WireItem





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
		self.setZValue(1)

		self.state: int = Const.UNKNOWN
		self._wire: WireItem|None = None
		self.isHighlighted = False
		self.viaProxy = False
		self.facing = facing
		self.label = ""

		# Color animation – prevents strobe on fast oscillators
		self.current_color: QColor = QColor(0, 0, 0, 0)
		self.color_anim = QVariantAnimation()
		self.color_anim.setDuration(100)
		self.color_anim.valueChanged.connect(self._on_color_change)

		self.setPos(relpos)
		theme.theme_changed.connect(self.updateVisual)
	
	@property
	def cscene(self):     return cast('CircuitScene', self.scene())
	@property
	def parentComp(self): return cast('CompItem', self.parentItem())
	
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
	def hasWire(self): return self._wire is not None
	def getWireID(self):
		if self._wire: return self._wire.getID()
		else:          return 0


	# Events
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			if self._wire: self._wire.updateShape()
		
		return super().itemChange(change, value)
	
	# Making pins unselectable so grabbing the pins don't grab the comps
	def mousePressEvent(self, event):
		super().mousePressEvent(event)
		self.setSelected(False); event.accept()
	def mouseMoveEvent(self, event): event.accept()


	def highlight(self, isHovered: bool, proxy: bool = False) -> None:
		self.isHighlighted = isHovered
		self.viaProxy = (isHovered and proxy)
		self.updateVisual()
	
	def paint(self, painter: QPainter, option, widget):
		# The HITBOX of the pin is larger (half of SIZE) than the visible radius
		r = 5

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))
	
	# Animation callback
	def _on_color_change(self, color: QColor):
		self.current_color = color
		self.setBrush(QBrush(color))
		self.update()

	def updateVisual(self):
		Color = theme.get_theme()
		if self.isHighlighted:
			if self.viaProxy: target_color = Color.pin_hoverproxy
			else:             target_color = Color.pin_hover
		
		elif self._wire:
			target_color = QColor(0, 0, 0, 0)  # transparent
		
		else:
			match self.state:
				case Const.HIGH:  target_color = Color.pin_high
				case Const.LOW:   target_color = Color.pin_low
				case Const.ERROR: target_color = Color.signal_error
				case _:           target_color = Color.signal_unknown

		if self.color_anim.endValue() != target_color:
			self.color_anim.stop()
			self.color_anim.setStartValue(self.current_color)
			self.color_anim.setEndValue(target_color)
			self.color_anim.start()





###======= INPUT PIN =======###
class InputPinItem(PinItem):
	def __init__(self, parent: CompItem|None, relpos: QPointF, facing: Facing):
		super().__init__(parent, relpos, facing)
		self.logical: tuple[Gate, int] | None = None
		self.state = Const.LOW
		self.updateVisual()

	def setLogical(self, input: Gate, index: int = 0) -> Self:
		# It's a builder function
		if input.id==Const.INPUT_PIN_ID:
			self.logical = (input, 0)
		else:
			self.logical = (input, index)
		return self

	def disconnect(self):
		if self._wire: self._wire.cutSupply(self)





###======= OUTPUT PIN =======###
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: QPointF, facing: Facing):
		super().__init__(parent, relpos, facing)
		self.logical: Gate | None = None
		self.updateVisual()

	def setLogical(self, output: Gate):
		self.logical = output
		return self
	
	def logicalStateChanged(self, state: int):
		self.state = state
		if self._wire:
			self._wire.updateShape()
		else:
			self.updateVisual()
	
	def disconnect(self):
		if self._wire: self.cscene.removeWire(self._wire)