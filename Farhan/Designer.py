from Gates import *
from Circuit import Circuit

class Design(Circuit):
    def __init__(self):
        super().__init__()
        self.stage=list()
        self.history={}
        self.undolist=[]
        self.redolist=[]



    def addtoundo(self,token):
        self.undolist.append(token)
        self.redolist=[]
    def popfromundo(self):
        x=self.undolist.pop()
        self.redolist.append(x)
        return x
    def popfromredo(self):
        x=self.redolist.pop()
        self.undolist.append(x)
        return x
    
    def undo(self):
        if len(self.undolist)==0:
                return
        event=self.popfromundo()
        command =event[0]            

        if command==1:
            super().hideComponent(event[1])

        elif command==2:
            super().renewComponent(event[1])

        elif command==3:
            gate1=event[1]
            if isinstance(gate1,Variable):
                self.connect(gate1,self.sign_1 if gate1.output==0 else self.sign_0)
                return
            gate2=event[2]              
            super().disconnect(gate1,gate2)

        elif command==4:
            super().connect(event[1],event[2])

        elif command==5:
            gates=event[2].split(',')
            for i in gates:
                gate=self.getobj(i)
                super().hideComponent(gate)
                del self.circuit_breaker[gate]
                del self.objlist[gate.code]
            self.rank_reset()

    def redo(self):
        if len(self.redolist)==0:
                return
        event=self.popfromredo()
        command =event[0]   

        if command==1:
            self.renewComponent(event[1])
            
        elif command==2:
            self.hideComponent(event[1])
            
        elif command==3:
            gate1=event[1]
            if isinstance(gate1,Variable):
                self.connect(gate1,self.sign_1 if gate1.output==0 else self.sign_0)
                return
            gate2=event[2]              
            self.connect(gate1,gate2)
            
        elif command==4:
            self.disconnect(event[1],event[2])

        elif command==5:
            gates=event[1].split(',')
            super().copy(gates)
            super().paste()




    def addcomponent(self,gate_option):
        gate=self.getcomponent(gate_option,'')
        self.solder(gate)
        self.addtoundo((1,gate))

    def livehide(self, gate):
        self.hideComponent(gate)
        self.addtoundo((2,gate))

    def liveconnect(self, parent, child):
        self.connect(parent, child)
        self.addtoundo((3,parent,child))
    
    def input(self,var,value):
        self.connect(var, self.sign_1 if value=='1' else self.sign_0)
        self.addtoundo((3,var))

    def livedisconnect(self, parent, child):
        self.disconnect(parent, child)
        self.addtoundo((4,parent,child))
    
    def copy(self,components):
        super().copy(components)

    def paste(self):
        if len(self.copydata):
            source=self.copydata[0]
            gates=super().paste()
            gates=','.join(gates)
            self.addtoundo((5,source,gates))

    def load(self,file_location):
        self.clearcircuit()
        self.undolist.clear()
        self.redolist.clear()
        self.readfromfile(file_location)
        
    def importfromfile(self,file_location):
        self.readfromfile(file_location)

    def save(self,file_location):
        self.writetofile(file_location)



        
    def stage_gate(self,i,code):
        gate=self.getcomponent(i,code)
        self.stage.append(gate)

    def liststage(self):
        for i in range(len(self.stage)):
            print(f'{i}. {self.stage[i]}')
            
    def stage_delete(self,gate:Gate):
        if gate in self.stage: # i won't simulate gates not in stage
            self.stage.remove(gate)
        if gate in self.canvas:
            self.history[(gate,)]=2

    def stage_renew(self,gate:Gate):
        key=(gate,)
        self.stage.append(gate)
        if key in self.history:
            self.history.pop(key,None)
        
    def stage_connect(self,parent:Gate,child:Gate):
        if isinstance(parent,Variable):
            return
        key=(parent,child)
        if key in self.history and self.history[key]==4:
            self.history.pop(key,None)
        elif parent not in child.parents:
            self.history[key]=3

    def stage_disconnect(self,parent:Gate,child:Gate):
        if isinstance(parent,Variable):
            return
        key=(parent,child)
        if key in self.history and self.history[key]==3:
            self.history.pop(key,None)
        elif parent in child.parents:
            self.history[key]=4

    def simulate(self):
        gates=[ gate for gate in self.stage if gate not in self.canvas]
        for gate in gates:
            self.solder(gate)
        for key,val in self.history.items():
            if len(key)==2 and key[0] in self.stage and key[1] in self.stage:
                if val==3:
                    self.connect(key[0],key[1])
                else:
                    self.disconnect(key[0],key[1])      
            elif len(key)==1:
                if val==2:
                    self.hideComponent(key[0])  
        self.history={}




    def __str__(self):
        return 'Designer'
    def __repr__(self):
        return 'Designer'
    
