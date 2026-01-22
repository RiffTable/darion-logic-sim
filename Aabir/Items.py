from __future__ import annotations
from typing import cast
from enum import Enum
from QtCore import *

from styles import (Color, Font)





class Facing(Enum):
	North = 1
	East  = 2
	South = 3
	West  = 4





class CompItem(QGraphicsRectItem):
	def __init__(self, x: float, y: float):
		super().__init__(x, y, 80, 50)
		
		# Behavior
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
		)

		# Properties
		self.state = False
		self.facing = Facing.East
		self.tail = []
		self.head = []
		self.top = []
		self.bottom = []

		# Visual
		self.setPen(QPen(Color.outline, 2))
		self.setBrush(Color.gate)

		# Label
		self.label = QGraphicsTextItem("XOR", self)
		self.label.setFont(Font.default)
		self.label.setPos(x+5, y+5)


	def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
		if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
			return QPointF(*self.scene().snapToGrid(
				value.x(),
				value.y()
			))

		return super().itemChange(change, value)





class PinItem(QGraphicsEllipseItem):
	def __init__(self, parent: CompItem):
		r = 5
		super().__init__(-r, -r, 2*r, 2*r, parent)
		self.setAcceptHoverEvents(True)

		self.state = False
		self.hovering = False
		self.label = ""

		self.setPen(QPen(Color.outline, 1))
		self.updateVisual()
		# self.setPos(80 if is_output else 0, 25)
	
	def updateVisual(self):
		if self.state:      self.setBrush(QBrush(Color.signal_on))
		elif self.hovering: self.setBrush(QBrush(Color.pin_hover))
		else:               self.setBrush(QBrush(Color.signal_off))
	
	def hoverEnterEvent(self, event):
		self.hovering = True
		self.updateVisual()
		super().hoverEnterEvent(event)

	def hoverLeaveEvent(self, event):
		self.hovering = False
		self.updateVisual()
		super().hoverLeaveEvent(event)





class WireItem(QGraphicsPathItem):
	def __init__(self, beg: CompItem, end: CompItem):
		super().__init__()
	
	def updateVisual(self):
		...