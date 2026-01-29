from enum import IntEnum
from common.QtCore import *





###======= ROTATION =======###
class Rotation(IntEnum):
	FORWARD  = 0
	RIGHT    = 1
	REVERESE = 2
	LEFT     = 3



###======= FACING =======###
class Facing(IntEnum):
	EAST     = 0
	SOUTH    = 1
	WEST     = 2
	NORTH    = 3
	NOTHING  = 4
	
	def opposite(self) -> 'Facing':
		return Facing((self.value + Rotation.REVERESE) % 4)
	
	def addRotation(self, rot: Rotation) -> 'Facing':
		return Facing((self.value + rot.value) % 4)
	
	def getRotation(self, other: 'Facing') -> Rotation:
		return Rotation((other.value - self.value) % 4)
	
	def toTuple(self, scale: float = 1) -> tuple[int, int]:
		return {
			Facing.WEST : (-scale,  0),
			Facing.EAST : (+scale,  0),
			Facing.NORTH: ( 0, -scale),
			Facing.SOUTH: ( 0, +scale)
		}[self]

	@staticmethod
	def toFacing(point: QPoint|QPointF):
		(x, y) = point.toTuple()
		if abs(x) > abs(y): return Facing.EAST  if x > 0 else Facing.WEST
		else:               return Facing.SOUTH if y > 0 else Facing.NORTH



###======= COMP EDGE =======###
class CompEdge(IntEnum):
	INPUT    = 0
	OUTPUT   = 1
	TOP      = 2
	BOTTOM   = 3



###======= EDITOR STATES =======###
class EditorState(IntEnum):
	NORMAL = 0
	WIRING = 1