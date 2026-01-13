from Gates import Gate,InputPin,OutputPin
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
    
