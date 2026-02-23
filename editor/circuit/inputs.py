from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.Enums import CompEdge, EditorState

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem


from engine import Const





class InputItem(CompItem):
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF, **kwargs):
		super().__init__(pos, **kwargs)
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.tag = "IN"
		
		if self._setupDefaultPins:
			self.addOutPin(CompEdge.OUTPUT, 0)
		self.outputPin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][0])
		
		self.readjustPins()   # fuck
	

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)
	

	def setState(self, state: int):
		self.state = state
		self.update()

	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == MouseBtn.LeftButton:
			delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
			if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
				self.setState(Const.HIGH if self.state == Const.LOW else Const.LOW)
			return super().mouseReleaseEvent(event)
	
	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		if self.state == Const.HIGH:
			painter.setBrush(Color.comp_on)
		else:
			painter.setBrush(Color.comp_body)