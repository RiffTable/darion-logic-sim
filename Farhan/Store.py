from Gates import *
from IC import IC
from Const import GateType


class Components:
    gateobjects = {GateType.NOT: NOT, GateType.AND: AND, GateType.NAND: NAND, GateType.OR: OR, GateType.NOR: NOR, GateType.XOR: XOR,
                   GateType.XNOR: XNOR, GateType.VARIABLE: Variable, GateType.PROBE: Probe, GateType.INPUT_PIN: InputPin, GateType.OUTPUT_PIN: OutputPin, GateType.IC: IC}

    @classmethod
    def get(cls, choice) -> Gate | IC:
        if choice not in cls.gateobjects:
            return None
        return cls.gateobjects[choice]()
