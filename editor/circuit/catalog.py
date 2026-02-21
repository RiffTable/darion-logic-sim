from __future__ import annotations
from dataclasses import dataclass

from .compitem import CompItem
from .gates import GateItem, UnaryGateItem, InputItem, OutputItem
from .wireitem import WireItem
from .pins import PinItem, InputPinItem, OutputPinItem





@dataclass
class CompDetail:
	skin: type[CompItem]
	logic: int
	tag: str
	name: str
	desc: str


###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
LOOKUP: dict[int, CompDetail] = {
	0:  CompDetail(UnaryGateItem, 0, "NOT"  , "NOT Gate"          , ""),
	1:  CompDetail(GateItem,      1, "AND"  , "AND Gate"          , ""),
	2:  CompDetail(GateItem,      2, "NAND" , "NAND Gate"         , ""),
	3:  CompDetail(GateItem,      3, "OR"   , "OR Gate"           , ""),
	4:  CompDetail(GateItem,      4, "NOR"  , "NOR Gate"          , ""),
	5:  CompDetail(GateItem,      5, "XOR"  , "XOR Gate"          , ""),
	6:  CompDetail(GateItem,      6, "XNOR" , "XNOR Gate"         , ""),
	7:  CompDetail(InputItem,     7, "IN"   , "Input (Toggle)"    , ""),
	8:  CompDetail(OutputItem,    8, "LED"  , "LED"               , ""),

	51: CompDetail(InputItem,     7, "IN"   , "Input (Hold)"      , ""),
	52: CompDetail(InputItem,     7, ""     , "Rotary Switch"     , ""),
	53: CompDetail(InputItem,     7, "CLK"  , "Clock"             , ""),
	54: CompDetail(InputItem,     7, ""     , "Constant"          , ""),
	62: CompDetail(OutputItem,    8, "OSC"  , "Oscilloscope"      , ""),
	63: CompDetail(OutputItem,    8, ""     , "7-Segment Display" , ""),
	64: CompDetail(OutputItem,    8, ""     , "Hex Display"       , ""),
	# (11, "IC",        CompItem),
}