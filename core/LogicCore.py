import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'engine'))
from engine import Const
from engine.Circuit import Circuit
from engine.Gates import Gate, AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, InputPin, OutputPin
from engine.IC import IC


logic = Circuit()
logic.simulate(Const.FLIPFLOP)