from __future__ import annotations
from typing import cast
from QtCore import *

from styles import (Color, Font)
from Items import (CompItem)





###======= LOOKUP TABLE FOR ALL COMPONENTS =======###
GATELOOKUP: list[tuple[str, str, type[CompItem]]] = [
	("AND Gate", "and-gate", CompItem),
	("OR Gate", "or-gate", CompItem),
	("NOT Gate", "not-gate", CompItem),
	("NOR Gate", "nor-gate", CompItem),
	("NAND Gate", "nand-gate", CompItem),
	("XOR Gate", "xor-gate", CompItem),
	("XNOR Gate", "xnor-gate", CompItem),
]

Name_to_ID    : dict[str, str] = {}
ID_to_Name    : dict[str, str] = {}
ID_to_Class   : dict[str, type[CompItem]] = {}
Class_to_ID   : dict[type[CompItem], str] = {}
Name_to_Class : dict[str, type[CompItem]] = {}
Class_to_Name : dict[type[CompItem], str] = {}

for name_, id_, class_ in GATELOOKUP:
	Name_to_ID[name_]     = {id_}
	ID_to_Name[id_]       = {name_}
	ID_to_Class[id_]      = {class_}
	Class_to_ID[class_]   = {id_}
	Name_to_Class[name_]  = {class_}
	Class_to_Name[class_] = {name_}


class GateItem(CompItem):
	def __init__(self, x, y):
		super().__init__(x, y)

		self.tail = []
		self.head = []
		self.top = []
		self.bottom = []