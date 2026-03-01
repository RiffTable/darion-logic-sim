import sys
import os
from typing import TYPE_CHECKING
sys.path.append(os.path.join(os.getcwd(), 'engine'))

# This is because pyright is having trouble importing without absolute paths
# but I can't bc that causes other *weird* issue
# This solution is beyond checky and will probably break >:3
if TYPE_CHECKING:
	from engine import Const
	from engine.Circuit import Circuit
	from engine.Gates import Gate, AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, InputPin, OutputPin
	from engine.IC import IC
else:
	import Const
	from Circuit import Circuit
	from Gates import Gate, AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, InputPin, OutputPin
	from IC import IC




logic = Circuit()
logic.simulate(Const.SIMULATE)
logic.set_UI_MODE(True)