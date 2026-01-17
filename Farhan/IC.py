from __future__ import annotations
from Gates import Gate,InputPin, OutputPin, Variable, NOT, AND, NAND, OR, NOR, XOR, XNOR, Probe
from Const import Const
class IC:
    def __init__(self):
        self.inputs=[]
        self.internal=[]
        self.outputs=[]

        self.name='IC'
        self.custom_name=''
        self.code=''

        self.gateobjects={1:NOT, 2:AND, 3:NAND, 4:OR, 5:NOR, 6:XOR, 7:XNOR, 8:Variable,9:Probe,10:InputPin,11:OutputPin,12:IC}
        self.map={}

    def __repr__(self):
        return self.name if self.custom_name=='' else self.custom_name
        
    def __str__(self):
        return self.name if self.custom_name=='' else self.custom_name
    
    def getcomponent(self,choice):
        if choice not in self.gateobjects:
            return
        gt=self.gateobjects[choice]()
        if isinstance(gt,InputPin):
            rank=len(self.inputs)
            self.inputs.append(gt)
            gt.name='in-'+str(len(self.inputs))
        elif isinstance(gt,OutputPin):
            rank=len(self.outputs)
            self.outputs.append(gt)
            gt.name='out-'+str(len(self.outputs))            
        else:
            rank=len(self.internal)
            self.internal.append(gt)
            gt.name=gt.__class__.__name__+'-'+str(len(self.internal))
        gt.code=(choice,rank,self.code)        
        return gt
    
    def addgate(self, child:Gate|OutputPin|InputPin):
        
        if isinstance(child,InputPin):
            rank=len(self.inputs)
            self.inputs.append(child)
            child.name='in-'+str(len(self.inputs))
        elif isinstance(child,OutputPin):
            rank=len(self.outputs)
            self.outputs.append(child)
            child.name='out-'+str(len(self.outputs))            
        else:
            rank=len(self.internal)
            self.internal.append(child)
            child.name=child.__class__.__name__+'-'+str(len(self.internal))
        child.code=(child.code[0],rank,self.code)     
        
    def configure(self,dictionary):
        pseudo={}
        self.map=dictionary["map"]
        self.load_components(dictionary,pseudo)
        self.clone(pseudo)
        
    def decode(self,code):
        if len(code)==2:
            return tuple(code)
        return (code[0],code[1],self.decode(code[2]))
    
    def load_components(self,dictionary,pseudo):
        for code in dictionary["components"]:# generate all the necessary components
            gate=self.getcomponent(code[0])
            pseudo[self.decode(code)]=gate

    def json_data(self):
        dictionary={
            "name":self.name,
            "code":self.code,            
            "components":[gate.code for gate in self.internal+self.inputs+self.outputs],
            "map":[]
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.json_data())
        return dictionary
    
    def clone(self,pseudo):
        for i in self.map:
            code=self.decode(i["code"])      
            gate=pseudo[code]
            if isinstance(gate,IC):
                gate.map=i["map"]
                gate.load_components(i,pseudo)
                gate.clone(pseudo)
            else:
                gate.clone(i,pseudo)       

    def load_to_cluster(self,cluster:set):
        for i in self.inputs+self.internal+self.outputs:
            if isinstance(i,IC):
                cluster.add(i)
                i.load_to_cluster(cluster)
            else:                
                cluster.add(i)

    def copy_data(self,cluster):
        dictionary={
            "name":self.name,
            "code":self.code,            
            "components":[gate.code for gate in self.internal+self.inputs+self.outputs],
            "map":[]
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.copy_data(cluster))
        return dictionary
    
    def implement(self,pseudo):
        for i in self.map:
            code=self.decode(i["code"])      
            gate=pseudo[code]
            if isinstance(gate,IC):
                gate.map=i["map"]
                gate.load_components(i,pseudo)
                gate.implement(pseudo)
            else:
                gate.implement(i,pseudo)       

    def hide(self):
        for pin in self.outputs:
            for parent in pin.parents:
                parent.children[pin.output].discard(pin)
            for parent in pin.parents:
                parent.process()
                parent.propagate()
        for pin in self.inputs:
            for i in pin.children.keys():
                for child in pin.children[i]:
                    child.parents.discard(pin)   
                
    def reveal(self):
        for pin in self.outputs:
            for parent in pin.parents:
                parent.connect(pin)
            for parent in pin.parents:
                parent.propagate()
        for pin in self.inputs:
            for i in pin.children.keys():
                for child in pin.children[i]:
                    child.parents.add(pin)   

    def reset(self):
        for i in self.inputs+self.internal+self.outputs:
            i.reset()
            
    def showinputpins(self):
        for i,gate in enumerate(self.inputs):
            print(f'{i}. {gate}')
    
    def showoutputpins(self):
        for i,gate in enumerate(self.outputs):
            print(f'{i}. {gate}')            
      
    def info(self):
        # show all components in a ordered way
        for comp in self.internal:
            if isinstance(comp,IC):
                comp.info()
            else:
                print(f'{comp.name} with output {comp.output}')
                print(f'Parents: {[p.name for p in comp.parents]}')
                print(f'Children (LOW): {[c.name for c in comp.children[Const.LOW]]}')
                print(f'Children (HIGH): {[c.name for c in comp.children[Const.HIGH]]}')
                print(f'Children (ERROR): {[c.name for c in comp.children[Const.ERROR]]}')
                print('---')
            

