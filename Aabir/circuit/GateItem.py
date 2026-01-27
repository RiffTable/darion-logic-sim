from __future__ import annotations
from typing import cast
from QtCore import *

from styles import (Color, Font)
from circuit.canvas import (CompItem)





###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
COMPONENT_LOOKUP: list[tuple[str, int, type[CompItem]]] = [
	("NOT Gate", 0, CompItem),
	("AND Gate", 1, CompItem),
	("NAND Gate", 2, CompItem),
	("OR Gate", 3, CompItem),
	("NOR Gate", 4, CompItem),
	("XOR Gate", 5, CompItem),
	("XNOR Gate", 6, CompItem),
]

Name_to_ID    : dict[str, int] = {}
ID_to_Name    : dict[int, str] = {}
ID_to_Class   : dict[int, type[CompItem]] = {}
Class_to_ID   : dict[type[CompItem], int] = {}
Name_to_Class : dict[str, type[CompItem]] = {}
Class_to_Name : dict[type[CompItem], str] = {}

for name_, id_, class_ in COMPONENT_LOOKUP:
	Name_to_ID[name_]     = {id_}
	ID_to_Name[id_]       = {name_}
	ID_to_Class[id_]      = {class_}
	Class_to_ID[class_]   = {id_}
	Name_to_Class[name_]  = {class_}
	Class_to_Name[class_] = {name_}


class GateItem(CompItem):
	def __init__(self, x, y):
		super().__init__(x, y)