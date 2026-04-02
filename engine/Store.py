
from Gates import Gate
from IC import IC
from Const import IC_ID, VARIABLE_ID, DEBUG

namelist = (
    'AND',
    'NAND',
    'OR',
    'NOR',
    'XOR',
    'XNOR',
    'Variable',
    'NOT',
    'Probe',
    'In',
    'Out',
    'IC',
)

# Shared mutable location counter — a single-element list so it acts as a
# pointer/reference that both Circuit.getcomponent and IC.getcomponent share.
_loc: list = [0]

def get(choice: int):
    if choice == IC_ID:
        return IC(choice, namelist[choice] if DEBUG else None)
    else:
        gate = Gate(choice, namelist[choice] if DEBUG else None)
        gate.location = _loc[0]
        _loc[0] += 1
        return gate

def reset_loc():
    """Reset the location counter (call when clearing the circuit entirely)."""
    _loc[0] = 0
