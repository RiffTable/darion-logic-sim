from Gates import Gate,InputPin,OutputPin
class IC:
    def __init__(self):
        self.inputs=[]
        self.allgates=[]
        self.outputs=[]
        self.name='IC'

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
    
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name
    
