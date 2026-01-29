from __future__ import annotations
from typing import cast

from QtCore import *
from circuit.canvas import CircuitScene
from Enums import EditorState



class CircuitView(QGraphicsView):
	scene: CircuitScene
	def __init__(self):
		self.scene = CircuitScene()
		super().__init__(self.scene)

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
		self._pan_1stpress = QPointF(0, 0)

		# Zooming
		self.viewScale = 1
		self.zoomlvl = 1
	

	###======= MOUSE CONTROLS =======###
	def mousePressEvent(self, event: QMouseEvent):
		if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
			self._pan_1stpress = self._pan_last_pos = event.position()
		
		super().mousePressEvent(event)
	
	def mouseMoveEvent(self, event: QMouseEvent):
		mousepos = event.position()
		if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
			delta = mousepos - self._pan_last_pos
			
			self.translate(
				delta.x()/self.viewScale,
				delta.y()/self.viewScale
			)
		else:
			super().mouseMoveEvent(event)
		
		self._pan_last_pos = mousepos
	
	def mouseReleaseEvent(self, event: QMouseEvent):

		if event.button() == Qt.MouseButton.RightButton and self.scene.checkState(EditorState.WIRING):
			# Wiring: Skip!
			dragDisplacement = event.position() - self._pan_1stpress
			if dragDisplacement.manhattanLength() < QApplication.startDragDistance():
				self.scene.skipWiring()
		
		return super().mouseReleaseEvent(event)
	
	def wheelEvent(self, event: QWheelEvent):
		pixelDelta = event.pixelDelta()
		angleDelta = event.angleDelta()
		dev = event.device()

		# Check if Touchpad
		if dev and dev.type() == QInputDevice.DeviceType.TouchPad:
			self.translate(
				pixelDelta.x()/self.viewScale,
				pixelDelta.y()/self.viewScale
			)
			return

		# Check if Mouse Wheel
		if dev and dev.type() == QInputDevice.DeviceType.Mouse:
			# angleDelta.y() equals to +/- 120 for mouse scroll, never below
			dy = angleDelta.y()
			if abs(dy) <= 10: return

			self.applyZoom(
				event.position().toPoint(),
				1.25 if dy > 0 else 0.8
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
