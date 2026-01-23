from __future__ import annotations
from typing import cast

from QtCore import *

from Items import CompItem, WireItem



class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.SIZE = 20
		self.gates: list[CompItem] = []
		self.wires: list[WireItem] = []

	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y), QPoint(5, 4), QPointF(0, 5))
		self.addItem(comp)
		self.gates.append(comp)

	def snapToGrid(self, x: float, y:float) -> tuple[int, int]:
		return (
			round(x/self.SIZE)*self.SIZE,
			round(y/self.SIZE)*self.SIZE
		)