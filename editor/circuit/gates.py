from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Prop

from editor.styles import Color

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem





### Gate Item
class GateItem(CompItem):
	MIN_INPUT = 2
	MAX_INPUT = 69

	def getRelSize(self):
		n = len(self._pinslist[CompEdge.INPUT])
		if   n < 5:  w = 6
		elif n < 10: w = 8
		else:        w = 10

		h = 2*(n-1) if n > 3 else 4
		return (w, h)
	
	def getRelPadding(self): return (0, 9)


	def __init__(self, pos: QPointF, **kwargs):
		super().__init__(pos, **kwargs)

		# Properties
		self.minInput = self.MIN_INPUT
		self.maxInput = self.MAX_INPUT

		# Pins
		if self._setupDefaultPins:
			for i in range(self.minInput):
				self.addInPin(CompEdge.INPUT, 0)
			self.addOutPin(CompEdge.OUTPUT, 0)
			self.readjustPins()   # fuck
		
		self.inputPins = cast(list[InputPinItem], self._pinslist[CompEdge.INPUT])
		self.outputPin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][0])
		
		# Setting logicals for pins (Works for both regular constructor and deserialization)
		for i, p in enumerate(self.inputPins):
			p.setLogical(self._unit, i)
		self.outputPin.setLogical(self._unit)

		self.proxyIndex = self.findFirstEmptyPin()
		self.peekingPin: PinItem|None = None
	

	# Properties Data
	def getProperties(self) -> dict:
		return super().getProperties() | {
			Prop.INPUTSIZE : len(self.inputPins),
		}
	
	def setProperty(self, prop: Prop, value):
		if prop == Prop.INPUTSIZE:
			if self.setInputCount(value):
				self.PropertyChanged()
				return True
			else:
				return False
		else:
			return super().setProperty(prop, value)
	

	def unitStateChanged(self, state: int):
		self.state = state
		self.outputPin.logicalStateChanged(state)


	# Proxying
	def proxyPin(self):
		if self.proxyIndex < len(self.inputPins):
			return self.inputPins[self.proxyIndex]
		else: return None
	
	def findFirstEmptyPin(self):
		for i, p in enumerate(self.inputPins):
			if not p.hasWire():
				return i
		return len(self.inputPins)


	# Pin Configuration
	def pushGatePin(self):
		...
	def popGatePin(self):
		...
	
	def pinUpdate(self, pin: PinItem, activePinCountChange: int):
		if (activePinCountChange == +1) and pin is self.proxyPin():
			self.proxyIndex = self.findFirstEmptyPin()
		
		if (activePinCountChange == -1) and pin in self.inputPins:
			index = self.inputPins.index(cast(InputPinItem, pin))
			self.proxyIndex = min(self.proxyIndex, index)
	
	def setInputCount(self, size: int) -> bool:
		# This is never called for NOT gates
		n = len(self.inputPins)
		if size < self.minInput \
		or size > self.maxInput \
		or size == n:
			return False
		
		if size > n:
			for i in range(n, size):
				self.addInPin(CompEdge.INPUT, 0).setLogical(self._unit, i)    # fuck
		else:
			left = n - size

			for i in range(n-1, -1, -1):
				pin = self.inputPins[i]
				if left == 0 or pin.hasWire(): break

				self.removePin(CompEdge.INPUT, i)
				left -= 1
		
		logic.setlimits(self._unit, size)
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
			self.peekingPin = self.addInPin(CompEdge.INPUT, 0).setLogical(self._unit, self.proxyIndex)
			self.updateShape()
			# fuck
	
	def betterHoverLeave(self):
		# "Peek Off": Removes the "Peeking Pin" if it has been created
		if self.peekingPin and not self.peekingPin.hasWire():
			self.removePin(CompEdge.INPUT, self.proxyIndex)
			self.updateShape()
			# fuck
		self.peekingPin = None
	
	def _updateHoverStatus(self, hoverStatus: bool, hoveredPin: PinItem|None = None):
		super()._updateHoverStatus(hoverStatus, hoveredPin)
		
		# Enable proxyHighlight if only the gate is being hovered, not its pins
		proxy = self.proxyPin()
		if proxy:
			proxy.proxyHighlight = True if (self._hover_count == 1) else False
			proxy.highlight(proxy is hoveredPin)

	# Events
	def _updateShape(self):
		n = len(self.inputPins)
		_, h = self.getRelSize()
		fa, gen = self.getPinPosGenerator(CompEdge.INPUT)

		if n == 1:
			p = self.inputPins[0]
			p.facing = fa
			self.setPinPos(p, gen(h//2))
		else:
			m = h//(n-1)

			for i, p in enumerate(self.inputPins):
				p.facing = fa
				self.setPinPos(p, gen(m*i))
			
		opin = self.outputPin
		fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
		opin.facing = fa
		self.setPinPos(opin, gen(h//2))
		super()._updateShape()



class NOTGate  (GateItem):
	TAG = "NOT"
	LOGIC = Const.NOT_ID
	NAME = DESC = "NOT Gate"
	MIN_INPUT = MAX_INPUT = 1
	def getRelSize(self): return (4, 2)
	def getRelPadding(self): return (0, 4)
class ANDGate  (GateItem): TAG="AND";  LOGIC=Const.AND_ID;  NAME=DESC="AND Gate"
class NANDGate (GateItem): TAG="NAND"; LOGIC=Const.NAND_ID; NAME=DESC="NAND Gate"
class ORGate   (GateItem): TAG="OR";   LOGIC=Const.OR_ID;   NAME=DESC="OR Gate"
class NORGate  (GateItem): TAG="NOR";  LOGIC=Const.NOR_ID;  NAME=DESC="NOR Gate"
class XORGate  (GateItem): TAG="XOR";  LOGIC=Const.XOR_ID;  NAME=DESC="XOR Gate"
class XNORGate (GateItem): TAG="XNOR"; LOGIC=Const.XNOR_ID; NAME=DESC="XNOR Gate"