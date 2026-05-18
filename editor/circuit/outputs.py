from __future__ import annotations
import math
from typing import cast
from core.QtCore import *
from PySide6.QtGui import QFontMetrics
from core.LogicCore import *
from core.Enums import CompEdge, Prop
from editor.styles import Font, Val
from editor import theme
import core.grid as GRID

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem


# ─────────────────────────────────────────────────────────────────────────────
# OutputItem
# ─────────────────────────────────────────────────────────────────────────────

class OutputItem(CompItem):
    TAG   = "OUT"
    LOGIC = Const.PROBE_ID
    NAME  = DESC = "LED"

    # ── Sizing ────────────────────────────────────────────────────────────────

    def _text_side_px(self) -> float:
        fm   = QFontMetrics(Font.gate)
        tw   = fm.horizontalAdvance(self.tag)
        th   = fm.height()
        diag = math.hypot(tw, th)
        return max(GRID.SIZE * 3, diag + GRID.SIZE * 1.2)

    def getRelSize(self) -> tuple[int, int]:
        side_px = self._text_side_px()
        units   = math.ceil(side_px / GRID.SIZE)
        if units % 2:
            units += 1
        return (units, units)

    def getRelPadding(self): return (0, 4)

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, pos: QPointF, **kwargs):
        super().__init__(pos, **kwargs)
        self._custom_draw = True

        # Properties
        self.state: int = Const.LOW
        self.prevState  = -1

        # Colour animation
        self.current_color: QColor = theme.get_theme().LED_off
        self.color_anim = QVariantAnimation()
        self.color_anim.setDuration(Val.AnimSpeedLED)
        self.color_anim.valueChanged.connect(self._on_color_change)

        # Pins
        if self._setupDefaultPins:
            s = self.getRelSize()[0]
            self.addInputPin(CompEdge.INPUT, s // 2)
            self.updateShape()

        self.inputPin = cast(InputPinItem, self._pinslist[CompEdge.INPUT][0])
        self.inputPin.setLogical(self._unit, 0)

    # ── Shape ─────────────────────────────────────────────────────────────────

    def _updateShape(self):
        super()._updateShape()
        s = self.getRelSize()[0]
        fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
        self.inputPin.facing = fa
        self.setPinPos(self.inputPin, gen(s // 2))

    # ── Properties ────────────────────────────────────────────────────────────

    def getProperties(self) -> dict:
        dic = super().getProperties() | {
            Prop.LABEL : self.tag,
            Prop.STATE : self.state,
        }
        dic.pop(Prop.TAG)
        return dic

    def setProperty(self, prop: Prop, value) -> bool:
        if prop == Prop.LABEL:
            self.tag = str(value)
            if self._unit: self._unit.custom_name = self.tag
            self.updateShape()              # re-size circle to fit new label
            self.propertyChanged(); return True
        return super().setProperty(prop, value)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _on_color_change(self, color: QColor):
        self.current_color = color
        self.update()

    def unitStateChanged(self, state: int):
        self.state = state
        self.propertyChanged()

        Color = theme.get_theme()
        target = Color.LED_on if state == Const.HIGH else Color.LED_off

        if self.color_anim.endValue() != target:
            self.color_anim.stop()
            self.color_anim.setStartValue(self.current_color)
            self.color_anim.setEndValue(target)
            self.color_anim.start()

    def poll_update(self) -> bool:
        if self._unit is None: return False
        current = self._unit.output
        if self.prevState != current:
            self.prevState = current
            self.unitStateChanged(current)
            return True
        return False

    def proxyPin(self) -> InputPinItem | None:
        return None if self.inputPin.hasWire() else self.inputPin

    # ── Paint ─────────────────────────────────────────────────────────────────

    def draw(self, painter: QPainter, option, widget):
        Color  = theme.get_theme()
        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)  # type: ignore

        g_outline = Color.input_sel_outline if is_sel else Color.output_outline
        g_label   = Color.output_label

        pen_style = Qt.PenStyle.DashLine if is_sel else Qt.PenStyle.SolidLine
        painter.setPen(QPen(g_outline, 1.8, pen_style))
        painter.setBrush(QBrush(self.current_color))   # animated LED colour

        w, h = self.getAbsSize()
        body = QRectF(0, 0, w * GRID.SIZE, h * GRID.SIZE)
        painter.drawEllipse(body)

        painter.setPen(g_label)
        painter.setFont(Font.gate)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self.tag)