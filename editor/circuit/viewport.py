from __future__ import annotations
from typing import cast

from core.QtCore import *
from .canvas import CircuitScene





class CircuitView(QGraphicsView):
	def __init__(self):
		self._scene = CircuitScene()
		super().__init__(self._scene)

		self.DRAG_THRESHOLD = QGuiApplication.styleHints().startDragDistance()
		self.setSceneRect(-5000, -5000, 10000, 10000)
		self.viewport().setMouseTracking(True)
		self.setInteractive(True)
		self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
		self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
		self.setRenderHints(
			QPainter.RenderHint.Antialiasing |
			QPainter.RenderHint.TextAntialiasing
		)
		
		# Hide scrollbars
		self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		# Disable scrollbars
		self.horizontalScrollBar().disconnect(self)
		self.verticalScrollBar().disconnect(self)
		# self.setTransformationAnchor(QGraphicsView.NoAnchor)    # .translate() moves scrollbars

		self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
		self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
		self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

		# Panning
		self._pan_last_pos = QPointF(0, 0)
		self.dragStart: dict[MouseBtn, QPointF] = {}

		# Zooming
		self.viewScale = 1

		
		self.scroll_inverted = False
	
	
	@property
	def cscene(self) -> CircuitScene:
		return self._scene
	

	###======= MOUSE CONTROLS =======###	
	def isDragAction(self, delta: QPointF) -> bool:
		return delta.manhattanLength() >= self.DRAG_THRESHOLD

	def mousePressEvent(self, event: QMouseEvent):
		mousepos = event.position()
		btn = event.button()
		
		# Tracking mouse dragging
		self.dragStart[btn]    = mousepos

		# Canvas Panning Last Position Tracking
		if event.buttons() & (MouseBtn.RightButton | MouseBtn.MiddleButton):
			self._pan_last_pos = mousepos
			event.accept(); return
		
		super().mousePressEvent(event)
	
	def mouseMoveEvent(self, event: QMouseEvent):
		mousepos = event.position()

		# Canvas Panning
		if event.buttons() & (MouseBtn.RightButton | MouseBtn.MiddleButton):
			delta = mousepos - self._pan_last_pos
			self.panCanvas(delta.toPoint())
		else:
			super().mouseMoveEvent(event)
		
		self._pan_last_pos = mousepos
	
	def mouseReleaseEvent(self, event: QMouseEvent):
		btn = event.button()
		mousepos = event.position()

		# Tracking mouse dragging (Possible None value is assumed to be (0, 0))
		# Double click can produce None
		start_pos = self.dragStart.pop(btn, mousepos)
		# print(f"{btn}: {dragDelta}")

		if start_pos is None:
			return super().mouseReleaseEvent(event)

		# Don't let the SCENE see RMB release if it ended after dragging
		if self.isDragAction(mousepos-start_pos) and btn == MouseBtn.RightButton:
			event.accept(); return
		
		return super().mouseReleaseEvent(event)
    
	def setScrollInverted(self, inverted):
		self.scroll_inverted = inverted
	
	def wheelEvent(self, event: QWheelEvent):
		pixelDelta = event.pixelDelta()
		angleDelta = event.angleDelta()
		dev = event.device()

		# Check if Touchpad
		if dev and dev.type() == QInputDevice.DeviceType.TouchPad:
			self.panCanvas(pixelDelta)
			return

		# Check if Mouse Wheel
		if dev and dev.type() == QInputDevice.DeviceType.Mouse:
			# angleDelta.y() equals to +/- 120 for mouse scroll, never below
			dy = angleDelta.y()
			if abs(dy) <= 10: return

			factor = 1.25 if dy > 0 else 0.8
			if self.scroll_inverted:
				factor = 0.8 if dy > 0 else 1.25

			self.applyZoom(
				event.position().toPoint(),
				factor
			)
	
	def viewportEvent(self, event: QEvent):
		if event.type() == QEvent.Type.NativeGesture:
			gestEvent = cast(QNativeGestureEvent, event)
			if gestEvent.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
				self.applyZoom(
					gestEvent.position().toPoint(),
					1.0 + gestEvent.value()
				)
				return True
		return super().viewportEvent(event)
	
	def keyPressEvent(self, event):
		key = event.key()
		mods = event.modifiers()
		
		return super().keyPressEvent(event)
	


	###======= ACTIONS =======###
	def panCanvas(self, delta: QPoint):
		self.setDragMode(QGraphicsView.DragMode.NoDrag)
		self.translate(
			delta.x()/self.viewScale,
			delta.y()/self.viewScale
		)
		self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
	
	def applyZoom(self, mousePos: QPoint, factor: float):
		minZ = 0.5
		maxZ = 2.0

		# Tracking data
		curZ = self.transform().m11()
		before = self.mapToScene(mousePos)

		# Calculating zoom factor
		newZ = curZ*factor
		newZ = max(minZ, min(newZ, maxZ))

		# Applying Zoom
		k = newZ/curZ
		self.scale(k, k)
		self.viewScale = newZ

		# Making sure cursor stays on the same position in scene
		after = self.mapToScene(mousePos)
		delta = after - before
		self.translate(delta.x(), delta.y())
	
	def zoomInOnMouse(self):
		self.applyZoom(self.viewport().mapFromGlobal(QCursor.pos()), 1.25)
	def zoomOutFromMouse(self):
		self.applyZoom(self.viewport().mapFromGlobal(QCursor.pos()), 0.8)
	
	def undo(self):
		print("Undo not implemented yet :P")

	def redo(self):
		print("Redo not implemented yet :P")