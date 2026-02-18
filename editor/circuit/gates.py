from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.Enums import CompEdge, EditorState

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem

from engine.Gates import Gate





### Gate Item
class GateItem(CompItem):
	def __init__(self, pos: QPointF):
		super().__init__(pos, QPoint(6, 4))
		
		# Behavior
		self.labelText = "GATE"
		self.labelItem.setPlainText(self.labelText)

		# Pins
		self.addPin(0, CompEdge.INPUT, InputPinItem)
		self.addPin(2, CompEdge.INPUT, InputPinItem)
		self.inputPins = cast(list[InputPinItem], self._pinslist[CompEdge.INPUT])
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.setHitbox()

		self.unit: Gate|None = None
		self.proxyIndex = 0    # Always the first unconnected pin or the peeking pin
		self.peekingPin: PinItem|None = None
		self.minInput = 2
		self.maxInput = 69

	
	def setUnit(self, unit: Gate):
		self.unit = unit
	def getUnit(self):
		return self.unit

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
				if left == 0: break
				pin = self.inputPins[i]

				# Only attempt to delete if not connected to a wire
				if not pin.hasWire():
					self.removePin(CompEdge.INPUT, i)
					left -= 1

					# Check the special "Proxy" constraint
					if i <= self.proxyIndex:
						self.proxyIndex = size + left
						break
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
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		if (activePinCountChange == +1) and pin is self.proxyPin():
			for i, p in enumerate(self.inputPins):
				if not p.hasWire():
					self.proxyIndex = i
					break
			else:
				self.proxyIndex = len(self.inputPins)
		
		if (activePinCountChange == -1) and pin in self.inputPins:
			index = self.inputPins.index(cast(InputPinItem, pin))
			self.proxyIndex = min(self.proxyIndex, index)

	# Events
	def updateShape(self):
		if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
	def paint(self, painter, option, widget):
		if self._dirty: self._updateShape(); self._dirty = False
		return super().paint(painter, option, widget)

	def _updateShape(self):
		"""DO NOT set _dirty to False before call this"""
		n = len(self.inputPins)
		w = 0
		if   n < 5:  w = 6
		elif n < 10: w = 8
		else:        w = 10
		h = 2*(n-1) if n > 3 else 4
		m = h//(n-1)
		self.setDimension(w, h)

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
	def __init__(self, pos: QPointF):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "NOT"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)

		# Pins
		self.inputPin = cast(InputPinItem, self.addPin(1, CompEdge.INPUT, InputPinItem))
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.setHitbox()

		# Properties
		self.minInput = 1
		self.maxInput = 1



class InputItem(CompItem):
	def __init__(self, pos: QPointF):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "IN"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)
		
		# Pins
		self.outputPin = cast(OutputPinItem, self.addPin(1, CompEdge.OUTPUT, OutputPinItem))
		self.setHitbox()

		# Properties
	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == MouseBtn.LeftButton:
			delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
			if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
				self.state = not self.state
				self.updateVisual()
			return super().mouseReleaseEvent(event)
	
	def updateVisual(self):
		self.setPen(QPen(Color.outline, 2))
		if self.state: self.setBrush(Color.comp_on)
		else:          self.setBrush(Color.comp_body)



class OutputItem(CompItem):
	def __init__(self, pos: QPointF):
		super().__init__(pos, QPoint(4, 2), QPointF(0, 4))
		
		# Behavior
		self.setAcceptHoverEvents(True)
		self.labelText = "OUT"
		self.labelItem.setPlainText(self.labelText)
		self.labelItem.setPos(5, -5)
		
		# Pins
		self.inputPin = cast(InputPinItem, self.addPin(1, CompEdge.INPUT, InputPinItem))
		self.setHitbox()

		# Properties
	

	def updateVisual(self):
		self.setPen(QPen(Color.outline, 2))
		if self.state: self.setBrush(Color.LED_on)
		else:          self.setBrush(Color.LED_off)