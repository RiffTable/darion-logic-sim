from PySide6.QtCore import QPointF

SIZE = 12
DSIZE = 2*SIZE

def snapF(point: QPointF) -> QPointF:
	return QPointF(
		(point.x()//SIZE+0.5)*SIZE,
		(point.y()//SIZE+0.5)*SIZE
	)

def snapT(tup: tuple[float, float]) -> tuple[float, float]:
	return (
		(tup[0]//SIZE+0.5)*SIZE,
		(tup[1]//SIZE+0.5)*SIZE
	)