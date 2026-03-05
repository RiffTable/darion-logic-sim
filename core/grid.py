import math
from PySide6.QtCore import QPointF

SIZE = 12
DSIZE = 2*SIZE
SQUARE = QPointF(SIZE, SIZE)

def snapF(point: QPointF) -> QPointF:
	x, y = point.toTuple()
	return QPointF(
		math.floor(x/SIZE+0.5)*SIZE,
		math.floor(y/SIZE+0.5)*SIZE
	)

def snapT(tup: tuple[float, float]) -> tuple[float, float]:
	x, y = tup
	return (
		math.floor(x/SIZE+0.5)*SIZE,
		math.floor(y/SIZE+0.5)*SIZE
	)