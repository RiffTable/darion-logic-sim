from __future__ import annotations

from .compitem import CompItem
from .gates import (GateItem,
	NOTGate, ANDGate, NANDGate, ORGate, NORGate, XORGate, XNORGate
)
from .inputs import InputItem
from .outputs import OutputItem
from .wireitem import WireItem
from .pins import PinItem, InputPinItem, OutputPinItem







###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
# LOOKUP: dict[int, CompDetail] = {
# 	0:  CompDetail(NOTGate,       0, "NOT"  , "NOT Gate"          , ""),
# 	1:  CompDetail(ANDGate,       1, "AND"  , "AND Gate"          , ""),
# 	2:  CompDetail(NANDGate,      2, "NAND" , "NAND Gate"         , ""),
# 	3:  CompDetail(ORGate,        3, "OR"   , "OR Gate"           , ""),
# 	4:  CompDetail(NORGate,       4, "NOR"  , "NOR Gate"          , ""),
# 	5:  CompDetail(XORGate,       5, "XOR"  , "XOR Gate"          , ""),
# 	6:  CompDetail(XNORGate,      6, "XNOR" , "XNOR Gate"         , ""),
# 	7:  CompDetail(InputItem,     7, "IN"   , "Input (Toggle)"    , ""),
# 	8:  CompDetail(OutputItem,    8, "LED"  , "LED"               , ""),

# 	51: CompDetail(InputItem,     7, "IN"   , "Input (Hold)"      , ""),
# 	52: CompDetail(InputItem,     7, ""     , "Rotary Switch"     , ""),
# 	53: CompDetail(InputItem,     7, "CLK"  , "Clock"             , ""),
# 	54: CompDetail(InputItem,     7, ""     , "Constant"          , ""),
# 	62: CompDetail(OutputItem,    8, "OSC"  , "Oscilloscope"      , ""),
# 	63: CompDetail(OutputItem,    8, ""     , "7-Segment Display" , ""),
# 	64: CompDetail(OutputItem,    8, ""     , "Hex Display"       , ""),
# 	# (11, "IC",        CompItem),
# }

LOOKUP: dict[int, type[CompItem]] = {
	0: NOTGate,
	1: ANDGate,
	2: NANDGate,
	3: ORGate,
	4: NORGate,
	5: XORGate,
	6: XNORGate,
}

# Setting up ID for all components
for i, comp in LOOKUP.items():
	comp.ID = i