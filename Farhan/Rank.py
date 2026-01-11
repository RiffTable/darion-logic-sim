from Gates import Variable,NOT,AND,NAND,OR,NOR,XOR,XNOR,Probe

class Rank:
    def __init__(self):
        self.ranker={Variable:0,NOT:0,AND:0,NAND:0,OR:0,NOR:0,XOR:0,XNOR:0,Probe:0}
        self.name_list={NOT:'NOT',AND:'AND',NAND:'NAND',OR:'OR',NOR:'NOR',XOR:'XOR',XNOR:'XNOR',Variable:'Variable',Probe:'Probe'}
    def get_name(self,cls):
        self.ranker[cls]+=1
        rank=self.ranker[cls]
        if cls==Variable:
            return chr('A'+(rank-1)%26)+str(rank)
        else:
            return self.name_list[cls]+str(rank)