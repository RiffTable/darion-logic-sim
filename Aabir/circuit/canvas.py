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
	def __init__(self, pos: QPointF, size: QPoint, padding: QPointF):
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
		self.outputPins : list[OutputPinItem] = []    # Facing.East
		self.inputPins  : list[InputPinItem] = []    # Facing.West
		self.topPins    : list[PinItem] = []    # Facing.North
		self.bottomPins : list[PinItem] = []    # Facing.South

		# Visual
		self.setPen(QPen(Color.outline, 2))
		self.setBrush(Color.gate)
		# inPin1  = InputPinItem(self, (0, 0), Facing.West)
		# inPin2  = InputPinItem(self, (0, 60), Facing.West)
		# outPin1 = OutputPinItem(self, (80, 0), Facing.East)
		# outPin1 = OutputPinItem(self, (80, 60), Facing.East)
		inputA  = InputPinItem(self, (0, 1*SIZE), Facing.West)
		inputB  = InputPinItem(self, (0, 3*SIZE), Facing.West)
		output  = OutputPinItem(self, (w*SIZE, 2*SIZE), Facing.East)


		# Label
		self.labelItem = QGraphicsTextItem(self.labelText, self)
		self.labelItem.setFont(Font.default)
		self.labelItem.setPos(5, 10)

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
		self.wire: WireItem = None
		self.isHighlighted = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(*relpos)
	
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			if self.wire: self.wire.updatePath()
		
		return super().itemChange(change, value)
	
	def highlight(self, isHovered: bool) -> None:
		...    # ABSTRACT METHOD
	
	def connect(self, wire: WireItem):
		self.wire = wire
		self.updateVisual()

	def hoverEnterEvent(self, event):
		self.highlight(True)
		self.updateVisual()
		super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event):
		self.highlight(False)
		self.updateVisual()
		super().hoverLeaveEvent(event)
	
	def paint(self, painter: QPainter, option, widget):
		r = 3

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))
	
	def updateVisual(self):
		if self.isHighlighted:
			self.setPen(Qt.PenStyle.NoPen)
			self.setBrush(QBrush(Color.pin_hover))
		
		elif self.wire:
			self.setPen(QPen(Color.outline, 2))
			self.setBrush(Qt.BrushStyle.NoBrush)
		
		else:
			self.setPen(Qt.PenStyle.NoPen)
			if self.state:
				self.setBrush(QBrush(Color.pin_on))
			else:
				self.setBrush(QBrush(Color.pin_off))


### Input Pin
class InputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)

	def disconnect(self):
		self.wire.cutSupply(self)
		self.wire = None
		self.updateVisual()
	
	def highlight(self, isHovered: bool) -> None:
		scene: CircuitScene = self.scene()
		self.isHighlighted = isHovered and scene.state == EditorState.WIRING
		self.updateVisual()
	
	def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
		scene: CircuitScene = self.scene()
		if scene.state == EditorState.WIRING:
			source = scene.wireSource
			if not source.wire:
				w = WireItem(source, self)
				scene.wires.append(w)
				scene.addItem(w)
			else:
				source.wire.addSupply(self)
			
			# self.run_logic()
			scene.state = EditorState.NORMAL
			scene.wireSource = None
		
		super().mouseReleaseEvent(event)


### Output Pin
class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def disconnect(self):
		self.wire.cutSource()
		self.wire = None
		self.updateVisual()

	
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

		beg.connect(self)
		end.connect(self)

		# Properties
		self.state = False
		self.source = beg
		self.supplies: list[InputPinItem] = [end]

		self.updatePath()
	
	def addSupply(self, pin: InputPinItem):
		self.supplies.append(pin)
		pin.connect(self)
		self.updatePath()
	
	def cutSupply(self, pin: InputPinItem):
		if not pin in self.supplies:
			return
		pin.wire = None
		self.supplies.remove(pin)
		if len(self.supplies) == 0:
			self.delete()
		else:
			self.updatePath()
	
	def cutSource(self):
		self.source.wire = None
		for supply in self.supplies:
			supply.wire = None
			supply.updateVisual()
		self.supplies.clear()
		self.delete()
	
	def delete(self):
		self.source.wire = None
		self.scene().removeItem(self)
			
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
		self.gates: list[CompItem] = []
		self.wires: list[WireItem] = []
		self.state = EditorState.NORMAL
		self.wireSource: OutputPinItem = None

	def addComp(self, x: float, y:float, comp_type: type[CompItem]):
		comp = comp_type(QPointF(x, y), QPoint(5, 4), QPointF(0, 3))
		self.addItem(comp)
		self.gates.append(comp)
# endregion