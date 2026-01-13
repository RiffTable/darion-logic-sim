from collections import deque
from Enum import Enum
class Signal:
    # default signals that exist indepdently
    def __init__(self,value):
        self.parents=set()
        self.output=value
        self.name=str(value)
        self.code=(0,value)
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name

class Gate:   
    def __init__(self):
        # a gate needs holders from the circuit

        # gate's children or inputs
        self.children={Enum.LOW:set(),Enum.HIGH:set(),Enum.ERROR:set()}
        self.parents=set()
        # input limit
        self.inputlimit=2
        #default output
        self.output=0
        self.prev_output=0
        # each gate will have it's own unique id
        self.code=''
        self.name=''
    def rename(self,name):
        self.name=name
        
    def __repr__(self):
        return self.name
        
    def __str__(self):
        return self.name
    
    def connect(self,child:'Gate'):
        val=child.output  
        if val==Enum.ERROR:
            child.parents.add(self)
            self.children[Enum.ERROR].add(child)
            self.burn()
            return
        if child in self.children[child.prev_output]:
            self.children[child.prev_output].discard(child)
        self.children[val].add(child)      
        if self not in child.parents:
            child.parents.add(self)
        self.process()
    
    def disconnect(self,child:'Gate'):
        val=child.output
        if child in self.children[val]:
            self.children[val].discard(child)
            child.parents.discard(self)
            child.process()
            child.propagate()
            self.process()
            self.propagate()

    def propagate(self):
        fuse={}
        queue=deque()
        for parent in self.parents:
            queue.append((parent,self))
        while len(queue):
            key=queue.popleft()
            parent=key[0]
            child=key[1]
            parent.connect(child)
            if parent.prev_output!=parent.output:
                if key not in fuse:
                    fuse[key]=(parent.output,child.output)
                    for grandparent in parent.parents:                        
                        queue.append((grandparent,parent))
                elif fuse[key]!=(parent.output,child.output):
                    child.burn()
                    return


    def burn(self):
        queue=deque()
        queue.append(self)
        while len(queue):
            gate=queue.popleft()
            gate.output=Enum.ERROR
            for parent in gate.parents:            
                parent.children[Enum.ERROR].add(gate)
                parent.children[Enum.LOW].discard(gate)
                parent.children[Enum.HIGH].discard(gate)
                if parent.output!=Enum.ERROR:
                    queue.append(parent)
    
    def hide(self):
        for parent in self.parents:# disconnect from parents and they will modify their output 
            parent.children[self.output].discard(self)
        for child in self.children[Enum.LOW]:# disconnect from children
            child.parents.discard(self)
        for child in self.children[Enum.HIGH]:
            child.parents.discard(self)  
        for child in self.children[Enum.ERROR]:
            child.parents.discard(self)               
        for parent in self.parents:# disconnect from parents and they will modify their output 
            parent.process()
            parent.propagate()

    def reveal(self):
        if self.output==Enum.ERROR:
                self.burn()
        else:
            for parent in self.parents:# disconnect from parents and they will modify their output 
                parent.connect(self)
            for parent in self.parents:# disconnect from parents and they will modify their output 
                parent.propogate()
        for child in self.children[Enum.LOW]:
            child.parents.add(self)
        for child in self.children[Enum.HIGH]:
            child.parents.add(self)   
        for child in self.children[Enum.ERROR]:
            child.parents.add(self)


    def turnon(self):
        return len(self.children[Enum.LOW])+len(self.children[Enum.HIGH])+len(self.children[Enum.ERROR])>=self.inputlimit

    # operates on the inputs
    def process(self):
        pass
    
    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs




    def getoutput(self):
        if self.turnon()==False:
            return 'X'
        elif self.output==-1:
            return '0/1'
        else:
            return 'T' if self.output else 'F'

class Variable(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):     
        super().__init__() 
        self.inputlimit=1

    def connect(self,child:Signal):
        self.children[self.output]=set()
        self.children[child.output].add(child)
        self.process()

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.HIGH])

class Probe(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1
        self.probetype=0
    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.HIGH])
class InputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1
    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.HIGH])
class OutputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1
    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.HIGH])

class NOT(Gate):

    def __init__(self):    
        super().__init__()
        self.inputlimit=1

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.LOW])

        
class AND(Gate):


    def __init__(self):
        super().__init__()
 
    def process(self):
        self.prev_output=self.output
        self.output=0 if len(self.children[Enum.LOW]) else 1

                
class NAND(Gate):

    def __init__(self):
        super().__init__()   

    def process(self):
        self.prev_output=self.output
        self.output=1 if len(self.children[Enum.LOW]) else 0

        
class OR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        self.output=1 if len(self.children[Enum.HIGH]) else 0

        
class NOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        self.output=0 if len(self.children[Enum.HIGH]) else 1

        
        
class XOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[Enum.HIGH])%2

        
class XNOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        self.output=(len(self.children[Enum.HIGH])%2)^1 

        
        
