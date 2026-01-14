import json
from Gates import Gate, Signal, Variable, NOT, AND, NAND, OR, NOR, XOR, XNOR,Probe,InputPin,OutputPin
from Enum import Enum
from IC import IC
class Circuit:

    def __init__(self):
        self.objlist={i:[] for i in range(-11,13)}# holds the objects with code name
        self.canvas=[]# displays the components 
        self.varlist=[]# holds variables with 0/1 input
        self.iclist=[]
        self.sign_0=Signal(Enum.LOW)
        self.sign_1=Signal(Enum.HIGH)
        self.objlist[0]=[self.sign_0,self.sign_1]
        self.copydata=[]
        self.gateobjects={1:NOT, 2:AND, 3:NAND, 4:OR, 5:NOR, 6:XOR, 7:XNOR, 8:Variable,9:Probe,10:InputPin,11:OutputPin,12:IC}

    def __repr__(self):
        return 'Circuit'

    def getcomponent(self,choice)->Gate|Signal:
        if abs(choice) not in self.gateobjects:
            return
        if choice!=12:
            gt=self.gateobjects[abs(choice)]()
        else:
            gt=self.gateobjects[choice](self)
        rank=len(self.objlist[choice])
        self.objlist[choice].append(gt)
        gt.code=(choice,rank)
        name=gt.__class__.__name__
        if name=='Variable':
            gt.name=chr(ord('A')+(rank)%26)+str((rank+1)//26)
            gt.children[Enum.LOW].add(self.sign_0)
        else:
            gt.name=name+'-'+str(len(self.objlist[choice]))

        if isinstance(gt,Variable):
            self.varlist.append(gt)
        if isinstance(gt,IC):
            self.iclist.append(gt)
        if choice>0:
            self.canvas.append(gt)
        return gt
    

    def getobj(self,code)->Gate|Signal:
        return self.objlist[code[0]][code[1]]
    
    def delobj(self,code):
        if code[0]==12:
            ic=self.objlist[code[0]][code[1]]
            ic.clearlist()
                
        self.objlist[code[0]][code[1]]=None

    # show component
    def listComponent(self):
        for i in range(len(self.canvas)):
            print(f'{i}. {self.canvas[i]}')

    # show variables
    def listVar(self):
        for i in range(len(self.varlist)):
            print(f'{i}. {self.varlist[i]}')
        
    # connects parent to it's child/inputs
    def connect(self,parent:Gate,child:Gate|Signal):
        if child not in parent.children[child.output]:
            parent.connect(child)
        if parent.prev_output!=parent.output:
            parent.propagate()

    def passive_connect(self,parent,child,child_output:str):
        parent_obj=self.getobj(parent)      
        child_obj=self.getobj(child)
        parent_obj.children[child_output].add(child_obj)
        if child[0]!=0:
            child_obj.parents.add(parent_obj)

    # identify parent/child
    def disconnect(self,parent:Gate,child:Gate):
        if parent in child.parents:
            parent.disconnect(child)

    # deletes component
    def hideComponent(self,gate:Gate|IC):
        gate.hide()
        if gate in self.varlist:
            self.varlist.remove(gate)
        self.canvas.remove(gate)

    def terminate(self,gate):
        self.delobj(gate.code)
        if gate in self.varlist:
            self.varlist.remove(gate)
        self.canvas.remove(gate)

    def renewComponent(self,gate:Gate|IC):
        gate.reveal()
        if isinstance(gate,Variable):
            self.varlist.append(gate)
        self.canvas.append(gate)       
    
    # Result 
    def output(self,gate:Gate):
        print(f'{gate} output is {gate.getoutput()}')

    # Truth Table
    def truthTable(self):
        if len(self.varlist) == 0:
            return
        
        gate_list=[i for i in self.canvas if i not in self.varlist and not isinstance(i,IC)]
        n = len(self.varlist)
        rows = 1 << n
        # Collect decoded variable names and the output gate name
        var_names = [v.name for v in self.varlist]
        output_name=[v.name for v in gate_list]

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + output_name ) + 2
        header = " | ".join(name.center(col_width) for name in var_names + output_name)
        separator = "─" * len(header)

        # Print table header
        Table="\nTruth Table\n"
        # add seperater header and seperator in Table 
        Table+=separator+'\n'
        Table+=header+'\n'
        Table+=separator+'\n'
        for i in range(rows):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                self.connect(var,self.sign_1 if bit else self.sign_0)
                inputs.append("1" if bit else "0")
            output=[gate.getoutput() for gate in gate_list]
            row = " | ".join(val.center(col_width) for val in inputs + output)
            Table+=row+'\n'
        Table+=separator+'\n'
        return Table
      

    # diagnosis: this menu is AI generated and it's not the main part of code just to check errors in CLI mode
    # i modified logic in between commits
    def diagnose(self):
        print("--- Component Diagnosis ---")
        
        # Define columns dynamically (easy to add/remove in the future)
        columns = [
            ("Component", 12),
            ("Input-0", 22),
            ("Input-1", 22),
            ('Error',22),
            ("Parents (Outputs to)", 25),
            ("State", 10)
        ]
        
        # Calculate total width for separator line
        total_width = sum(width for _, width in columns)
        
        # Header row
        header_format = "".join(f"{{:<{width}}}" for _, width in columns)
        header_names = [name for name, _ in columns]
        print(header_format.format(*header_names))
        print("-" * total_width)
        
        # Data rows
        row_format = header_format  # Same alignment and widths
        
        for component in self.canvas:
            if isinstance(component,IC):
                continue
            # Inputs (children)
            input_0=[]
            input_1=[]
            Error=[]
            for i in component.children[Enum.LOW]:
                input_0.append(i.name)
            for i in component.children[Enum.HIGH]:
                input_1.append(i.name)
            for i in component.children[Enum.ERROR]:
                Error.append(i.name)
            children_0 = ", ".join(sorted(input_0)) if input_0 else "None"
            children_1 = ", ".join(sorted(input_1)) if input_1 else "None"
            children_neg = ", ".join(sorted(Error)) if Error else "None"
            
            # Outputs (parents)
            parents=[]
            for i in component.parents:
                parents.append(i.name)
            parents = ", ".join(sorted(parents)) if parents else "None"
            
            # State
            state = component.getoutput()
            
            print(row_format.format(str(component), children_0, children_1,children_neg, parents, state))
        
        print("-" * total_width)
        

    def writetojson(self,location):
        circuit=[{"Component_List":[gate.code for gate in self.canvas]}]
        for gate in self.canvas:
            gate_dict={
                "name":gate.name,
                "code":gate.code,
                "high_child":[child.code for child in gate.children[Enum.HIGH]],
                "low_child":[child.code for child in gate.children[Enum.LOW]],
                "error_child":[child.code for child in gate.children[Enum.ERROR]],
                "output":gate.output,
                "parents":[parent.code for parent in gate.parents]            
                 }
            circuit.append(gate_dict)
        with open(location,'w') as file:
            json.dump(circuit,file,indent=4)

    def readfromjson(self,location):
        with open(location,'r') as file:
            circuit=json.load(file)
        pseudo={}
        pseudo[(0,0)]=self.sign_0
        pseudo[(0,1)]=self.sign_1
        for i in circuit[0]["Component_List"]:
            gate=self.getcomponent(i[0])
            pseudo[tuple(i)]=gate
        
        for i in range(1,len(circuit)):
            gate_dict=circuit[i]
            code=(gate_dict["code"][0],gate_dict["code"][1])
            gate=pseudo[code]
            gate.children[Enum.LOW]=set(pseudo[tuple(child)] for child in gate_dict["low_child"])
            gate.children[Enum.HIGH]=set(pseudo[tuple(child)] for child in gate_dict["high_child"])
            gate.children[Enum.ERROR]=set(pseudo[tuple(child)] for child in gate_dict["error_child"])
            gate.output=gate_dict["output"]
            gate.parents=set(pseudo[tuple(parent)] for parent in gate_dict["parents"])
    
    def createIC(self,location):
        myIC=self.getcomponent(12)
        with open(location,'r') as file:
            circuit=json.load(file)
        pseudo={}
        pseudo[(0,0)]=self.sign_0
        pseudo[(0,1)]=self.sign_1
        for i in circuit[0]["Component_List"]:
            gate=self.getcomponent(i[0])
            myIC.addgate(gate)
            pseudo[tuple(i)]=gate
        for i in range(1,len(circuit)):
            gate_dict=circuit[i]
            code=tuple(gate_dict["code"])
            gate=pseudo[code]
            if isinstance(gate,InputPin|OutputPin):
                gate.name=myIC.name+' '+gate_dict["name"]
            gate.children[Enum.LOW]=set(pseudo[tuple(child)] for child in gate_dict["low_child"])
            gate.children[Enum.HIGH]=set(pseudo[tuple(child)] for child in gate_dict["high_child"])
            gate.children[Enum.ERROR]=set(pseudo[tuple(child)] for child in gate_dict["error_child"])
            gate.output=gate_dict["output"]
            gate.parents=set(pseudo[tuple(parent)] for parent in gate_dict["parents"])
        # for inputs in myIC.inputs:
        #     self.canvas.append(inputs)
        # for outputs in myIC.outputs:
        #     self.canvas.append(outputs)

    def rank_reset(self):
        for key in self.objlist:
            while key and key[-1]==None:
                key.pop()
            
    def clearcircuit(self):
        for i,_ in enumerate(self.objlist):
            self.objlist[i]=[]
        self.varlist=[]
        self.canvas=[]

    def copy(self,components):
        if len(components)==0:
            return
        
        self.copydata={}
        for i in components:
            i.getcopyinfo(self.copydata,components)
        # for component in components:
        #     obj=self.getobj(component)
        #     info=[component]
        #     children=obj.children[Enum.LOW]|obj.children[Enum.HIGH]|obj.children[Enum.ERROR]
        #     children=[i.code for i in children]
        #     copychild=[]
        #     for child in children:
        #         if child in components or child[0]==0:
        #             copychild.append(child)
        #     if len(copychild)==0:
        #         copychild=()
        #     info.append(copychild)
        #     self.copydata.append(info)

    def paste(self):
        if len(self.copydata)==0:
            return
        pseudo={}
        pseudo[(0,0)]=self.sign_0
        pseudo[(0,1)]=self.sign_1
        new_items=[]
        for component in self.copydata.keys():
            identity=component[0]
            comp=self.getcomponent(identity)
            pseudo[component]=comp
            new_items.append(comp.code)
        for component,parentlist in self.copydata.items():
            component=pseudo[component]
            component.clone(pseudo,parentlist)
        return new_items

    # def paste(self):
    #     if len(self.copydata)==0:
    #         return
    #     components=self.copydata[0]
    #     pseudo={}
    #     pseudo[(0,0)]=self.sign_0
    #     pseudo[(0,1)]=self.sign_1
    #     new_items=[]
    #     for component in components:
    #         identity=component[0]
    #         comp=self.getcomponent(identity)
    #         pseudo[component]=comp
    #         new_items.append(comp.code)
    #     connections=[self.copydata[i] for i in range(1,len(self.copydata))]
    #     for line in connections:
    #         gate=line[0]
    #         children=line[1]
    #         if 'X' not in children:
    #             for child in children :
    #                 self.connect(pseudo[gate],pseudo[child])
    #     return new_items


