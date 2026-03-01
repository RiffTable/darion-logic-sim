import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'engine'))
import Const
from Circuit import Circuit
from Gates import Gate, AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, InputPin, OutputPin
from IC import IC


logic = Circuit()
logic.simulate(Const.SIMULATE)
logic.set_UI_MODE(True)