from __future__ import annotations
from typing import cast
from enum import IntEnum
from QtCore import *

from styles import (Color, Font)

SIZE = 20
def snapToGrid(x: float, y:float) -> tuple[int, int]:
	return (
		round(x/SIZE)*SIZE,
		round(y/SIZE)*SIZE
	)


class Rotation(IntEnum):
	Forward = 0
	Right   = 1
	Reverse = 2
	Left    = 3

class Facing(IntEnum):
	East  = 0
	South = 1
	West  = 2
	North = 3
	Nothing = 4
	
	def opposite(self) -> 'Facing':
		return Facing((self.value + Rotation.Reverse) % 4)
	
	def addRotation(self, rot: Rotation) -> 'Facing':
		return Facing((self.value + rot.value) % 4)
	
	def getRotation(self, other: Facing) -> Rotation:
		return Rotation((other.value - self.value) % 4)
	
	def toPointF(self) -> QPointF:
		return {
			Facing.East : (+1,  0),
			Facing.South: ( 0, +1),
			Facing.West : (-1,  0),
			Facing.North: ( 0, -1)
		}[self]

	@staticmethod
	def toFacing(point: QPoint|QPointF):
		(x, y) = point.toTuple()
		if abs(x) > abs(y): return Facing.East  if x > 0 else Facing.West
		else:               return Facing.South if y > 0 else Facing.North





###======= COMPONENT ITEM =======###
class CompItem(QGraphicsRectItem):
	def __init__(self, pos: QPointF, size: QPoint, padding: QPointF):
		x, y = snapToGrid(*pos.toTuple())
		w, h = size.toTuple()
		dx, dy = padding.toTuple()
		super().__init__(-dx, -dy, w*SIZE + 2*dx, h*SIZE + 2*dy)
		
		# Behavior
		self.setPos(x, y)
		self.setFlags(
			QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
			QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
			QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
		)

		# Properties
		self.state = False
		self.facing = Facing.East
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
		self.label = QGraphicsTextItem("XOR", self)
		self.label.setFont(Font.default)
		self.label.setPos(5, 5)

	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemPositionChange:
			return QPointF(*snapToGrid(*value.toTuple()))

		return super().itemChange(change, value)
	
	def updateVisual(self):
		...





###======= PIN ITEM =======###
class PinItem(QGraphicsRectItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(-SIZE/2, -SIZE/2, SIZE, SIZE, parent)
		self.setAcceptHoverEvents(True)

		self.state = False
		self.wire: WireItem = None
		self.hovering = False
		self.facing = facing
		self.label = ""

		self.updateVisual()
		self.setPos(*relpos)
	
	def updateVisual(self):
		if self.state:      self.setBrush(QBrush(Color.signal_on))
		elif self.hovering: self.setBrush(QBrush(Color.pin_hover))
		else:               self.setBrush(QBrush(Color.signal_off))
	
	def hoverEnterEvent(self, event):
		self.hovering = True
		self.updateVisual()
		super().hoverEnterEvent(event)
	def hoverLeaveEvent(self, event):
		self.hovering = False
		self.updateVisual()
		super().hoverLeaveEvent(event)
	
	def paint(self, painter, option, widget):
		r = 8

		painter.setBrush(self.brush())
		painter.setPen(self.pen())
		painter.drawEllipse(QRectF(
			-r, -r, 2*r, 2*r
		))



class InputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
		# WIRE DRAWING LOGIC
		super().mousePressEvent(event)
	
	def itemChange(self, change: GraphicsItemChange, value):
		if change == GraphicsItemChange.ItemScenePositionHasChanged:
			self.wire.updatePath()
		
		return super().itemChange(change, value)

	def disconnect(self):
		self.wire.cutSupply(self)
		self.wire = None



class OutputPinItem(PinItem):
	def __init__(self, parent: CompItem, relpos: tuple[float, float], facing: int):
		super().__init__(parent, relpos, facing)
	
	def disconnect(self, wire: WireItem):
		wire.cutSource()
		self.wire = None




###======= WIRE ITEM =======###
class WireItem(QGraphicsPathItem):
	def __init__(self, beg: OutputPinItem, end: InputPinItem):
		super().__init__()

		# Behavior
		self.setFlags(QGraphicsItem.ItemIsSelectable)
		self.setZValue(-1)

		# Properties
		self.MINWALK = 2
		self.source = beg
		self.supplies: list[InputPinItem] = [end]
	
	def connect(self, pin: InputPinItem):
		self.supplies.append(pin)
		self.updatePath()
	
	def cutSupply(self, pin: InputPinItem):
		if not pin in self.supplies:
			return
		pin.wire = None
		self.supplies.remove(pin)
		if len(self.supplies) == 0:
			self.source.wire = None
			self.scene().removeItem(self)
	
	def cutSource(self):
		self.source.wire = None
		for supply in self.supplies:
			supply.wire = None
		self.supplies.clear()
		self.source.wire = None
		self.scene().removeItem(self)
			
	def updateVisual(self):
		...
	
	def updatePath(self):
		...

		path = QPainterPath()
		p1 = self.source.scenePos()

		for out in self.supplies:
			p2 = out.scenePos()
			path.moveTo(p1)
			path.cubicTo(p1.x() + 50, p1.y(), p2.x() - 50, p2.y(), p2.x(), p2.y())
			path.lineTo(p2)
			self.setPath(path)
			color = QColor("#2ecc71") if self.start_gate.state == 1 else QColor("#7f8c8d")
			if self.isSelected(): color = QColor("#f39c12")
			self.setPen(QPen(color, 3 if not self.isSelected() else 5))


	def mousePressEvent(self, event):
		if event.button() == Qt.RightButton:
			self.manager.remove_wire(self)
		super().mousePressEvent(event)