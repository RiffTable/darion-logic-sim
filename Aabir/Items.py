from __future__ import annotations
from typing import cast

from QtCore import *

from styles import (Color, Font)






class CompItem(QGraphicsRectItem):
	def __init__(self, x: float, y: float):
		super().__init__(x, y, 80, 50)
		
		self.state = False
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
		)
		self.updateVisual()
		self.setPen(QPen(Color.outline, 2))
		self.label = QGraphicsTextItem("=1", self)
		self.label.setFont(Font.default)
		# self.label.setDefaultTextColor(Color.text)
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
		else         : self.setBrush(Color.gate_off)





class WireItem(QGraphicsPathItem):
	def __init__(self, beg: CompItem, end: CompItem):
		super().__init__()