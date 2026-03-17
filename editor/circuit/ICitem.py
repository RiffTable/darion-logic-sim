from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge

from .compitem import CompItem
from .pins import InputPinItem, OutputPinItem





class ICitem(CompItem):
	TAG = DESC = NAME = ""
	LOGIC = Const.IC_ID

	def __init__(self, pos: QPointF, ic_data_index: int, ic_data, **kwargs):
		self.ic_data_index = int(ic_data_index)
		self._unit = cast(IC, logic.load_ic(ic_data))
		# self._unit = cast(IC, logic.load_ic(self.cscene.iclist[ic_data_index]))

		# Dimension Setup
		ninputs = len(self._unit.inputs)
		noutputs = len(self._unit.outputs)
		n = max(ninputs, noutputs)
		h = 2*n if n > 2 else 6
		
		self.getRelSize = lambda: (6, h)
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