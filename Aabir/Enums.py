from enum import IntEnum
from QtCore import *





###======= ROTATION =======###
class Rotation(IntEnum):
	Forward = 0
	Right   = 1
	Reverse = 2
	Left    = 3



###======= FACING =======###
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
	
	def getRotation(self, other: 'Facing') -> Rotation:
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



###======= EDITOR STATES =======###
class EditorState(IntEnum):
	NORMAL = 0
	WIRING = 1