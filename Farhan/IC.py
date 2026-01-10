from Gates import Probe
class IC:
    rank=0
    def __init__(self):
        self.inputs=[]
        self.allgates=[]
        self.outputs=[]
        self.name=''
        IC.rank+=1
        self.code='IC'+str(IC.rank)
    def rename(self,name):
        self.name=name
    
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name