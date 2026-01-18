# Using this file to import everything I need from PySide6 so that I don't need to
# constantly manage packages and ruin how the other project files look

from PySide6.QtWidgets import (
	QApplication, QMainWindow, QWidget,
	QPushButton, 
	QGraphicsScene, QGraphicsView,
	QVBoxLayout, QHBoxLayout,
	QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent,
)
from PySide6.QtCore import (
	Qt, QObject,
	QEvent, 
	QPoint, QPointF, QLineF, QRectF,
)
from PySide6.QtGui import (
	QPalette, QColor, QFont, QPainter, QPen, QBrush, QPainterPath,
	QInputDevice,
	QMouseEvent, QKeyEvent, QWheelEvent, QNativeGestureEvent,
)