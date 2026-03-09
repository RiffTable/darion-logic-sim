
from Gates import Gate
from IC import IC
from Const import IC_ID
namelist=(
    'AND',
    'NAND',
    'OR',
    'NOR',
    'XOR',
    'XNOR',
    'NOT',
    'Variable',
    'Probe',
    'In',
    'Out',
    'IC',
)

def get(choice):
    if choice==IC_ID:return IC(choice,namelist[choice])
    else:return Gate(choice,namelist[choice])
