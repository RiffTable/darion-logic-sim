from __future__ import annotations
from typing import cast, TYPE_CHECKING
from core.QtCore import *
from core.LogicCore import *

from editor.styles import Color

if TYPE_CHECKING:
	from .canvas import CircuitScene
	from .pins import InputPinItem, OutputPinItem





class WireItem(QGraphicsPathItem):
	_COUNT = 1    # NO CONNECTION = ZERO (0)
	MINWALK = 2
	def __init__(self, beg: OutputPinItem, end: InputPinItem):
		super().__init__()

		# Behavior
		self.setFlags(GraphicsItemFlag.ItemIsSelectable)
		self.setZValue(-1)
		self._dirty = False

		beg.setWire(self)
		end.setWire(self)

		# Properties
		self._id = WireItem._COUNT
		self.state: int = Const.LOW
		self.source = beg
		self.supplies: list[InputPinItem] = [end]

		self.logicalConnect(beg, end)

		self._updateShape()

		WireItem._COUNT += 1
	
	@property
	def cscene(self): return cast('CircuitScene', self.scene())
	def getID(self):
		return self._id

	
	## Properties Data
	def getData(self):
		return {}


	# Connection configuration
	@classmethod
	def logicalConnect(cls, outpin: OutputPinItem, inpin: InputPinItem):
		if inpin.logical and outpin.logical:
			u, i = inpin.logical
			logic.connect(u, outpin.logical, i)
	
	def addSupply(self, pin: InputPinItem):
		if pin in self.supplies: return
		self.supplies.append(pin)
		pin.setWire(self)

		self.logicalConnect(self.source, pin)
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
			if supply.logical: logic.disconnect(*supply.logical)
			supply.setWire(None)
	
	# Events
	def setState(self, state: int):
		self.state = state
		self.updateVisual()
	
	def updateVisual(self):
		match self.state:
			case Const.HIGH: self.setPen(QPen(Color.signal_on, 3))
			case _:          self.setPen(QPen(Color.signal_off, 3))
		# if self.isSelected(): color = QColor("#f39c12")
	
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
		self.updateVisual()

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