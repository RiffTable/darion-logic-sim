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
    def __repr__(self):
        return self.name
        
    def __str__(self):
        return self.name
    
    def override(self,code):
        pass

    def turnon(self):
        return len(self.children[0])+len(self.children[1])+len(self.children[-1])>=self.inputlimit

    # operates on the inputs
    def process(self):
        pass
    
    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs
    def getoutput(self):
        if self.output==-1:
            x= '0<=>1'
        elif self.output==0:
            x= 'F'
        else:
            x= 'T'
        if self.turnon()==False:
            x+='*'
        return x

class Variable(Gate):
    # this can be both an input or output(bulb)
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)          
        self.inputlimit=1
        self.code='8'+str(Variable.rank)
        Variable.rank+=1
        self.children[0].add(self.circuit.sign_0)

    def override(self, code):
        self.code=code
        Variable.rank=max(Variable.rank,int(code[1:]))

    def process(self):
        if len(self.children[0]):
            out=0
        elif len(self.children[1]):
            out=1
        self.prev_output=self.output
        self.output=out

class NOT(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)        
        self.inputlimit=1
        NOT.rank+=1
        self.code='1'+str(NOT.rank)

    def override(self, code):
        self.code=code
        NOT.rank=max(NOT.rank,int(code[1:]))
    def process(self):
        if len(self.children[0]):
            out=1
        elif len(self.children[1]):
            out=0
        else:
            out=0
        self.prev_output=self.output
        self.output=out
        
        
class AND(Gate):

    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)       
        AND.rank+=1
        self.code='2'+str(AND.rank)

    def override(self, code):
        self.code=code
        AND.rank=max(AND.rank,int(code[1:]))
        
    def process(self):
        if len(self.children[0]):
            out=0
        elif len(self.children[1]):
            out=1
        else: 
            out=0
        self.prev_output=self.output
        self.output=out
        
        
class NAND(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        NAND.rank+=1
        self.code='3'+str(NAND.rank)
    
    def override(self, code):
        self.code=code
        NAND.rank=max(NAND.rank,int(code[1:]))
        
    def process(self):
        if len(self.children[0]):
            out=1
        elif len(self.children[1]):
            out=0
        else: 
            out=0
        self.prev_output=self.output
        self.output=out
        

class OR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)         
        OR.rank+=1
        self.code='4'+str(OR.rank)
        
    def override(self, code):
        self.code=code
        OR.rank=max(OR.rank,int(code[1:]))        
        
    def process(self):
        if len(self.children[1]):
            out=1
        else: 
            out=0
        self.prev_output=self.output
        self.output=out
        
class NOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        NOR.rank+=1
        self.code='5'+str(NOR.rank)    

    def override(self, code):
        self.code=code
        NOR.rank=max(NOR.rank,int(code[1:]))

    def process(self):
        if len(self.children[1]):
            out=0
        elif len(self.children[0]):
            out=1
        else: 
            out=0
        # output needs to be updated first
        self.prev_output=self.output
        self.output=out
        
class XOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)       
        XOR.rank+=1
        self.code='6'+str(XOR.rank)
    
    def override(self, code):
        self.code=code
        XOR.rank=max(XOR.rank,int(code[1:]))
        
    def process(self):
        out=int(len(self.children[1])%2)
        self.prev_output=self.output
        self.output=out
        
class XNOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        XNOR.rank+=1
        self.code='7'+str(XNOR.rank)
    
    def override(self, code):
        self.code=code
        XNOR.rank=max(XNOR.rank,int(code[1:]))
        
    def process(self):
        out=int(len(self.children[1])%2==0)
        self.prev_output=self.output
        self.output=out
        
