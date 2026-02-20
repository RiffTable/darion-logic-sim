from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.Enums import Facing, EditorState
import core.grid as GRID

from .catalog import (
	LOOKUP, CompItem, LabelItem, WireItem, InputPinItem, OutputPinItem,
	GateItem
)

from engine.Circuit import Circuit
from engine.Gates import Gate, InputPin, OutputPin






class CircuitScene(QGraphicsScene):
	def __init__(self, logic: Circuit):
		super().__init__()

		self.logic = logic
		self.comps: list[CompItem] = []
		self.wires: list[WireItem] = []

		self._rmb_last_pos = QPointF()

		# Clipboard
		self.clipboard = { "comps": [], "wires": [] }

		# Editor Stuffs
		self._state = EditorState.NORMAL
		self.defaultFacing = Facing.EAST
		self.defaultMirror = False

		# Wiring logic
		self.ghostWire: WireItem|None = None
		self.ghostPin = InputPinItem(None, QPointF(), Facing.WEST)

		self.ghostPin.hide()    # These three lines does the same thing but still...
		self.ghostPin.setEnabled(False)    # You can never be too sure
		self.ghostPin.setAcceptedMouseButtons(MouseBtn.NoButton)

		self.addItem(self.ghostPin)


	# Editor State Management
	def checkState(self, st: EditorState) -> bool:
		return self.getState() == st
	
	def getState(self):
		return self._state
		# if self.ghostWire: return EditorState.WIRING
		# return EditorState.NORMAL
	
	def setState(self, st: EditorState):
		self._state = st
		...
	
	def skipWiring(self):
		self.setState(EditorState.NORMAL)
		gwire = self.ghostWire
		self.ghostWire = None
		if gwire:
			if len(gwire.supplies) == 1:
				gwire._disconnect()
				self.removeItem(gwire)
			else:
				gwire.supplies.remove(self.ghostPin)
				self.ghostPin.setWire(None)
				gwire.updateShape()


	# Components Management
	def addComp(self, x: float, y:float, comp_id: int):
		cd = LOOKUP[comp_id]
		comp = cd.skin(QPointF(x, y))
		comp.labelItem.setPlainText(cd.tag)
		# horse-egg
		# self.logic.getcomponent(cd.logic, )
		
		self.addItem(comp)
		self.comps.append(comp)
		# run_logic()
	
	def removeComp(self, comp: CompItem):
		if comp not in self.comps: return
		comp.cutConnections()

		self.comps.remove(comp)
		self.removeItem(comp)
		# run_logic()
	
	# Wires	Management
	def finishWiring(self, target: QGraphicsItem|None, multiWireMode: bool):
		g_wire = self.ghostWire

		if g_wire == None:
			self.setState(EditorState.NORMAL)
			return
		g_pin = self.ghostPin
		source = g_wire.source
		finishing = False

		# Wiring: Finish!
		if isinstance(target, CompItem):
			# Proxying: Wire is connected to the gate's *favorite* pin
			target = target.proxyPin()
			if target is None: return
		
		if isinstance(target, InputPinItem):
			t_wire = target.getWire()
			if t_wire:
				# Swap Connections
				g_wire.supplies.remove(g_pin); g_wire.supplies.append(target)
				t_wire.supplies.append(g_pin); t_wire.supplies.remove(target)
				
				g_pin.setWire(t_wire);  g_wire.updateShape()
				target.setWire(g_wire); t_wire.updateShape()
				self.ghostWire = t_wire
				
				if len(g_wire.supplies) == 1: self.wires.append(g_wire)
				finishing = False
			else:
				finishing = True
		
		if finishing:
			target = cast(InputPinItem, target)
			if len(g_wire.supplies) == 1: self.wires.append(g_wire)

			if not multiWireMode:
				g_wire.supplies.remove(g_pin);  g_pin.setWire(None)
				self.setState(EditorState.NORMAL)
				self.ghostWire = None
			self.clearSelection()
			g_wire.setSelected(True)    # Solo select the finished wire
			
			g_wire.supplies.append(target); target.setWire(g_wire)

			# horse-egg
			# g, idx = target.logical
			# if isinstance(g, Gate) and idx < g.inputlimit:
			# 	g.setlimits(idx)
			# self.logic.connect(g, source.logical, idx)

			g_wire.updateShape()
			target.highlight(False)
			
			# wire.setFlag(QGraphicsItem.ItemIsSelectable, True)
			# self.clearSelection()
			# wire.setSelected(True)  # Solo select the finished wire
			# self.run_logic()

	def removeWire(self, wire: WireItem):
		# Works for both ghost wires and regular wires
		if (wire not in self.wires) and wire is self.ghostWire:
			return
		
		wire._disconnect()

		if not (wire is self.ghostWire): self.wires.remove(wire)
		self.removeItem(wire)
		# run_logic()

	###======= MOUSE/KEY EVENTS =======###
	def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
		item = self.itemAt(event.scenePos(), QTransform())

		# Wiring: Start!
		if self.checkState(EditorState.NORMAL):
			if isinstance(item, OutputPinItem) and event.button() == MouseBtn.LeftButton:
				if event.button() == MouseBtn.LeftButton:
					self.setState(EditorState.WIRING)
					w = item.getWire()
					if w == None:
						self.ghostWire = WireItem(item, self.ghostPin)
						# self.ghostWire.setFlag(QGraphicsItem.ItemIsSelectable, False)
						self.addItem(self.ghostWire)
					else:
						self.ghostWire = w
						self.ghostWire.addSupply(self.ghostPin)
		
		return super().mousePressEvent(event)

	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		# This event only takes place after the CircuitView handles its!
		# RMB drag has been handled
		btn = event.button()
		target = self.itemAt(event.scenePos(), QTransform())
		if isinstance(target, LabelItem): target = target.parentItem()

		if self.checkState(EditorState.WIRING):
			# Wiring: Finish?
			if btn == MouseBtn.LeftButton:
				self.finishWiring(
					target,
					bool(event.modifiers() & KeyMod.ShiftModifier)
				)

			# Wiring: Skip!
			if btn == MouseBtn.RightButton:   # RMB click
				self.skipWiring()
				event.accept()
				return
		
		super().mouseReleaseEvent(event)

	def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
		self.ghostPin.setPos(GRID.snapF(event.scenePos()))
		return super().mouseMoveEvent(event)
	
	def keyPressEvent(self, event: QKeyEvent):
		key = event.key()
		mod = event.modifiers()

		if key in (Key.Key_Delete, Key.Key_Backspace, Key.Key_X):
			for item in self.selectedItems():
				if isinstance(item, WireItem):
					if item in self.wires: self.removeWire(item)
				
				elif isinstance(item, CompItem):
					if item in self.comps: self.removeComp(item)
			
			# self.run_logic()
		
		if self.checkState(EditorState.WIRING) and (event.key() == Key.Key_Escape):
			self.skipWiring()
		
		if key in (Key.Key_Plus, Key.Key_Equal, Key.Key_Minus, Key.Key_Underscore):
			for item in self.selectedItems():
				if isinstance(item, GateItem):
					is_plus = event.key() in (Key.Key_Plus, Key.Key_Equal)
					new_size = len(item.inputPins) + (1 if is_plus else -1)
					item.setInputCount(new_size)
					u = item.getUnit()
					if u: self.logic.setlimits(u, new_size)
		
		# if key == Key.Key_M:
		# 	for item in self.selectedItems():
		# 		if isinstance(item, CompItem):
		# 			item.mirror()
		# 			item.updateShape()
		
		if key == Key.Key_F:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.flip()
					item.updateShape()
		
		if key == Key.Key_R:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					item.rotate(not mod & KeyMod.ShiftModifier)
					item.updateShape()
		
		if key in (Key.Key_Right, Key.Key_Down, Key.Key_Left, Key.Key_Up) \
		and mod & KeyMod.ControlModifier:
			for item in self.selectedItems():
				if isinstance(item, CompItem):
					match key:
						case Key.Key_Right: item.setFacing(Facing.EAST)
						case Key.Key_Down:  item.setFacing(Facing.SOUTH)
						case Key.Key_Left:  item.setFacing(Facing.WEST)
						case Key.Key_Up:    item.setFacing(Facing.NORTH)
					item.updateShape()
		
		# if key == Key.Key_C and mod & KeyMod.ControlModifier:
		# 	comps = [item.getData() for item in self.selectedItems() if isinstance(item, CompItem)]
		# # DEBUG
		# if key == Key.Key_Space:
		# 	for item in self.selectedItems():
		# 		if isinstance(item, CompItem):
		# 			print(item.getData())
		# 			break


		super().keyPressEvent(event)