from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem





class OutputItem(CompItem):
	TAG="OUT"
	LOGIC=Const.OUTPUT_PIN_ID
	NAME=DESC="LED"
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF, **kwargs):
		super().__init__(pos, **kwargs)
		
		# Pins
		if self._setupDefaultPins:
			self.addInPin(CompEdge.INPUT, 0).setLogical(self._unit, 0)
			self.readjustPins()   # fuck
		
		self.inputPin = cast(InputPinItem, self._pinslist[CompEdge.INPUT][0])


	def unitStateChanged(self, state: int):
		self.state = state
		self.update()
	
	def proxyPin(self) -> InputPinItem | None:
		return None if self.inputPin.hasWire() else self.inputPin

	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		if self.state == Const.HIGH:
			painter.setBrush(Color.LED_on)
		else:
			painter.setBrush(Color.LED_off)