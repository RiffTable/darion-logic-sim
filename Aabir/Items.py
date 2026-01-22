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
		self.updateVisual()

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
	
	def updateVisual(self):
		if self.state: self.setBrush(Color.gate_on)
		else:          self.setBrush(Color.gate_off)


class PortItem(QGraphicsEllipseItem):
    def __init__(self, parent, is_output=True):
        super().__init__(-5, -5, 10, 10, parent)
        self.is_output = is_output
        self.setBrush(QBrush(QColor("#34495e") if not is_output else "#3498db"))
        self.setPen(QPen(Qt.white, 1))
        self.setPos(80 if is_output else 0, 25)




class WireItem(QGraphicsPathItem):
	def __init__(self, beg: CompItem, end: CompItem):
		super().__init__()