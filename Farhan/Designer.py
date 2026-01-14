from Gates import InputPin, OutputPin, Variable,Gate,Probe,NOT
from Circuit import Circuit

class Design(Circuit):
    def __init__(self):
        super().__init__()
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
            gates=event[2]
            for i in gates:
                gate=self.getobj(i)
                self.terminate(gate)
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
            gates=event[1]
            super().copy(gates)
            super().paste()




    def addcomponent(self,gate_option)->Gate:
        gate=self.getcomponent(gate_option)
        self.addtoundo((1,gate))
        return gate

    def livehide(self, gate):
        self.hideComponent(gate)
        self.addtoundo((2,gate))

    def liveconnect(self, parent:Gate, child:Gate):
        if parent.inputpoint==False or child.outputpoint==False or parent.turnon():
            return False
        self.connect(parent, child)
        self.addtoundo((3,parent,child))
        return True
    
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
            source=self.copydata.keys()
            gates=super().paste()           
            self.addtoundo((5,source,gates))

    def load(self,file_location):
        # self.clearcircuit()
        self.undolist.clear()
        self.redolist.clear()
        self.readfromjson(file_location)
        
    def save(self,file_location):
        self.writetojson(file_location)

    def __str__(self):
        return 'Designer'
    def __repr__(self):
        return 'Designer'
    
