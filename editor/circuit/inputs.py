from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Prop

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem





class InputItem(CompItem):
	TAG="IN"
	LOGIC=Const.VARIABLE_ID
	NAME=DESC="INPUT"
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF, **kwargs):
		super().__init__(pos, **kwargs)

		# Properties
		self.state: int = Const.LOW
		
		# Pins Setup
		if self._setupDefaultPins:
			self.addOutputPin(CompEdge.OUTPUT, 1)
			self.updateShape()
		
		# Pins Casting
		self.outputPin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][0])

		# Setting Pin logicals
		self.outputPin.setLogical(self._unit)

		# Final Setup
		self.setState(False)


	# Properties Data
	def getProperties(self) -> dict:
		return super().getProperties() | {
			Prop.STATE     : self.state
		}

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)
	
	def setState(self, state: bool):
		bookish = Const.HIGH if state else Const.LOW
		self.state = bookish
		logic.toggle(self._unit, bookish)
		self.update()

	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == MouseBtn.LeftButton:
			delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
			if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
				self.setState(not self.state)
			return super().mouseReleaseEvent(event)
	
	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		if self.state == Const.HIGH:
			painter.setBrush(Color.comp_on)
		else:
			painter.setBrush(Color.comp_body)