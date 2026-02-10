from enum import IntEnum
from core.QtCore import *





###======= ROTATION =======###
class Rotation(IntEnum):
	FORWARD       = 0
	CLOCKWISE     = 1
	REVERSE      = 2
	ANTICLOCKWISE = 3

	@classmethod
	def _missing_(cls, value: int):
		if isinstance(value, int): return cls(value % 4)
		return super()._missing_(value)



###======= FACING =======###
class Facing(IntEnum):
	EAST     = 0
	SOUTH    = 1
	WEST     = 2
	NORTH    = 3

	@classmethod
	def _missing_(cls, value: int):
		if isinstance(value, int): return cls(value % 4)
		return super()._missing_(value)	
	
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
	OUTPUT   = 0
	BOTTOM   = 1
	INPUT    = 2
	TOP      = 3

	@classmethod
	def _missing_(cls, value: int):
		if isinstance(value, int): return cls(value % 4)
		return super()._missing_(value)



###======= EDITOR STATES =======###
class EditorState(IntEnum):
	NORMAL = 0
	WIRING = 1