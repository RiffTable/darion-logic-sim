from Circuit import Circuit
class Manager:
    def __init__(self):
        self.base=Circuit()
        self.undolist=[]
        self.redolist=[]

    def addtoundo(self,undo,redo,token):
        undo.append(token)
        redo.clear
    def popfromundo(self,undo,redo):
        x=undo.pop()
        redo.append(x)
        return x
    def popfromredo(self,undo,redo):
        x=redo.pop()
        undo.append(x)
        return x

    def addcomponent(self,gate_option):
        gate=self.base.getcomponent(gate_option,'')
        token='1 '+gate
        self.addtoundo(self.undolist,self.redolist,token)

    def connect(self,parent,child):
        self.base.connect(parent, child)
        token='3 '+parent+' '+ child
        self.addtoundo(self.undolist,self.redolist,token)

    def disconnect(self,parent,child):
        self.base.disconnect(parent, child)
        token='4 '+parent+' '+ child
        self.addtoundo(self.undolist,self.redolist,token)

    def deletecomponent(self,gatelist):
        for gate in gatelist:
            self.base.deleteComponent(gate)
            self.base.complist.remove(gate)
            token='2 '+gate
            self.addtoundo(self.undolist,self.redolist,token)

    def input(self,var,value):
        value='0'+value
        if value not in self.base.getobj(var).children[int(value[1:])]:
            self.base.connect(var, value)
            token='3 '+var+' '+ '0'+value
            self.addtoundo(self.undolist,self.redolist,token)

    def output(self,gate):
        return self.base.getobj(gate).getoutput()

    def truthTable(self,):
        return self.base.truthTable()

    def undo(self,):
        if len(self.undolist)==0:
            return
        event=self.popfromundo(self.undolist,self.redolist)
        event=event.split()
        command =event[0]            

        if command=='1':
            gate=event[1]
            self.base.deleteComponent(gate)
            self.base.complist.remove(gate)

        elif command=='2':
            gate=event[1]
            self.base.renewComponent(gate)
            self.base.complist.append(gate)

        elif command=='3':
            gate1=event[1]
            gate2=event[2]
            if gate1[0]=='8' and gate2[0]=='0':
                gate_obj1=self.base.getobj(gate1)
                self.base.connect(gate1,'0'+str(gate_obj1.output^1))
            else:
                self.base.disconnect(gate1,gate2)

        elif command=='4':
            gate1=event[1]
            gate2=event[2]
            self.base.connect(gate1,gate2)

        elif command=='5':
            gates=event[2].split(',')
            for i in gates:
                self.base.deleteComponent(i)
                del self.base.circuit_breaker[i]
                del self.base.objlist[int(i[0])][i[1:]]
                self.base.complist.remove(i)
            self.base.rank_reset()

    def redo(self,):
        if len(self.redolist)==0:
            return
        event=self.popfromredo(self.undolist,self.redolist)
        event=event.split()
        command =event[0]   

        if command=='1':
            gate=event[1]
            self.base.renewComponent(gate)
            self.base.complist.append(gate)
            
        elif command=='2':
            gate=event[1]
            self.base.deleteComponent(gate)
            self.base.complist.remove(gate)
            
        elif command=='3':
            gate1=event[1]
            gate2=event[2]
            self.base.connect(gate1,gate2)
            
        elif command=='4':
            gate1=event[1]
            gate2=event[2]
            self.base.disconnect(gate1,gate2)

        elif command=='5':
            gates=event[1].split(',')
            self.base.copy(gates)
            self.base.paste()

    def copy(self,components):
        self.base.copy(components)

    def paste(self,):
        if len(self.base.copydata):
            source=self.base.copydata[0]
            gates=self.base.paste()
            gates=','.join(gates)
            self.addtoundo(self.undolist,self.redolist,'5 '+source+' '+gates)

    def load(self,file_location):
        self.base.clearcircuit()
        self.undolist.clear()
        self.redolist.clear()
        self.base.readfromfile(file_location)
        
    def importfromfile(self,file_location):
        self.base.readfromfile(file_location)

    def save(self,file_location):
        self.base.writetofile(file_location)


