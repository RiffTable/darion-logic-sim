from __future__ import annotations
from typing import cast, TYPE_CHECKING
from enum import IntEnum
from QtCore import *

from styles import Color, Font
from Enums import Facing, Rotation, EditorState





SIZE = 12
def snapToGrid(x: float, y:float) -> tuple[int, int]:
	return (
		round(x/SIZE)*SIZE,
		round(y/SIZE)*SIZE
	)



# region: ###======= COMPONENT ITEM =======###
class CompItem(QGraphicsRectItem):
	def __init__(
			self,
			pos: QPointF | tuple[float, float],
			size: QPoint | tuple[int, int],
			padding: QPointF | tuple[float, float]
		):
		x, y = snapToGrid(*pos.toTuple())
		w, h = size.toTuple()
		dx, dy = padding.toTuple()
		super().__init__(-dx, -dy, w*SIZE + 2*dx, h*SIZE + 2*dy)
		
		# Behavior
		self.setPos(x, y)
		self.setZValue(0)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
			QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)

		# Properties
		self.state = False
		self.facing = Facing.East
		self.labelText = "COMP"
		self.outputPins : list[PinItem] = []    # Facing.East
		self.inputPins  : list[PinItem] = []    # Facing.West
		self.topPins    : list[PinItem] = []    # Facing.North
		self.bottomPins : list[PinItem] = []    # Facing.South

		# Visual
		self.setPen(QPen(Color.outline, 2))
		self.setBrush(Color.gate)

		# fuck
		self.inputPins.append(InputPinItem(self, (0, 1*SIZE), Facing.West))
		self.inputPins.append(InputPinItem(self, (0, 3*SIZE), Facing.West))
		self.outputPins.append(OutputPinItem(self, (w*SIZE, 2*SIZE), Facing.East))


		# Label
		self.labelItem = QGraphicsTextItem(self.labelText, self)
		self.labelItem.setFont(Font.default)
		self.labelItem.setPos(5, 10)
	
	# def addInputPin(self, index: int, edge: Facing) -> InputPinItem:
	# 	facing = {
	# 		Facing.East: self.outputPins,
	# 		Facing.West: self.inputPins,
	# 		Facing.North: self.topPins,
	# 		Facing.South: self.bottomPins
	# 	}[edge]
	# 	...
	
	# def addOutputPin(self, index: int, edge: Facing) -> OutputPinItem:
	# 	...
	
	def allPins(self):
		pins = self.outputPins + self.inputPins + self.topPins + self.bottomPins
		return pins
	
	def cutConnections(self):
		for p in self.allPins():
			p.disconnect()

	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemPositionChange:
			return QPointF(*snapToGrid(*value.toTuple()))

		return super().itemChange(change, value)
	
	def updateVisual(self):
		...
	
	def mouseReleaseEvent(self, event):
		return super().mouseReleaseEvent(event)
# endregion



# region: ###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parentComp: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(-SIZE/2, -SIZE/2, SIZE, SIZE, parentComp)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
		)
		self.setPen(Qt.PenStyle.NoPen)
		self.setAcceptHoverEvents(True)
		self.setZValue(1)

		self.state = False
		self._wire: WireItem = None
		self.isHighlighted = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(*relpos)
	
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			if self._wire: self._wire.updatePath()
		
		return super().itemChange(change, value)
	
	def highlight(self, isHovered: bool) -> None:
		...    # ABSTRACT METHOD
	def disconnect(self):
		...    # ABSTRACT METHOD
	
	def setWire(self, wire: WireItem):
		self._wire = wire
		self.updateVisual()

	def hoverEnterEvent(self, event): self.highlight(True);  super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event): self.highlight(False); super().hoverLeaveEvent(event)
	
	def paint(self, painter: QPainter, option, widget):
		r = 3

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))
	
	def updateVisual(self):
		if self.isHighlighted:
			self.setPen(QPen(Color.outline, 2))
			self.setBrush(QBrush(Color.pin_hover))
		
		elif self._wire:
			self.setPen(Qt.PenStyle.NoPen)
			self.setBrush(Qt.BrushStyle.NoBrush)
		
		else:
			self.setPen(QPen(Color.outline, 2))
			if self.state:
				self.setBrush(QBrush(Color.pin_on))
			else:
				self.setBrush(QBrush(Color.pin_off))


