from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Prop
from editor import theme

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
		self.state: int = kwargs.get("state", Const.LOW)
		self.prevState = -1
		
		# Pins Setup
		if self._setupDefaultPins:
			self.addOutputPin(CompEdge.OUTPUT, 1)
			self.updateShape()
		
		# Pins Casting
		self.outputPin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][0])

		# Setting Pin logicals
		self.outputPin.setLogical(self._unit)
		self.outputPin.logicalStateChanged(self.state)

		# Final Setup
		self.setState(True if self.state == Const.HIGH else False)


	# Properties Data
	def getData(self):
		return super().getData() | {
			"state"      : self.state,
		}
	
	def getProperties(self) -> dict:
		dic = super().getProperties() | {
			Prop.LABEL   : self.tag,
			Prop.STATE   : self.state
		}
		dic.pop(Prop.TAG)
		return dic

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)
		self.propertyChanged()
	
	def poll_update(self) -> bool:
		if self._unit is None: return False
		
		current = self._unit.output
		if self.prevState != current:
			self.prevState = current
			self.unitStateChanged(current)
			return True
		return False
	
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
		Color = theme.get_theme()
		if self.state == Const.HIGH:
			painter.setBrush(Color.comp_active)
		else:
			painter.setBrush(Color.comp_body)