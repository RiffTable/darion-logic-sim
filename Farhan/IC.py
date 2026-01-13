import select
from Gates import Gate,InputPin,OutputPin
from Enum import Enum
class IC:
    def __init__(self,circuit):
        self.inputs=[]
        self.allgates=[]
        self.outputs=[]
        self.name='IC'
        self.code=''
        self.circuit=circuit

    def addgate(self,child:Gate|OutputPin|InputPin):
        self.allgates.append(child)
        if isinstance(child,InputPin):
            self.inputs.append(child)
        if isinstance(child,OutputPin):
            self.outputs.append(child)
    def showinputpins(self):
        for i,gate in enumerate(self.inputs):
            print(f'{i}. {gate}')
    
    def showoutputpins(self):
        for i,gate in enumerate(self.outputs):
            print(f'{i}. {gate}')            

    def hide(self):
        for pin in self.outputs:
            for parent in pin.parents:
                parent.children[pin.output].discard(pin)
        for pin in self.inputs:
            for child in pin.children[Enum.LOW]:
                child.parents.discard(pin)
            for child in pin.children[Enum.HIGH]:
                child.parents.discard(pin)
            for child in pin.children[Enum.ERROR]:
                child.parents.discard(pin)
                
    def reveal(self):
        for pin in self.outputs:
            for parent in pin.parents:
                parent.children[pin.output].add(pin)
            for parent in pin.parents:
                parent.propogate()
        for pin in self.inputs:
            for child in pin.children[Enum.LOW]:
                child.parents.discard(pin)
            for child in pin.children[Enum.HIGH]:
                child.parents.discard(pin)
            for child in pin.children[Enum.ERROR]:
                child.parents.discard(pin)
    
    def info(self):
        # show all components in a ordered way
        for comp in self.allgates:
            print(f'{comp.name} with output {comp.output}')
            print(f'Parents: {[p.name for p in comp.parents]}')
            print(f'Children (LOW): {[c.name for c in comp.children[Enum.LOW]]}')
            print(f'Children (HIGH): {[c.name for c in comp.children[Enum.HIGH]]}')
            print(f'Children (ERROR): {[c.name for c in comp.children[Enum.ERROR]]}')
            print('---')
            
    def connect(self,pin:InputPin,gate:Gate):
        pin.connect(gate)

    def halfclone(self,pseudo:dict):
        clone=pseudo[self.code]
        for obj in self.allgates:
            comp=self.circuit.getICcomponent(obj.code[0])
            pseudo[obj.code]=comp
            clone.addgate(comp)
        for obj in self.allgates:
            obj.halfclone(pseudo) 
    def clearlist(self):
        for gate in self.allgates:
            self.circuit.delobj(gate.code)
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name
    
