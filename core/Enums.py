from enum import IntEnum
from core.QtCore import *





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
    
    def toTuple(self, scale: float = 1) -> tuple[float, float]:
        match self:
            case Facing.WEST : return (-scale,  0)
            case Facing.EAST : return (+scale,  0)
            case Facing.NORTH: return ( 0, -scale)
            case Facing.SOUTH: return ( 0, +scale)
    
    def toPointF(self, scale: float = 1) -> QPointF:
        match self:
            case Facing.WEST : return QPointF(-scale,  0)
            case Facing.EAST : return QPointF(+scale,  0)
            case Facing.NORTH: return QPointF( 0, -scale)
            case Facing.SOUTH: return QPointF( 0, +scale)
        
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
    def _missing_(cls, value):
        if isinstance(value, int): return cls(value % 4)
        return super()._missing_(value)



###======= EDITOR STATES =======###
class EditorState(IntEnum):
    NORMAL = 0
    WIRING = 1



###======= EDITOR STATES =======###
class Prop(IntEnum):
    # POS         = 0
    LABEL       = 0    # Edittable TAG
    TAG         = 1    # Unedittable TAG
    FACING      = 2
    MIRROR      = 3
    STATE       = 4
    INPUTSIZE   = 5