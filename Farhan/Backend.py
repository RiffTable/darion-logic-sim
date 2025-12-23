

objlist={}
complist=[]
varlist=[]
circuit_breaker={}

class Signal:
    # default signals that exist indepdently
    def __init__(self,value):
        self.parents=set()
        self.output=value
    
objlist['0']=Signal(0)
objlist['1']=Signal(1)

class Gate:   

    def __init__(self):
        # gate's children or inputs
        self.children=[set(),set()]
        self.parents=set()
        # input limit
        self.inputlimit=2
        #default output
        self.output=0
        # each gate will have it's own unique id
        self.code=''
    # sets number of children
    def setlimits(self,l):
        self.inputlimit=l

    def turnon(self):
        return len(self.children[0])+len(self.children[1])>=self.inputlimit

    # connects gates
    def connect(self,child):
        val=objlist[child].output
        # secondary optimization
        # connect child to self
        if child in self.children[val]:
            return
        else:
            if isinstance(self,Variable) or isinstance(self,NOT):
                self.children[val].clear()
            self.children[val].add(child)
        if child in self.children[val^1]:
            self.children[val^1].discard(child)
        if isinstance(self,Variable) or isinstance(self,NOT):
            self.children[val^1].clear()

        # connect itself to children
        if isinstance(objlist[child],Signal)==False and self.code not in objlist[child].parents:
            objlist[child].parents.add(self.code)
        self.process()

    # deletes parent from the parent list
    def disconnect(self,node):    
        # check if node is a parent or a child
        # then delete accordingly
        val=objlist[node].output


        if node in self.parents:
            objlist[node].children[val].discard(self.code)
            objlist[node].process()
            self.parents.discard(node)
        elif node in self.children[val]:
            objlist[node].parents.discard(self.code)
            self.children[val].discard(node)
            self.process()
        else:
            print('Not Connected')
    def fix(self,node):
        objlist[node].parents.discard(self.code)
        self.children[0].discard(node)
        self.children[1].discard(node)
        self.process()
                    

    def update(self,prev,out):
        if circuit_breaker[self.code]==-1:
            circuit_breaker[self.code]=self.output
            if self.turnon() and prev!=out:
                for parent in self.parents:
                    objlist[parent].connect(self.code)
                    if objlist[parent].output==-1:
                        self.output=-1
                        break
            circuit_breaker[self.code]=-1
        elif circuit_breaker[self.code]==self.output:
            return
        else:
            print(f'{self.code} is unstable')
            self.output=-1

    def process(self):
        pass

    # gives output in T or F
    def display_output(self):
        if self.turnon()==False:
            return 'OFF'
        elif self.output==0:
            return 'F'
        else:
            return 'T'


class Variable(Gate):
    # this can be both an input or output(bulb)
    rank=0
    def __init__(self):
        super().__init__()        
        self.inputlimit=1
        self.code=chr(ord('A') + Variable.rank)
        Variable.rank+=1
        self.children[0].add('0')
    # no changing the limit
    def setlimits(self):
        pass
    def process(self):
        out=self.output
        if len(self.children[0]):
            out=0
        elif len(self.children[1]):
            out=1
        else:
            out=0
        prev=self.output
        self.output=out
        # may need to update when error
        self.update(prev,out)

        
class NOT(Gate):
    rank=0
    def __init__(self):
        super().__init__()        
        self.inputlimit=1
        NOT.rank+=1
        self.code='NOT-'+str(NOT.rank)

    # no changing the limit
    def setlimits(self):
        pass
    def process(self):
        out=self.output
        if len(self.children[0]):
            out=1
        elif len(self.children[1]):
            out=0
        else:
            out=0
        prev=self.output
        self.output=out
        self.update(prev,out)
        
class AND(Gate):

    rank=0
    def __init__(self):
        super().__init__()        
        AND.rank+=1
        self.code='AND-'+str(AND.rank)
    def process(self):
        out=self.output
        if len(self.children[0]):
            out=0
        elif len(self.children[1]):
            out=1
        else: 
            out=0
        prev=self.output
        self.output=out
        self.update(prev,out)

        
