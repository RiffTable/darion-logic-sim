import Const
import Gates
from IC import IC


class Components:
    # A shelf where we keep all the component blueprints
    # This helps us create new gates by just asking for them by name
    gateobjects = {
        Const.NOT        : Gates.NOT,
        Const.AND        : Gates.AND,
        Const.NAND       : Gates.NAND,
        Const.OR         : Gates.OR,
        Const.NOR        : Gates.NOR,
        Const.XOR        : Gates.XOR,
        Const.XNOR       : Gates.XNOR,
        Const.VARIABLE   : Gates.Variable,
        Const.PROBE      : Gates.Probe,
        Const.INPUT_PIN  : Gates.InputPin,
        Const.OUTPUT_PIN : Gates.OutputPin,
        Const.IC         : IC
    }

    @classmethod
    def get(cls, choice) -> Gates.Gate | IC:
        if choice not in cls.gateobjects:
            return None
        return cls.gateobjects[choice]()