### Input Pin
class InputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)

	def disconnect(self):
		if not self._wire: return

		self._wire.cutSupply(self)
	
	def highlight(self, isHovered: bool) -> None:
		scene: CircuitScene = self.scene()
		self.isHighlighted = isHovered and scene.state == EditorState.WIRING
		self.updateVisual()
	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		scene: CircuitScene = self.scene()
		if scene.state == EditorState.WIRING:
			source = scene.wireSource
			if not self._wire:
				if not source._wire:
					w = WireItem(source, self)
					scene.wires.append(w)
					scene.addItem(w)
				else:
					source._wire.addSupply(self)
			
			# self.run_logic()
			scene.state = EditorState.NORMAL
			scene.wireSource = None
		
		super().mouseReleaseEvent(event)


### Output Pin
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def disconnect(self):
		if not self._wire: return

		scene: CircuitScene = self.scene()
		scene.removeWire(self._wire)
	
	def highlight(self, isHovered: bool) -> None:
		scene: CircuitScene = self.scene()
		self.isHighlighted = isHovered and scene.state == EditorState.NORMAL
		self.updateVisual()
	
	def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
		if event.button() == Qt.LeftButton:
			scene: CircuitScene = self.scene()
			scene.state = EditorState.WIRING
			scene.wireSource = self
		
		super().mousePressEvent(event)
# endregion



# region: ###======= WIRE ITEM =======###
class WireItem(QGraphicsPathItem):
	MINWALK = 2
	def __init__(self, beg: OutputPinItem, end: InputPinItem):
		super().__init__()

		# Behavior
		self.setFlags(QGraphicsItem.ItemIsSelectable)
		self.setZValue(-1)

		beg.setWire(self)
		end.setWire(self)

		# Properties
		self.state = False
		self.source = beg
		self.supplies: list[InputPinItem] = [end]

		self.updatePath()
	
	def addSupply(self, pin: InputPinItem):
		if pin in self.supplies: return
		self.supplies.append(pin)
		pin.setWire(self)
		self.updatePath()
	
	def cutSupply(self, pin: InputPinItem):
		if not pin in self.supplies: return

		pin.setWire(None)
		self.supplies.remove(pin)

		# Check if wire has any supply left
		if len(self.supplies) == 0:
			scene: CircuitScene = self.scene()
			scene.removeWire(self)
		else:
			self.updatePath()
	
	def updateVisual(self):
		color = Color.signal_on if self.state else Color.signal_off
		# if self.isSelected(): color = QColor("#f39c12")
		self.setPen(QPen(color, 3))
	
	def updatePath(self):
		path = QPainterPath()
		p1 = self.source.scenePos()

		for out in self.supplies:
			p2 = out.scenePos()
			path.moveTo(p1)
			path.cubicTo(
				p1.x() + 50, p1.y(),
				p2.x() - 50, p2.y(),
				p2.x(), p2.y()
			)
			path.lineTo(p2)
		
		self.setPath(path)
		self.updateVisual()


	def mousePressEvent(self, event):
		if event.button() == Qt.RightButton:
			self.manager.remove_wire(self)
		super().mousePressEvent(event)
# endregion



# region: ###======= CIRCUIT SCENE =======###
class CircuitScene(QGraphicsScene):
	def __init__(self):
		super().__init__()

		self.SIZE = 12
		self.comps: list[CompItem] = []
		self.wires: list[WireItem] = []
		self.state = EditorState.NORMAL
		self.wireSource: OutputPinItem = None

	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y), QPoint(5, 4), QPointF(0, 3))
		self.addItem(comp)
		self.comps.append(comp)
		# run_logic()
	
	def removeComp(self, comp: CompItem):
		if comp not in self.comps: return
		comp.cutConnections()

		self.comps.remove(comp)
		self.removeItem(comp)
		# run_logic()
	
	def removeWire(self, wire: WireItem):
		if wire not in self.wires: return
		
		wire.source.setWire(None)
		for supply in wire.supplies:
			supply.setWire(None)

		self.wires.remove(wire)
		self.removeItem(wire)
		# run_logic()

	def keyPressEvent(self, event):
		if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_X):
			for item in self.selectedItems():
				if isinstance(item, WireItem):
					if item in self.wires: self.removeWire(item)
				
				elif isinstance(item, CompItem):
					if item in self.comps: self.removeComp(item)
				
			# self.run_logic()
		super().keyPressEvent(event)
# endregion