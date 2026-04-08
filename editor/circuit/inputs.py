from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Prop
from editor import theme

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem





class InputItem(CompItem):
    TAG="IN"
    LOGIC=Const.VARIABLE_ID
    NAME=DESC="INPUT"
    def getRelSize(self): return (4, 2)
    def getRelPadding(self): return (0, 4)

    def __init__(self, pos: QPointF, **kwargs):
        super().__init__(pos, **kwargs)

        # Properties
        self.state = int(kwargs.get("state", Const.LOW))
        self.prevState = -1

        # Timing / Clock properties (backed by gate.book[] and gate.clock())
        self.is_clock:     bool = bool(kwargs.get("is_clock", False))
        self.delay_primary: int = int(kwargs.get("delay_primary", 0))
        self.delay_high:    int = int(kwargs.get("delay_high",    0))
        self.delay_low:     int = int(kwargs.get("delay_low",     0))
        
        # Pins Setup
        if self._setupDefaultPins:
            self.addOutputPin(CompEdge.OUTPUT, 1)
            self.updateShape()
        
        # Pins Casting
        self.outputPin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][0])

        # Setting Pin logicals
        self.outputPin.setLogical(self._unit)
        self.outputPin.logicalStateChanged(self.state)

        # Final Setup
        self.setState(True if self.state == Const.HIGH else False)
        self._apply_pulse_settings()


    # Properties Data
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
                    # Restore inputlimit to 1 (non-clock mode)
                    self._unit.inputlimit = 1
                self.propertyChanged(); return True
        return super().setProperty(prop, value)

    def _apply_pulse_settings(self):
        """Push stored delay/clock values into the logic unit."""
        if self._unit is None:
            return
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
        
        current = self._unit.output
        if self.prevState != current:
            self.prevState = current
            self.unitStateChanged(current)
            return True
        return False
    
    def setState(self, state: bool):
        bookish = Const.HIGH if state else Const.LOW
        self.state = bookish
        logic.toggle(self._unit, bookish)
        self.update()


    
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == MouseBtn.LeftButton:
            delta = event.scenePos() - event.buttonDownScenePos(MouseBtn.LeftButton)
            if delta.manhattanLength() < QGuiApplication.styleHints().startDragDistance():
                self.setState(not self.state)
            return super().mouseReleaseEvent(event)
    
    def draw(self, painter, option, widget):
        # painter.setPen(QPen(Color.outline, 2))
        Color = theme.get_theme()
        if self.state == Const.HIGH:
            painter.setBrush(Color.comp_active)
        else:
            painter.setBrush(Color.comp_body)