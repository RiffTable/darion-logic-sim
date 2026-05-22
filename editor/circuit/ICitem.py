from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import Facing, CompEdge
import editor.theme as theme
from editor.styles import Font

from .compitem import CompItem
from .pins import InputPin, OutputPin





class IC_Comp(CompItem):
    TAG = DESC = NAME = ""
    LOGIC = Const.IC_ID

    def __init__(self, pos: QPointF, ic_data_index: int|str, ic_data, **kwargs):
        self.ic_data_index = int(ic_data_index)
        self._unit = cast(IC, logic.load_ic(ic_data))

        pin_orientations = getattr(self._unit, 'pin_orientations', [[], []])
        has_orientations = any(pin_orientations)

        ninputs = len(self._unit.inputs)
        noutputs = len(self._unit.outputs)

        if has_orientations:
            edge_inputs = {e: [] for e in CompEdge}
            edge_outputs = {e: [] for e in CompEdge}
            
            for i, f_val in enumerate(pin_orientations[0]):
                edge = CompEdge((f_val + 2) % 4)
                edge_inputs[edge].append(i)
                
            for i, f_val in enumerate(pin_orientations[1]):
                edge = CompEdge(f_val % 4)
                edge_outputs[edge].append(i)
                
            n_horiz = max(len(edge_inputs[CompEdge.INPUT]) + len(edge_outputs[CompEdge.INPUT]), 
                          len(edge_inputs[CompEdge.OUTPUT]) + len(edge_outputs[CompEdge.OUTPUT]))
            n_vert = max(len(edge_inputs[CompEdge.TOP]) + len(edge_outputs[CompEdge.TOP]), 
                         len(edge_inputs[CompEdge.BOTTOM]) + len(edge_outputs[CompEdge.BOTTOM]))
                         
            w = 2 * n_vert if n_vert > 2 else 7
            h = 2 * n_horiz if n_horiz > 2 else 6
            w = max(w, 7)
            h = max(h, 6)
        else:
            n = max(ninputs, noutputs)
            h = 2*n if n > 2 else 6
            w = 7

        self.getRelSize = lambda: (w, h)
        self.getRelPadding = lambda: (0, 0)

        super().__init__(pos, **kwargs)

        self.tag = self._unit.tag

        # Pins Setup
        if self._setupDefaultPins:
            if has_orientations:
                for edge in CompEdge:
                    in_indices = edge_inputs[edge]
                    out_indices = edge_outputs[edge]
                    
                    total_pins = len(in_indices) + len(out_indices)
                    if total_pins == 0: continue
                    
                    length = h if edge in (CompEdge.INPUT, CompEdge.OUTPUT) else w
                    start = length // 2 + 1 - total_pins
                    fa, gen = self.getPinPosGenerator(edge)
                    
                    current_pos = start
                    for _ in in_indices:
                        self._pinslist[edge].append(InputPin(self, gen(current_pos), fa))
                        current_pos += 2
                    for _ in out_indices:
                        self._pinslist[edge].append(OutputPin(self, gen(current_pos), fa))
                        current_pos += 2
            else:
                start = h//2 + 1 - ninputs
                fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
                for i in range(ninputs):
                    self._pinslist[CompEdge.INPUT].append(
                        InputPin(self, gen(start + 2*i), fa)
                    )
                
                start = h//2 + 1 - noutputs
                fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
                for i in range(noutputs):
                    self._pinslist[CompEdge.OUTPUT].append(
                        OutputPin(self, gen(start + 2*i), fa)
                    )

        # Setting Pin Logicals
        self.input_pins = []
        self.output_pins = []
        
        if has_orientations:
            input_iters = {edge: (p for p in self._pinslist[edge] if isinstance(p, InputPin)) for edge in CompEdge}
            output_iters = {edge: (p for p in self._pinslist[edge] if isinstance(p, OutputPin)) for edge in CompEdge}
            
            for i, inpin in enumerate(self._unit.inputs):
                edge = CompEdge((pin_orientations[0][i] + 2) % 4)
                pin = next(input_iters[edge])
                pin.setLogical(inpin)
                self.input_pins.append(pin)
                
            for i, outpin in enumerate(self._unit.outputs):
                edge = CompEdge(pin_orientations[1][i] % 4)
                pin = next(output_iters[edge])
                pin.setLogical(outpin)
                self.output_pins.append(pin)
        else:
            for i, inpin in enumerate(self._unit.inputs):
                pin = cast(InputPin, self._pinslist[CompEdge.INPUT][i])
                pin.setLogical(inpin)
                self.input_pins.append(pin)

            for i, outpin in enumerate(self._unit.outputs):
                pin = cast(OutputPin, self._pinslist[CompEdge.OUTPUT][i])
                pin.setLogical(outpin)
                self.output_pins.append(pin)



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
                if isinstance(pin, OutputPin) and pin.logical is not None:
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
        painter.setFont(QFont("Consolas", 8, QFont.Weight.DemiBold))
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