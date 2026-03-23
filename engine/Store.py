
from Gates import Gate
from IC import IC
from Const import IC_ID,DEBUG
namelist=(
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

def get(choice):
    if DEBUG:
        if choice==IC_ID:return IC(choice,namelist[choice])
        else:return Gate(choice,namelist[choice])
    else:
        if choice==IC_ID:return IC(choice,None)
        else:return Gate(choice,None)
