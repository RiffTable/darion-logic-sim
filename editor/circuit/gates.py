from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.Enums import CompEdge, EditorState

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem


from engine import Const





### Gate Item
class GateItem(CompItem):
	def getRelSize(self):
		n = len(self._pinslist[CompEdge.INPUT])
		if   n < 5:  w = 6
		elif n < 10: w = 8
		else:        w = 10

		h = 2*(n-1) if n > 3 else 4
		return (w, h)
	
	def getRelPadding(self): return (0, 9)
	def __init__(self, pos: QPointF):
		super().__init__(pos)
		
		# Behavior
		self.tag = "GATE"

		# Pins
		self.addPin(0, CompEdge.INPUT, InputPinItem)
		self.addPin(2, CompEdge.INPUT, InputPinItem)
		self.inputPins = cast(list[InputPinItem], self._pinslist[CompEdge.INPUT])
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.updateShape()

		self.proxyIndex = self.findFirstEmptyPin()
		self.peekingPin: PinItem|None = None

		# Properties
		self.minInput = 2
		self.maxInput = 69


	### Properties Data
	def getData(self):
		return super().getData() | {
			"maxInput" : self.maxInput,
			"minInput" : self.minInput,
		}
	

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)


	# Proxying
	def proxyPin(self):
		if self.proxyIndex < len(self.inputPins):
			return self.inputPins[self.proxyIndex]
		else: return None
	
	def setInputCount(self, size: int) -> bool:
		if size > self.maxInput or size < self.minInput:
			return False
		n = len(self.inputPins)
		if size >= n:
			for _ in range(size-n):
				self.addPin(0, CompEdge.INPUT, InputPinItem)
		else:
			left = n - size

			for i in range(n-1, -1, -1):
				pin = self.inputPins[i]
				if left == 0 or pin.hasWire(): break

				self.removePin(CompEdge.INPUT, i)
				left -= 1
			
		self.updateShape()
		return True

	# Input feedback
	# All events regarding "pin peeking":
	# 1. Peek Out (betterHoverEnter)
	# 2. Peek Off (betterHoverLeave)
	# 3. Default/Proxy Connection

	# Smart Hover + Proxy System
	def betterHoverEnter(self):
		# "Peek Out": Peeks out the "Peeking Pin"
		if self.proxyIndex == len(self.inputPins) \
		and len(self.inputPins) < self.maxInput \
		and self.cscene.checkState(EditorState.WIRING):
			self.peekingPin = self.addPin(0, CompEdge.INPUT, InputPinItem)
			self.updateShape()
	
	def betterHoverLeave(self):
		# "Peek Off": Removes the "Peeking Pin" if it has been created
		if self.peekingPin and not self.peekingPin.hasWire():
			self.removePin(CompEdge.INPUT, self.proxyIndex)
			self.updateShape()
		self.peekingPin = None
	
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem|None = None):
		super()._updateHoverStatus(hoverStatus, hoveredPin)
		
		# Enable proxyHighlight if only the gate is being hovered, not its pins
		proxy = self.proxyPin()
		if proxy:
			proxy.proxyHighlight = True if (self._hover_count == 1) else False
			proxy.highlight(proxy is hoveredPin)
	
	def findFirstEmptyPin(self):
		for i, p in enumerate(self.inputPins):
			if not p.hasWire():
				return i
		return len(self.inputPins)
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		if (activePinCountChange == +1) and pin is self.proxyPin():
			self.proxyIndex = self.findFirstEmptyPin()
		
		if (activePinCountChange == -1) and pin in self.inputPins:
			index = self.inputPins.index(cast(InputPinItem, pin))
			self.proxyIndex = min(self.proxyIndex, index)

	# Events
	def _updateShape(self):
		n = len(self.inputPins)
		_, h = self.getRelSize()
		m = h//(n-1)

		fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
		for i, p in enumerate(self.inputPins):
			p.facing = fa
			self.setPinPos(p, gen(m*i))
		
		opin = self.outputPin
		fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
		opin.facing = fa
		self.setPinPos(opin, gen(h//2))
		super()._updateShape()



### Gate Item
class UnaryGateItem(CompItem):
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF):
		super().__init__(pos)
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.tag = "NOT"

		# Pins
		self.inputPin = cast(InputPinItem, self.addPin(1, CompEdge.INPUT, InputPinItem))
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.updateShape()

		# Properties
		self.minInput = 1
		self.maxInput = 1
	

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)




class InputItem(CompItem):
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF):
		super().__init__(pos)
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.tag = "IN"
		
		# Pins
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.updateShape()
	

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)
	

	def setState(self, state: int):
		self.state = state

	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == MouseBtn.LeftButton:
			delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
			if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
				self.setState(Const.HIGH if self.state == Const.LOW else Const.HIGH)
			return super().mouseReleaseEvent(event)
	
	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		if self.state == Const.HIGH:
			painter.setBrush(Color.comp_on)
		else:
			painter.setBrush(Color.comp_body)



class OutputItem(CompItem):
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
	def __init__(self, pos: QPointF):
		super().__init__(pos)
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.tag = "OUT"
		
		# Pins
		self.inputPin = cast(InputPinItem, self.addPin(1, CompEdge.INPUT, InputPinItem))
		self.updateShape()
	

	def unitStateChanged(self, state: int):
		self.state = state
	

	def draw(self, painter, option, widget):
		# painter.setPen(QPen(Color.outline, 2))
		if self.state == Const.HIGH:
			painter.setBrush(Color.LED_on)
		else:
			painter.setBrush(Color.LED_off)