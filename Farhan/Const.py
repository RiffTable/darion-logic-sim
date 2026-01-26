class Const:
    HIGH = 1
    LOW = 0
    ERROR = 2
    UNKNOWN = 3

    DESIGN = 0
    SIMULATE = 1
    FLIPFLOP = 2
    MODE = 0

    ADD = 1
    DELETE = 2
    CONNECT = 3
    DISCONNECT = 4
    PASTE = 5
    TOGGLE = 6

    LIMIT=100


class GateType:
    NOT = 0
    AND = 1
    NAND = 2
    OR = 3
    NOR = 4
    XOR = 5
    XNOR = 6
    VARIABLE = 7
    PROBE = 8
    INPUT_PIN = 9
    OUTPUT_PIN = 10
    IC = 11
