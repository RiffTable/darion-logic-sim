from __future__ import annotations
from typing import cast

from QtCore import *
from CircuitScene import CircuitScene



class CircuitView(QGraphicsView):
	scene: CircuitScene
	def __init__(self):
		self.scene = CircuitScene()
		super().__init__(self.scene)

		self.setSceneRect(-5000, -5000, 10000, 10000)
		self.viewport().setMouseTracking(True)
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

		self.lastMousePos = QPointF(0, 0)

		# Zooming
		self.viewScale = 1
		self.zoomlvl = 1
	

	###======= MOUTH CONTROLS =======###
	def mousePressEvent(self, event: QMouseEvent):
		if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
		# if event.button() == Qt.MouseButton.MiddleButton or event.button() == Qt.MouseButton.RightButton:
			self.lastMousePos = event.position()
		
		super().mousePressEvent(event)
	
	def mouseMoveEvent(self, event: QMouseEvent):
		mousepos = event.position()
		if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
			delta = mousepos - self.lastMousePos
			
			self.translate(
				delta.x()/self.viewScale,
				delta.y()/self.viewScale
			)
		else:
			super().mouseMoveEvent(event)
		
		self.lastMousePos = mousepos
	
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
			dy = angleDelta.y()
			if abs(dy) <= 1: return

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
