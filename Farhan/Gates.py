from collections import deque
gatelist=['NOT', 'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR','Variable','Probe']
class Signal:
    # default signals that exist indepdently
    def __init__(self,circuit,value):
        self.circuit=circuit
        self.parents=set()
        self.output=value
        self.name=str(value)
        self.code='0'+self.name
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name

class Gate:   
    def __init__(self,circuit):
        # a gate needs holders from the circuit
        self.circuit=circuit

        # gate's children or inputs
        self.children=[set() for i in range(3)]
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

    def decode(self,code):
        gate=int(code[0])
        if(gate==8):
            order=int(code[1:])
            return chr(ord('A')+(order-1)%26)+str(order//26)
        elif gate==0:
            return code[1:]
        else:
            gate-=1
            return gatelist[gate]+'-'+code[1:]    
        
    def __repr__(self):
        return self.name
        
    def __str__(self):
        return self.name
    
    def connect(self,child:'Gate'):
        val=child.output  
        if val==-1:
            child.parents.add(self)
            self.children[-1].add(child)
            self.poison()
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
                    fuse[key]=parent.output
                    for grandparent in parent.parents:
                        queue.append((grandparent,parent))
                elif fuse[key]!=parent.output and (child,parent) in fuse:
                    parent.poison()
                    return

    def poison(self):
        queue=deque()
        queue.append(self)
        while len(queue):
            gate=queue.popleft()
            gate.output=-1
            for parent in gate.parents:            
                parent.children[-1].add(gate)
                parent.children[0].discard(gate)
                parent.children[1].discard(gate)
                if parent.output!=-1:
                    queue.append(parent)
    
    def hide(self):
        for parent in self.parents:# disconnect from parents and they will modify their output 
            parent.children[self.output].discard(self)
        for child in self.children[0]:# disconnect from children
            child.parents.discard(self)
        for child in self.children[1]:
            child.parents.discard(self)  
        for child in self.children[-1]:
            child.parents.discard(self)               
        for parent in self.parents:# disconnect from parents and they will modify their output 
            parent.process()
            parent.propagate()

    def reveal(self):
        if self.output==-1:
                self.poison()
        else:
            for parent in self.parents:# disconnect from parents and they will modify their output 
                parent.connect(self)
        for child in self.children[0]:
            child.parents.add(self)
        for child in self.children[1]:
            child.parents.add(self)   
        for child in self.children[-1]:
            child.parents.add(self)


    def turnon(self):
        return len(self.children[0])+len(self.children[1])+len(self.children[-1])>=self.inputlimit

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
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)          
        self.inputlimit=1
        self.children[0].add(self.circuit.sign_0)
        if code=='':
            Variable.rank+=1
            self.code='8'+str(Variable.rank)
        else:
            self.code=code
            Variable.rank=max(Variable.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def connect(self,child:Signal):
        self.children[self.output]=set()
        self.children[child.output].add(child)
        self.process()

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[1])

class Probe(Gate):
    # this can be both an input or output(bulb)
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)          
        self.inputlimit=1
        if code=='':
            Probe.rank+=1
            self.code='9'+str(Probe.rank)
        else:
            self.code=code
            Probe.rank=max(Probe.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[1])

class NOT(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)        
        self.inputlimit=1
        if code=='':
            self.code='1'+str(NOT.rank)
            NOT.rank+=1
        else:     
            self.code=code
            NOT.rank=max(NOT.rank,int(code[1:]))
        self.name=self.decode(self.code)        
            

    def connect(self, child):
        if child.output==-1:
            child.parents.add(self)
            self.children[-1].add(child)
            self.poison()
            return
        if len(self.children[self.output]):
            dead_child=self.children[self.output].pop() 
            dead_child.parents.discard(self)

        if child in self.children[child.prev_output]:
            self.children[child.prev_output].discard(child)
        self.children[child.output].add(child)        

        # connect children to it as their parent
        if self not in child.parents:
            child.parents.add(self)
        self.process()

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[0])

        
class AND(Gate):

    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)       
        if code=='':
            AND.rank+=1
            self.code='2'+str(AND.rank)
        else:
            self.code=code
            AND.rank=max(AND.rank,int(code[1:]))
        self.name=self.decode(self.code)            

    def process(self):
        self.prev_output=self.output
        self.output=0 if len(self.children[0]) else 1

                
class NAND(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)   
        if code=='':
            NAND.rank+=1
            self.code='3'+str(NAND.rank)
        else:
            self.code=code
            NAND.rank=max(NAND.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=1 if len(self.children[0]) else 0

        
class OR(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)         
        if code=='':
            OR.rank+=1
            self.code='4'+str(OR.rank)
        else:
            self.code=code
            OR.rank=max(OR.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=1 if len(self.children[1]) else 0

        
class NOR(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)   
        if code=='':
            NOR.rank+=1
            self.code='5'+str(NOR.rank)
        else:
            self.code=code
            NOR.rank=max(NOR.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=0 if len(self.children[1]) else 1

        
        
class XOR(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)       
        if code=='':
            XOR.rank+=1
            self.code='6'+str(XOR.rank)
        else:
            self.code=code
            XOR.rank=max(XOR.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=len(self.children[1])%2

        
class XNOR(Gate):
    rank=0
    def __init__(self,circuit,code):
        super().__init__(circuit)   
        if code=='':
            XNOR.rank+=1
            self.code='7'+str(XNOR.rank)
        else:
            self.code=code
            XNOR.rank=max(XNOR.rank,int(code[1:]))
        self.name=self.decode(self.code)

    def process(self):
        self.prev_output=self.output
        self.output=(len(self.children[1])%2)^1 

        
        
