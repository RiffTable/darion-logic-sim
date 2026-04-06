from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import Facing, CompEdge
import editor.theme as theme
from editor.styles import Font

from .compitem import CompItem
from .pins import InputPinItem, OutputPinItem





class ICitem(CompItem):
    TAG = DESC = NAME = ""
    LOGIC = Const.IC_ID

    def __init__(self, pos: QPointF, ic_data_index: int|str, ic_data, **kwargs):
        self.ic_data_index = int(ic_data_index)
        self._unit = cast(IC, logic.load_ic(ic_data))
        # self._unit = cast(IC, logic.load_ic(self.cscene.iclist[ic_data_index]))

        # Dimension Setup
        ninputs = len(self._unit.inputs)
        noutputs = len(self._unit.outputs)
        n = max(ninputs, noutputs)
        h = 2*n if n > 2 else 6
        
        self.getRelSize = lambda: (7, h)
        self.getRelPadding = lambda: (0, 0)

        super().__init__(pos, **kwargs)

        self.tag = self._unit.tag

        # Pins Setup
        if self._setupDefaultPins:
            start = h//2 + 1 - ninputs
            fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
            for i in range(ninputs):
                self._pinslist[CompEdge.INPUT].append(
                    InputPinItem(self, gen(start + 2*i), fa)
                )
            
            start = h//2 + 1 - noutputs
            fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
            for i in range(noutputs):
                self._pinslist[CompEdge.OUTPUT].append(
                    OutputPinItem(self, gen(start + 2*i), fa)
                )

        # Setting Pin Logicals
        for i, inpin in enumerate(self._unit.inputs):
            pin = cast(InputPinItem, self._pinslist[CompEdge.INPUT][i])
            pin.setLogical(inpin)

        for i, outpin in enumerate(self._unit.outputs):
            pin = cast(OutputPinItem, self._pinslist[CompEdge.OUTPUT][i])
            pin.setLogical(outpin)



    ### Properties Data
    def getData(self):
        return super().getData() | {
            "ic_data_index": self.ic_data_index
        }

    def poll_update(self) -> bool:
        if self._unit is None: return False

        changed = False
        for pinlist in self._pinslist.values():
            for pin in pinlist:
                if isinstance(pin, OutputPinItem) and pin.logical is not None:
                    current = pin.logical.output
                    if current != pin.state:
                        pin.logicalStateChanged(current)
                        changed = True
        return changed
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        if self._dirty: self._updateShape(); self._dirty = False


        Color = theme.get_theme()
        if option.state & QStyle.StateFlag.State_Selected:    # type: ignore ; fuck off pyright
            painter.setPen(QPen(Color.hl_text_bg, 2, Qt.PenStyle.DashLine))
        else:
            painter.setPen(QPen(Color.outline, 2))
        painter.setBrush(Color.comp_body)
        painter.drawRect(self._rect)


        # Tag at the Center
        AFlag = Qt.AlignmentFlag
        painter.setPen(Color.text)
        painter.setFont(Font.default)
        painter.drawText(self._rect, AFlag.AlignCenter, self.tag)


        # Labels
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        for edge, pins in self._pinslist.items():
            fa = self.edgeToFacing(edge)

            # Position
            match fa:
                case Facing.EAST:
                    align = AFlag.AlignVCenter | AFlag.AlignRight
                    rect = QRect(-40, -20, 40, 40)
                    
                case Facing.WEST:
                    align = AFlag.AlignVCenter | AFlag.AlignLeft
                    rect = QRect(0, -20, 40, 40)
                    
                case Facing.NORTH:
                    align = AFlag.AlignHCenter | AFlag.AlignTop
                    rect = QRect(-20, 0, 40, 40)
                    
                case Facing.SOUTH:
                    align = AFlag.AlignHCenter | AFlag.AlignBottom
                    rect = QRect(-20, -40, 40, 40)
            
            for pin in pins:
                
                # Logical
                logical = pin.logical
                if logical is None:
                    continue
                logical = logical[0] if isinstance(logical, tuple) else logical
                
                # Text
                font = painter.font()
                text = logical.custom_name

                if text.startswith("~"):
                    font.setOverline(True)
                    text = text[1:]
                else:
                    font.setOverline(False)
                painter.setFont(font)

                # Positioning
                center = pin.pos() + fa.toPointF(-8)
                prect = rect.translated(center.toPoint())

                painter.drawText(prect, align, text)
                # print(f"Pin '{logical.custom_name}' aligned '{align}' when '{fa}' at '{center}'")