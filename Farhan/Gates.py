from __future__ import annotations
from collections import deque
from Const import Const

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
        # gate's children or inputs
        self.children={Const.LOW:set(),Const.HIGH:set(),Const.ERROR:set(),Const.UNKNOWN:set()}
        self.parents=set()
        # input limit
        self.inputlimit=2
        #default output
        self.output=Const.UNKNOWN
        self.prev_output=Const.UNKNOWN
        # each gate will have it's own unique id
        self.code=''
        self.name=''
        self.custom_name=''

        self.inputpoint=True
        self.outputpoint=True

    def process():
        pass
    
    def rename(self,name):
        self.name=name
        
    def __repr__(self):
        return self.name if self.custom_name=='' else self.custom_name
        
    def __str__(self):
        return self.name if self.custom_name=='' else self.custom_name
    
    def isready(self):
        if Const.MODE==Const.DESIGN:
            return False
        else:
            realchild=len(self.children[Const.HIGH])+len(self.children[Const.LOW])+len(self.children[Const.ERROR])
            if Const.MODE==Const.SIMULATE:
                return realchild==self.inputlimit
        return realchild and realchild+len(self.children[Const.UNKNOWN])==self.inputlimit        
        
    def connect(self,child:Gate):
        if child.output==Const.ERROR:
            child.parents.add(self)
            child.burn()
        if child in self.children[child.output]:
            return
        if child in self.children[child.prev_output]:
            self.children[child.prev_output].discard(child)
        self.children[child.output].add(child)
        if self not in child.parents:
            child.parents.add(self)
        self.process()
    
    def burn(self):
        queue=deque()
        queue.append(self)
        while len(queue):
            gate=queue.popleft()
            gate.output=-1
            for parent in gate.parents:            
                parent.children[Const.HIGH].discard(gate)
                parent.children[Const.LOW].discard(gate)
                parent.children[Const.ERROR].add(gate)
                if parent.isready() and parent.output!=Const.ERROR:
                    queue.append(parent)

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
                
    def disconnect(self,child:Gate):
        val=child.output
        if child in self.children[val]:
            self.children[val].discard(child)
            child.parents.discard(self)
            child.process()
            child.propagate()
            self.process()
            self.propagate()

    def reset(self):
        self.output=Const.UNKNOWN
        self.children[Const.UNKNOWN]=self.children[Const.HIGH]|self.children[Const.LOW]|self.children[Const.ERROR]|self.children[Const.UNKNOWN]
        self.children[Const.HIGH]=set()
        self.children[Const.LOW]=set()
        self.children[Const.ERROR]=set()
    
    def hide(self):

        for parent in self.parents:
            parent.children[self.output].discard(self)
       
        for i in self.children.keys():
            for child in self.children[i]:
                child.parents.discard(self)   

        for parent in self.parents:
            parent.process()
            parent.propagate()   

    def reveal(self):
        if self.output==Const.ERROR:
                self.burn()
        else:
            for parent in self.parents:# disconnect from parents and they will modify their output 
                parent.connect(self)
        for child in self.children[Const.LOW]| self.children[Const.HIGH]|self.children[Const.ERROR]:
            child.parents.add(self)
        for parent in self.parents:# disconnect from parents and they will modify their output 
            parent.propagate()

    def turnon(self):
        return len(self.children[Const.LOW])+len(self.children[Const.HIGH])+len(self.children[Const.ERROR])>=self.inputlimit


    
    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs

    def getoutput(self):
        if self.output==Const.ERROR:
            return '1/0'
        if self.output==Const.UNKNOWN:
            return Const.UNKNOWN
        return 'T' if self.output == Const.HIGH else 'F'
        
    def json_data(self):
        all_children = (
            self.children[Const.UNKNOWN] | 
            self.children[Const.HIGH] | 
            self.children[Const.LOW] | 
            self.children[Const.ERROR]
    )
        dictionary={
            "name":self.name,
            "custom_name":self.custom_name,
            "code":self.code,
            "children":[child.code for child in all_children],
            "parents":[parent.code for parent in self.parents],
            "output":self.output,
        }
        return dictionary
    
    def copy_data(self,cluster):
        dictionary={
            "name":self.name,
            "custom_name":self.custom_name,
            "code":self.code,
            "parents":[parent.code for parent in self.parents if parent in cluster],
            "output":self.output,
        }
        return dictionary
    
    def decode(self,code):
        if len(code)==2 :
            return tuple(code)
        return (code[0],code[1],self.decode(code[2]))
    
    def clone(self,dictionary,pseudo):
        self.custom_name=dictionary["custom_name"]
        self.parents=set(pseudo[self.decode(parent)] for parent in dictionary["parents"])
        self.children[Const.UNKNOWN]=set(pseudo[self.decode(child)] for child in dictionary["children"])
        self.output=dictionary["output"]
    
    def load_to_cluster(self,cluster):
        cluster.add(self)

    def implement(self,dictionary,pseudo):
        self.custom_name=dictionary["custom_name"]
        self.parents=set(pseudo[self.decode(parent)] for parent in dictionary["parents"])
        # connect and propagate to parents
        for parent in self.parents:
            parent.connect(self)
        
class Variable(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):     
        super().__init__() 
        self.inputlimit=1
        self.realchild=1

    def connect(self,child:Signal):
        if isinstance(child,Signal):
            self.children[child.output].add(child)
            self.children[child.output^1]=set()
            self.process()
    def reset(self):
        self.output='X'
        pass
    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=len(self.children[Const.HIGH])
        else:
            self.output=Const.UNKNOWN

class Probe(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=len(self.children[Const.HIGH])
        else:
            self.output=Const.UNKNOWN
                    
    # def json_data(self):
    #     dictionary={
    #         "name":self.name,
    #         "code":self.code,
    #         "parents":[parent.code for parent in self.parents],
    #         "High":[child.code for child in self.children[Const.HIGH]],
    #         "Low":[child.code for child in self.children[Const.LOW]],
    #         "Error":[child.code for child in self.children[Const.ERROR]],
    #         "output":self.output,
    #         "inputpoint":self.inputpoint,
    #         "outputpoint":self.outputpoint
    #     }
    #     return dictionary            

class InputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1
        # self.inputpoint=False

class OutputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):      
        super().__init__()    
        self.inputlimit=1
        # self.outputpoint=False

class NOT(Gate):
    def __init__(self):    
        super().__init__()
        self.inputlimit=1

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=len(self.children[Const.LOW])
        else:
            self.output=Const.UNKNOWN

class AND(Gate):
    def __init__(self):
        super().__init__()
 
    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=0 if len(self.children[Const.LOW]) else 1
        else:
            self.output=Const.UNKNOWN

class NAND(Gate):
    def __init__(self):
        super().__init__()   

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=1 if len(self.children[Const.LOW]) else 0
        else:
            self.output=Const.UNKNOWN

class OR(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=1 if len(self.children[Const.HIGH]) else 0
        else:
            self.output=Const.UNKNOWN

class NOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=0 if len(self.children[Const.HIGH]) else 1
        else:
            self.output=Const.UNKNOWN
       
class XOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=len(self.children[Const.HIGH])%2
        else:
            self.output=Const.UNKNOWN

class XNOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output=self.output
        if self.isready():
            self.output=(len(self.children[Const.HIGH])%2)^1 
        else:
            self.output=Const.UNKNOWN
        
        
