from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, Prop
from editor.styles import Val
from editor import theme

from .compitem import CompItem
from .pins import PinItem, InputPinItem, OutputPinItem





class OutputItem(CompItem):
    TAG="OUT"
    LOGIC=Const.OUTPUT_PIN_ID
    NAME=DESC="LED"
    def getRelSize(self): return (4, 2)
    def getRelPadding(self): return (0, 4)

    def __init__(self, pos: QPointF, **kwargs):
        super().__init__(pos, **kwargs)

        # Properties
        self.state: int = Const.LOW
        self.prevState = -1

        # Color animation – prevents strobe on fast oscillators
        self.current_color: QColor = theme.get_theme().LED_off
        self.color_anim = QVariantAnimation()
        self.color_anim.setDuration(Val.AnimSpeedLED)
        self.color_anim.valueChanged.connect(self._on_color_change)
        
        # Pins Setup
        if self._setupDefaultPins:
            self.addInputPin(CompEdge.INPUT, 1)
            self.updateShape()
        
        # Pins Casting
        self.inputPin = cast(InputPinItem, self._pinslist[CompEdge.INPUT][0])

        # Setting Pin Logicals
        self.inputPin.setLogical(self._unit, 0)


    # Properties Data
    def getProperties(self) -> dict:
        dic = super().getProperties() | {
            Prop.LABEL   : self.tag,
            Prop.STATE   : self.state
        }
        dic.pop(Prop.TAG)
        return dic


    # Animation callback
    def _on_color_change(self, color: QColor):
        self.current_color = color
        self.update()  # Trigger repaint with the new intermediate color

    def unitStateChanged(self, state: int):
        self.state = state
        self.propertyChanged()

        Color = theme.get_theme()
        match state:
            case Const.HIGH:  target_color = Color.LED_on
            case Const.ERROR: target_color = Color.LED_on.darker(150)
            case _:           target_color = Color.LED_off

        if self.color_anim.endValue() != target_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(self.current_color)
            self.color_anim.setEndValue(target_color)
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

    def draw(self, painter, option, widget):
        # Paint using the animated tween color (not the raw logic state)
        painter.setBrush(QBrush(self.current_color))