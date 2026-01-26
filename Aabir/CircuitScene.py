from __future__ import annotations
from typing import cast
from enum import IntEnum
from QtCore import *

from Items import CompItem, WireItem, OutputPinItem
from Enums import Facing, Rotation, EditorState





class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.SIZE = 12
		self.gates: list[CompItem] = []
		self.wires: list[WireItem] = []
		self.state = EditorState.NORMAL
		self.wireSource: OutputPinItem = None

	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y), QPoint(5, 4), QPointF(0, 3))
		self.addItem(comp)
		self.gates.append(comp)
