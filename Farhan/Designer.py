from Gates import *
from Circuit import Circuit

class Design(Circuit):
    def __init__(self):
        super().__init__()
        self.history={}
    def raw_delete(self,parent:Gate):
        self.complist.remove(parent)

    def raw_renew(self,parent:Gate):
        self.complist.append(parent)
        
    def rawconnect(self,parent:Gate,child:Gate):
        if isinstance(parent,Variable):
            return
        key=(parent,child)
        if key in self.history and self.history[key]==4:
            self.history.pop(key,None)
        elif parent not in child.parents:
            self.history[key]=3

    def raw_disconnect(self,parent:Gate,child:Gate):
        if isinstance(parent,Variable):
            return
        key=(parent,child)
        if key in self.history and self.history[key]==3:
            self.history.pop(key,None)
        elif parent in child.parents:
            self.history[key]=4
    def simulate(self):
        for key,val in self.history.items():
            if key[0] in self.complist and key[1] in self.complist:
                if val==3:
                    self.connect(key[0],key[1])
                else:
                    self.disconnect(key[0],key[1])
        self.history={}
    def __str__(self):
        return 'Designer'
    def __repr__(self):
        return 'Designer'
    
