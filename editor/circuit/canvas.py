from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, Facing, EditorState
import core.grid as GRID

import editor.theme as theme
from .catalog import (
	LOOKUP, CompItem, WireItem, PinItem, InputPinItem, OutputPinItem,
	InputItem, OutputItem,
	GateItem, ICitem
)





class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.comps: list[CompItem] = []
		self.wires: list[WireItem] = []
		self.iclist: list = []

		self._last_mouse_pos = QPointF()
		self._rmb_last_pos = QPointF()

		# Clipboard
		self.clipboard = { "comps": [], "wires": [], "iclist": [] }

		# Editor Stuffs
		self._state = EditorState.NORMAL
		self.defaultFacing = Facing.EAST
		self.defaultMirror = False
		self.peeking_disabled = False
		self.bg_style = 1

		# Wiring logic
		self.hoveredComp: CompItem|None = None
		self.hoveredPin: PinItem|None = None
		self.ghostWire: WireItem|None = None
		self.ghostPin = InputPinItem(None, QPointF(), Facing.WEST)

		self.ghostPin.hide()    # These three lines does the same thing but still...
		self.ghostPin.setEnabled(False)    # You can never be too sure
		self.ghostPin.setAcceptedMouseButtons(MouseBtn.NoButton)

		self.addItem(self.ghostPin)

		# Replacement to the simpler listener system
		fps = QGuiApplication.primaryScreen().refreshRate()
		fps = (60 if fps==0 else fps)
		self.ui_update_timer = QTimer(self)
		self.ui_update_timer.timeout.connect(self.poll_ui_state)
		self.ui_update_timer.start(round(1000/fps))

	def poll_ui_state(self):
		# Updates screen per frame
		for comp in self.comps:
			unit = comp._unit
			if unit is None:
				continue

			if isinstance(comp, (GateItem, InputItem, OutputItem)):
				# These components have single output and its calculation is optimized
				current = unit.output
				if comp.prevState != current:
					comp.prevState = current
					comp.unitStateChanged(current)
			
			else:
				# These components can have multiple outputs and thus slower calculation
				for pinlist in comp._pinslist.values():
					for pin in pinlist:
						if isinstance(pin, OutputPinItem) and pin.logical is not None:
							current = pin.logical.output
							if current != pin.state:
								pin.logicalStateChanged(current)

	# Editor State Management
	def checkState(self, st: EditorState) -> bool:
		return self.getState() == st
	
	def getState(self):
		return self._state
		# if self.ghostWire: return EditorState.WIRING
		# return EditorState.NORMAL
	
	def setState(self, st: EditorState):
		self._state = st


	# Components Management
	def addComp(self, x: float, y:float, comp_id: int):
		comp_type = LOOKUP[comp_id]
		comp = comp_type(
			QPointF(x, y),
			facing = self.defaultFacing,
			mirror = self.defaultMirror,
		)
		
		self.addItem(comp)
		self.comps.append(comp)
		return comp

	def removeComp(self, comp: CompItem):
		if comp not in self.comps: return
		comp.cutConnections()
		if comp._unit is not None and comp._unit in logic.objlist[comp.LOGIC]:
			logic.hide([comp._unit])
		comp._unit = None    # just in case

		self.comps.remove(comp)
		self.removeItem(comp)
	
	def addCompFromData(self, _data: dict) -> CompItem:
		data = _data.copy()
		comp_type = LOOKUP[data.pop("id")]
		if comp_type.LOGIC == Const.IC_ID:
			data["ic_data"] = self.iclist[int(data["ic_data_index"])]
		pos = QPointF(*data.pop("pos")) + QPoint(7, 5)*GRID.SIZE
		
		comp = comp_type(pos, **data)
		
		self.addItem(comp)
		self.comps.append(comp)
		return comp
	
	
	# IC Management
	def addIC(self, x: float, y:float, ic_data_index: int):
		comp = ICitem(
			QPointF(x, y),
			ic_data_index,
			self.iclist[ic_data_index],
			facing = self.defaultFacing,
			mirror = self.defaultMirror,
		)
		
		self.addItem(comp)
		self.comps.append(comp)
		return comp
	
	def makeICfyable(self):
		# logic.diagnose()
		comps = self.comps.copy()
		for comp in comps:
			if isinstance(comp, InputItem):
				w = comp.outputPin.getWire()
				targets = []
				if w is not None and comp.outputPin.logical:
					targets = [supply.logical for supply in w.supplies if supply.logical is not None]

					self.removeComp(comp)

					inpin = cast(Gate, logic.getcomponent(Const.INPUT_PIN_ID))
					for g, i in targets:
						logic.connect(g, inpin, i)
				else:
					self.removeComp(comp)
		
		# Output items are not converted since they are already of class Out
		#! Don't forget to order the pins
	
	
	# Wires	Management
	def finishWiring(self, target: QGraphicsItem|None, multiWireMode: bool) -> bool:
		g_wire = self.ghostWire
		if g_wire is None: return False

		g_pin = self.ghostPin
		source = g_wire.source

		# Wiring: Finish!
		if isinstance(target, CompItem):
			# Proxying: Wire is connected to the gate's *favorite* pin
			target = target.proxyPin()
			if target is None: return False
		
		if isinstance(target, InputPinItem):
			t_wire = target.getWire()
			# Add wire to canvas
			if len(g_wire.supplies) == 1:
				self.wires.append(g_wire)

			if t_wire:  # Swap Connections

				g_wire.supplies.remove(g_pin); g_wire.supplies.append(target)
				t_wire.supplies.append(g_pin); t_wire.supplies.remove(target)


				if target.logical: logic.disconnect(*target.logical)
				g_wire.logicalConnect(source, target)
				
				g_pin.setWire(t_wire);  g_wire.updateShape()
				target.setWire(g_wire); t_wire.updateShape()
				self.ghostWire = t_wire
				
			else:  # Connecting wire to an empty pin

				# End WIRING phase if not multi-wiring
				if not multiWireMode:
					g_wire.supplies.remove(g_pin);  g_pin.setWire(None)
					self.setState(EditorState.NORMAL)
					self.ghostWire = None
				
				# Solo select the finished wire
				self.clearSelection()
				g_wire.setSelected(True)
				
				# Attach wire to pin
				g_wire.supplies.append(target); target.setWire(g_wire)
				if target.logical and source.logical:
					unit, idx = target.logical

					# print(f"{isinstance(unit, Gate)} and {idx >= unit.inputlimit}")
					# Resize gate input if needed
					if isinstance(unit, Gate) and idx >= unit.inputlimit:
						unit.setlimits(idx+1)
					logic.connect(unit, source.logical, idx)

				g_wire.updateShape()
			
			parent = target.parentComp
			self.updateHoverStatus(None, parent, True)
			return True
		
		return False
	
	def skipWiring(self):
		if self.checkState(EditorState.WIRING):
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
			
			# Update hovered pin and comps that state changed
			# TODO: Make it generalized for all state changes
			self.updateHoverStatus(self.hoveredPin, self.hoveredComp, True)

	def removeWire(self, wire: WireItem):
		# Works for both ghost wires and regular wires
		if (wire not in self.wires) and wire is self.ghostWire:
			return
		
		wire._disconnect()

		if not (wire is self.ghostWire): self.wires.remove(wire)
		self.removeItem(wire)

	###======= MOUSE/KEY EVENTS =======###
	def updateHoverStatus(self, pin: PinItem|None, comp: CompItem|None = None, forced: bool = False):
		"""
		(PIN, COMP, ...):   Only updates if the PIN belongs to COMP \\
		(NONE, COMP, ...):  Updates the comp's proxy pin \\
		(PIN, NONE, ...) :  Updates the pin's parent \\
		(NONE, NONE, ...) : Unhighlights the previous \\
		"""
		
		hcomp = self.hoveredComp
		hpin = self.hoveredPin
		if pin:
			# Find the pin's component
			if comp is None:
				comp = pin.parentComp

			# Exit function if pin doesn't belong to component
			elif (comp is not pin.parentComp): return
		
		# ---------- DEBUG ----------
		# _pstat = "ACT" if pin else "---"
		# _cstat = "ACT" if comp else "---"
		# _hpstat = "ACT" if hpin else "---"
		# _hcstat = "ACT" if hcomp else "---"
		# if (pin and comp is None): _cstat = "INH"
		# if (pin is None and comp): _pstat = "PXY"
		# print(f"pin: {_pstat}, comp: {_cstat}, hpin: {_hpstat}, hcomp: {_hcstat}")
		
		if (hcomp is not comp) or forced:
			# Unhighlight previously highlighted pin
			if hcomp:
				if forced: hcomp.betterHoverLeave()
				else:      hcomp.hoverLeaveTimer.start()
			self.hoveredComp = comp

			# Highlight Comp
			if comp:
				if not comp.hoverLeaveTimer.isActive() or forced:
					comp.betterHoverEnter()
				comp.hoverLeaveTimer.stop()

				# Now that the peeking pin is out, focus on that
				if pin is None:
					pin = comp.proxyPin()
		
		if (hpin is not pin) or forced:
			# Unhighlight previously highlighted pin
			if hpin:
				hpin.highlight(False)
			self.hoveredPin = pin

			# Highlight Pin
			if pin:
				S = self.checkState(EditorState.WIRING)
				I = isinstance(pin, InputPinItem)
				highlightCondition = ((I == S) and not(pin.hasWire() and I))
				# ---------- DEBUG ----------
				# print("I: ", I)
				# print("S: ", S)
				# print("W: ", pin.hasWire())
				# print("res: ", highlightCondition)

				pin.highlight(highlightCondition)
				self.ghostPin.setPos(pin.scenePos())

	def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
		mousepos = event.scenePos()
		if (mousepos - self._last_mouse_pos).manhattanLength() < 2:
			return
		
		items = self.items(mousepos)

		# Find pin hovered by cursor
		pin = None
		comp = None
		for item in items:
			if isinstance(item, PinItem):
				pin = item
				comp = item.parentComp
				break
			if isinstance(item, CompItem):
				pin = item.proxyPin()
				comp = item
				break

		self.updateHoverStatus(pin, comp)
		if self.ghostPin is None:
			self.ghostPin = InputPinItem(None, QPointF(), Facing.WEST)
		
		if self.hoveredPin is None:
			self.ghostPin.setPos(GRID.snapF(mousepos))
		
		self._last_mouse_pos = mousepos
		return super().mouseMoveEvent(event)
	
	def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
		item = self.itemAt(event.scenePos(), QTransform())

		# Wiring: Start!
		if self.checkState(EditorState.NORMAL) \
		and isinstance(item, OutputPinItem) \
		and event.button() == MouseBtn.LeftButton:
			self.setState(EditorState.WIRING)
			w = item.getWire()
			if w is None:
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
		scenepos = event.scenePos()
		btn = event.button()
		target = self.itemAt(scenepos, QTransform())

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
	
	def keyPressEvent(self, event: QKeyEvent):
		key = event.key()
		mod = event.modifiers()

		# # DEBUG
		# if key == Key.Key_Space:
		# 	logic.diagnose()

		super().keyPressEvent(event)
	
	###======= BACKGROUND GRID =======###
	def setGridStyle(self, style: str):
		if style == "lines":  self.bg_style = 1
		elif style == "dots": self.bg_style = 2
		else:                 self.bg_style = 0
		self.update()

	def drawBackground(self, painter: QPainter, rect: QRectF | QRect, /) -> None:
		if self.bg_style == 0:    # Grid Hidden
			return
		Color = theme.get_theme()
		bg_color = Color.primary_bg
		grid_color = Color.bg_grid
		painter.fillRect(rect, bg_color)


		rect_left = int(rect.left())
		rect_top =  int(rect.top())
		rect_right =  int(rect.right())
		rect_bottom =  int(rect.bottom())

		left = rect_left - (rect_left % GRID.SIZE)
		top = rect_top - (rect_top % GRID.SIZE)

		if self.bg_style == 1:    # Lines Background
			smol_lines: list[QLineF] = []
			beeg_lines: list[QLineF] = []
			unit_size = GRID.SIZE

			# Vertical Lines
			for x in range(left, rect_right, unit_size):
				line = QLineF(x, rect_top, x, rect_bottom)
				if x%(5*unit_size) == 0: beeg_lines.append(line)
				else:                    smol_lines.append(line)
				
			# Horizontal lines
			for y in range(top, rect_bottom, unit_size):
				line = QLineF(rect_left, y, rect_right, y)
				if y%(5*unit_size) == 0: beeg_lines.append(line)
				else:                    smol_lines.append(line)
			
			painter.setPen(QPen(grid_color, 1))
			painter.drawLines(smol_lines)
			painter.setPen(QPen(grid_color, 2))
			painter.drawLines(beeg_lines)
		
		elif self.bg_style == 2:    # Dots Background
			points = []
			unit_size = 2*GRID.SIZE

			for x in range(left, rect_right, unit_size):
				for y in range(top, rect_bottom, unit_size):
					points.append(QPointF(x, y))
			
			painter.setPen(QPen(grid_color.lighter(120), 3))
			painter.drawPoints(points)



	def clearCanvas(self):
		for wire in self.wires.copy():
			self.removeWire(wire)
		for comp in self.comps.copy():
			self.removeComp(comp)
	
	def serialize(self) -> dict:
		return {
			"comps": [comp.getData() for comp in self.comps],
			"wires": []
		}
	
	def deserialize(self, data: dict, addToSelected: bool = False):
		sources: dict[int, OutputPinItem] = {}
		supplies: dict[int, list[InputPinItem]] = {}

		# Creating Components from data
		for comp_data in data.get("comps", []):
			comp = self.addCompFromData(comp_data)
			if addToSelected: comp.setSelected(True)

			# Getting all pins reference to wire them later
			for _edge, pin_data_list in comp_data["pinslist"].items():
				edge = CompEdge(int(_edge))
				for i, pin_data in enumerate(pin_data_list):
					w = pin_data["wire"]
					if w == 0: continue

					if pin_data["isInput"]:
						p = cast(InputPinItem, comp._pinslist[edge][i])
						if w in supplies: supplies[w].append(p)
						else:             supplies[w] = [p]
					else:
						p = cast(OutputPinItem, comp._pinslist[edge][i])
						sources[w] = p
		
		# Wiring
		for id, outpin in sources.items():
			if id not in supplies: continue

			inpins = supplies[id]
			w = WireItem(outpin, inpins.pop(0))
			
			for inpin in inpins:
				w.addSupply(inpin)
			
			self.wires.append(w)
			self.addItem(w)



	###======= ACTIONS =======###
	def removeFromSelection(self):
		for item in self.selectedItems():
			if isinstance(item, WireItem):
				if item in self.wires: self.removeWire(item)
			
			elif isinstance(item, CompItem):
				if item in self.comps: self.removeComp(item)
	
	def selectNone(self):
		for item in self.selectedItems():
			item.setSelected(False)
		self.clearSelection()

	def selectAllComps(self):
		self.clearSelection()
		for item in self.comps:
			item.setSelected(True)
	
	def copyFromSelection(self):
		comps = [item.getData() for item in self.selectedItems() if isinstance(item, CompItem)]
		self.clipboard = {
			"comps": comps,
			"wires": []
		}
	def pasteComps(self):
		self.clearSelection()
		self.deserialize(self.clipboard, True)
	def cutComps(self):
		self.copyFromSelection()
		self.removeFromSelection()
	
	# Orientation
	def rotateSelectionCW(self):
		for item in self.selectedItems():
			if isinstance(item, CompItem): item.rotateCW()
	def rotateSelectionCCW(self):
		for item in self.selectedItems():
			if isinstance(item, CompItem): item.rotateCCW()
	def flipSelectionHorizontal(self):
		for item in self.selectedItems():
			if isinstance(item, CompItem): item.flipHorizontal()
	def flipSelectionVertical(self):
		for item in self.selectedItems():
			if isinstance(item, CompItem): item.flipVertical()
	def setFacingForSelected(self, facing: Facing):
		for item in self.selectedItems():
			if isinstance(item, CompItem): item.setFacing(facing)
	
	# Gate Input
	def increaseInputsForSelected(self):
		for item in self.selectedItems():
			if isinstance(item, GateItem): item.setInputCount(len(item.inputPins) + 1)
	def decreaseInputsForSelected(self):
		for item in self.selectedItems():
			if isinstance(item, GateItem): item.setInputCount(len(item.inputPins) - 1)