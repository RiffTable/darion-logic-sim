from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, Prop

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

		# Properties
		self.state: int = Const.LOW
		self.peeking_disabled = False
		
		# Pins Setup
		if self._setupDefaultPins:
			self.addInputPin(CompEdge.INPUT, 1)
			self.updateShape()
		
		# Pins Casting
		self.inputPin = cast(InputPinItem, self._pinslist[CompEdge.INPUT][0])

		# Setting Pin Logicals
		self.inputPin.setLogical(self._unit, 0)


	# Properties Data
	def getProperties(self) -> dict:
		return super().getProperties() | {
			Prop.STATE     : self.state
		}


	def unitStateChanged(self, state: int):
		self.state = state
		self.update()
	
	def proxyPin(self) -> InputPinItem | None:
		# Don't show proxy pin if peeking is disabled
		if self.peeking_disabled:
			return None
		return None if self.inputPin.hasWire() else self.inputPin

	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		match self.state:
			case Const.HIGH:  painter.setBrush(QBrush(self.colors.LED_on))
			case Const.ERROR: painter.setBrush(QBrush(self.colors.LED_error))
			case _:           painter.setBrush(QBrush(self.colors.LED_off))