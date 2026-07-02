from __future__ import annotations
import math
from typing import cast
from core.QtCore import *
from PySide6.QtGui import QFontMetrics
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Prop
from editor import theme
from editor.styles import Font
import core.grid as GRID

from .compitem import CompItem
from .pins import PinItem, InputPin, OutputPin


# ─────────────────────────────────────────────────────────────────────────────
# InputItem
# ─────────────────────────────────────────────────────────────────────────────

class InputComp(CompItem):
    TAG   = "IN"
    LOGIC = Const.VARIABLE_ID
    NAME  = DESC = "INPUT"

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, pos: QPointF, **kwargs):
        self.rLength, self.rBreadth = (4, 4)
        super().__init__(pos, **kwargs)
        self._custom_draw = True   # we handle body + text ourselves

        # Properties
        self.state          = int(kwargs.get("state",         Const.LOW))
        self.prevState      = -1
        self.is_clock       = bool(kwargs.get("is_clock",     False))
        self.delay_primary  = int(kwargs.get("delay_primary", 0))
        self.delay_high     = int(kwargs.get("delay_high",    0))
        self.delay_low      = int(kwargs.get("delay_low",     0))

        # Pins
        if self._setupDefaultPins:
            s = self.rLength
            self.addOutputPin(CompEdge.OUTPUT, s // 2)
            self.updateShape()

        self.outputPin = cast(OutputPin, self._pinslist[CompEdge.OUTPUT][0])
        self.outputPin.setLogical(self._unit)
        self.outputPin.logicalStateChanged(self.state)

        self.setState(self.state == Const.HIGH)
        self._apply_pulse_settings()

    # ── Shape (pin repositioned on every updateShape) ─────────────────────────

    def _updateShape(self):
        super()._updateShape()
        # Reposition output pin to the true centre of the output edge.
        s = self.rLength
        fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
        self.outputPin.facing = fa
        self.setPinPos(self.outputPin, gen(s // 2))

    # ── Properties ────────────────────────────────────────────────────────────

    def getData(self):
        return super().getData() | {
            "state"         : self.state,
            "is_clock"      : self.is_clock,
            "delay_primary" : self.delay_primary,
            "delay_high"    : self.delay_high,
            "delay_low"     : self.delay_low,
        }

    def getProperties(self) -> dict:
        dic = super().getProperties() | {
            Prop.LABEL         : self.tag,
            Prop.STATE         : self.state,
            Prop.DELAY_PRIMARY : self.delay_primary,
            Prop.DELAY_HIGH    : self.delay_high,
            Prop.DELAY_LOW     : self.delay_low,
            Prop.IS_CLOCK      : self.is_clock,
        }
        dic.pop(Prop.TAG)
        return dic

    def setProperty(self, prop: Prop, value) -> bool:
        match prop:
            case Prop.LABEL:
                self.tag = str(value)
                if self._unit: self._unit.custom_name = self.tag
                self.updateShape()          # re-size circle to fit new label
                self.propertyChanged(); return True
            case Prop.DELAY_PRIMARY:
                self.delay_primary = max(0, int(value))
                self._unit.set_pulse(self.delay_primary, Const.PRIMARY)
                self.propertyChanged(); return True
            case Prop.DELAY_HIGH:
                self.delay_high = max(0, int(value))
                self._unit.set_pulse(self.delay_high, Const.HIGH)
                self.propertyChanged(); return True
            case Prop.DELAY_LOW:
                self.delay_low = max(0, int(value))
                self._unit.set_pulse(self.delay_low, Const.LOW)
                self.propertyChanged(); return True
            case Prop.IS_CLOCK:
                self.is_clock = bool(value)
                if self.is_clock:
                    self._unit.clock()
                else:
                    self._unit.inputlimit = 1
                self.update()               # circle ↔ square shape switch
                self.propertyChanged(); return True
        return super().setProperty(prop, value)

    def _apply_pulse_settings(self):
        if self._unit is None: return
        self._unit.set_pulse(self.delay_primary, Const.PRIMARY)
        self._unit.set_pulse(self.delay_high,    Const.HIGH)
        self._unit.set_pulse(self.delay_low,     Const.LOW)
        if self.is_clock:
            self._unit.clock()

    def unitStateChanged(self, state: int):
        self.state = state
        self.outputPin.logicalStateChanged(state)
        self.propertyChanged()

    def poll_update(self) -> bool:
        if self._unit is None: return False
        current = self._unit.value
        if self.prevState != current:
            self.prevState = current
            self.unitStateChanged(current)
            return True
        return False

    def setState(self, state: bool):
        logic.toggle(self._unit, state)
        self.update()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == MouseBtn.LeftButton:
            delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
            if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
                self.setState(not self.state)
            return super().mouseReleaseEvent(event)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def draw(self, painter: QPainter, option, widget):
        Color    = theme.get_theme()
        is_sel   = bool(option.state & QStyle.StateFlag.State_Selected)  # type: ignore
        is_high  = (self.state == Const.HIGH)

        g_body    = Color.comp_active if is_high else Color.comp_body
        g_outline = Color.hl_text_bg  if is_sel  else Color.outline
        pen_style = Qt.PenStyle.DashLine if is_sel else Qt.PenStyle.SolidLine

        painter.setPen(QPen(g_outline, 2, pen_style))
        painter.setBrush(g_body)

        w, h = self.getAbsSize()
        body = QRectF(0, 0, w * GRID.SIZE, h * GRID.SIZE)

        if self.is_clock:
            r = GRID.SIZE * 0.5
            painter.drawRoundedRect(body, r, r)
        else:
            painter.drawEllipse(body)

        painter.setPen(Color.text)
        painter.setFont(Font.default)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self.tag)