class NAND(Gate):
    rank=0
    # basically a not + and gate
    def __init__(self):
        super().__init__()
        NAND.rank+=1
        self.code='NAND-'+str(NAND.rank)
    def process(self):
        out=self.output
        if len(self.children[0]):
            out=1
        elif len(self.children[1]):
            out=0
        else: 
            out=0
        prev=self.output
        self.output=out
        self.update(prev,out)

class OR(Gate):
    rank=0
    def __init__(self):
        super().__init__()        
        OR.rank+=1
        self.code='OR-'+str(OR.rank)
    def process(self):
        out=self.output
        if len(self.children[1]):
            out=1
        else: 
            out=0
        prev=self.output
        self.output=out
        self.update(prev,out)

class NOR(Gate):
    rank=0
    def __init__(self):
        super().__init__()
        NOR.rank+=1
        self.code='NOR-'+str(NOR.rank)
    def process(self):
        out=self.output
        if len(self.children[1]):
            out=0
        elif len(self.children[0]):
            out=1
        else: 
            out=0
        # output needs to be updated first
        prev=self.output
        self.output=out
        self.update(prev,out)

class XOR(Gate):
    rank=0
    def __init__(self):
        super().__init__()        
        XOR.rank+=1
        self.code='XOR-'+str(XOR.rank)
    def process(self):
        out=int(len(self.children[1])%2)
        prev=self.output
        self.output=out
        self.update(prev,out)

class XNOR(Gate):
    rank=0
    def __init__(self):
        super().__init__()
        XNOR.rank+=1
        self.code='XNOR-'+str(XNOR.rank)
    def process(self):
        out=int(len(self.children[1])%2==0)
        prev=self.output
        self.output=out
        self.update(prev,out)


# inventory
def listComponent():
    for i in range(len(complist)):
        print(f'{i}. {complist[i]}')

def listVar():
    for i in range(len(varlist)):
        print(f'{i}. {varlist[i]}')

def addComponent():
    print("Choose a gate to add to the circuit:")
    print("1. NOT")
    print("2. AND")
    print("3. NAND")
    print("4. OR")
    print("5. NOR")  
    print("6. XOR")
    print("7. XNOR")
    print("8. Variable")     

    choice = input("Enter your choice: ").split()

    for i in choice:
        if i == '1':
            gt = NOT()
        elif i == '2':
            gt = AND()
        elif i == '3':
            gt = NAND()
        elif i == '4':
            gt = OR()
        elif i == '5':
            gt = NOR()                
        elif i == '6':
            gt = XOR()
        elif i == '7':
            gt = XNOR()
        elif i=='8':
            gt=Variable()
            varlist.append(gt.code)
        objlist[gt.code]=gt
        complist.append(gt.code)
        circuit_breaker[gt.code]=-1

def deleteComponent(gate):
    gate_obj=objlist[gate]
    for child in gate_obj.children[0]:
        objlist[child].parents.discard(gate)
    for child in gate_obj.children[1]:
        objlist[child].parents.discard(gate)
    for parent in gate_obj.parents:
        objlist[parent].diconnect(gate)
    del objlist[gate]
    
# wiring

def connect(gate,comp):
    objlist[gate].connect(comp)
def disconnect(gate,comp):
    objlist[gate].disconnect(comp)


# Result 
def output(gate):
    print(objlist[gate].display_output())


# Truth Table
def truthTable(gate):
    if gate in complist and gate not in varlist:
        bits=1<<len(varlist)
        for i in varlist:
            print(i,end=' ')
        print(gate)
        for i in range(bits):
            for j in range(len(varlist)):
                var=objlist[varlist[j]]
                bitpoint=int((i & (1<<(len(varlist)-j-1)))!=0)
                var.connect(str(bitpoint))
                print('T' if var.output else 'F',end=' ')
            print('T' if objlist[gate].output else 'F')

