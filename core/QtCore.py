# Using this file to import everything I need from PySide6 so that I don't need to
# constantly manage packages and ruin how the other project files look

from PySide6.QtWidgets import (
	QApplication, QMainWindow, QWidget, QFrame,
	QPushButton, QLabel, QSpinBox,
	QVBoxLayout, QHBoxLayout, QFormLayout,
	QFileDialog, QMenu, QMenuBar, QLineEdit, QScrollArea,

	QGraphicsScene, QGraphicsView,
	QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent,
	QStyle, QStyleOptionGraphicsItem
)
from PySide6.QtCore import (
	Qt, QObject, QEvent, QTimer, QKeyCombination,
	QPoint, QPointF, QLineF, QRectF, QSettings, Signal
)
from PySide6.QtGui import (
	QGuiApplication, QInputDevice, QAction, QKeySequence, QCursor,
	QPalette, QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QTransform,
	QMouseEvent, QKeyEvent, QWheelEvent, QNativeGestureEvent,
)

# Just some Quality of Life
GraphicsItemChange = QGraphicsItem.GraphicsItemChange
GraphicsItemFlag = QGraphicsItem.GraphicsItemFlag
Key = Qt.Key
KeyMod = Qt.KeyboardModifier
MouseBtn = Qt.MouseButton
StandardKey = QKeySequence.StandardKey