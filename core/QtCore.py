# Using this file to import everything I need from PySide6 so that I don't need to
# constantly manage packages and ruin how the other project files look

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QPushButton, QLabel, QLineEdit, QTextEdit, QSpinBox, QComboBox,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QDialog, QFileDialog, QInputDialog, QMessageBox,
    QDialogButtonBox, QMenu, QMenuBar, QLineEdit, QScrollArea,

    QGraphicsScene, QGraphicsView,
    QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent,
    QStyle, QStyleOptionGraphicsItem
)
from PySide6.QtCore import (
    Qt, QObject, QEvent, QTimer, QKeyCombination,
    QPoint, QPointF, QLineF, QRect, QRectF, QCoreApplication, QStandardPaths, QSettings, Signal,
    QVariantAnimation
)
from PySide6.QtGui import (
    QGuiApplication, QInputDevice, QAction, QActionGroup, QKeySequence, QCursor,
    QPalette, QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QTransform,
    QMouseEvent, QKeyEvent, QWheelEvent, QNativeGestureEvent, QUndoCommand, QUndoStack
)

# Just some Quality of Life
GraphicsItemChange = QGraphicsItem.GraphicsItemChange
GraphicsItemFlag = QGraphicsItem.GraphicsItemFlag
StandardLocation = QStandardPaths.StandardLocation
Key = Qt.Key
KeyMod = Qt.KeyboardModifier
MouseBtn = Qt.MouseButton