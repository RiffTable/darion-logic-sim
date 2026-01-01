class Signal:
    # default signals that exist indepdently
    def __init__(self,circuit,value):
        self.circuit=circuit
        self.parents=set()
        self.output=value
        self.name=str(value)

class Gate:   

    def __init__(self,circuit):
        # a gate needs holders from the circuit
        self.circuit=circuit

        # gate's children or inputs
        self.children=[set(),set()]
        self.parents=set()
        # input limit
        self.inputlimit=2
        #default output
        self.output=0
        self.prev_output=0
        # each gate will have it's own unique id
        self.code=''
        self.name=''

    def parity(self):
        if len(self.parents):
            for parent in self.parents:
                if self.code in self.circuit.getobj(parent).children[self.output]:
                    return False
                else:
                    return True
        return False
    def override(self,code):
        self.code=code

    def turnon(self):
        return len(self.children[0])+len(self.children[1])>=self.inputlimit

    # operates on the inputs
    def process(self):
        pass
    
    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs
    def display_output(self):
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
        self.children[0].add('00')
    def override(self, code):
        super().override(code)
        Variable.rank=max(Variable.rank,int(code[1:]))
    def process(self):
        out=self.output
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
        super().override(code)
        NOT.rank=max(NOT.rank,int(code[1:]))
    def process(self):
        out=self.output
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
        super().override(code)
        AND.rank=max(AND.rank,int(code[1:]))
        
    def process(self):
        out=self.output
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
        super().override(code)
        NAND.rank=max(NAND.rank,int(code[1:]))
        
    def process(self):
        out=self.output
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
        super().override(code)
        OR.rank=max(OR.rank,int(code[1:]))
        
        
    def process(self):
        out=self.output
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
        super().override(code)
        NOR.rank=max(NOR.rank,int(code[1:]))

    def process(self):
        out=self.output
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
        super().override(code)
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
        super().override(code)
        XNOR.rank=max(XNOR.rank,int(code[1:]))
        
    def process(self):
        out=int(len(self.children[1])%2==0)
        self.prev_output=self.output
        self.output=out
        


# inventory
class Circuit:
    def __init__(self):
        self.objlist=[{} for i in range(9)]# holds the objects with code name
        self.complist=[]# displays the components 
        self.varlist=[]# holds variables with 0/1 input
        self.probelist=[]# variables with gate input or these are probes
        self.circuit_breaker={}# checks for loops while connecting
        self.gatelist=['NOT', 'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR']
        self.objlist[0]['0']=Signal(self,0)
        self.objlist[0]['1']=Signal(self,1)

        
    def getobj(self,code):
        return self.objlist[int(code[0])][code[1:]]
    # show component
    def listComponent(self):
        for i in range(len(self.complist)):
            comp=self.getname(self.complist[i])
            print(f'{i}. {comp}')

    # show variables
    def listVar(self):
        for i in range(len(self.varlist)):
            var=self.getname(self.varlist[i])
            print(f'{i}. {var}')

    # name suggests it
    def getcomponent(self,i,code):

        if i == '1':
            gt = NOT(self)# feed circuit to the gates so they can access it's holders
        elif i == '2':
            gt = AND(self)
        elif i == '3':
            gt = NAND(self)
        elif i == '4':
            gt = OR(self)
        elif i == '5':
            gt = NOR(self)                
        elif i == '6':
            gt = XOR(self)
        elif i == '7':
            gt = XNOR(self)   
        elif i=='8':
            gt=Variable(self)
            self.varlist.append(gt.code)     
        else:
            return
        if code!='':
            gt.override(code)
        gt.name=self.decode(gt.code)
        self.objlist[int(gt.code[0])][gt.code[1:]]=gt
        self.complist.append(gt.code)
        self.circuit_breaker[gt.code]=-1
        return gt.code

    def decode(self,code):
        gate=int(code[0])
        if(gate==8):
            order=int(code[1:])
            return chr(ord('A')+order%26)+str(order//26)
        elif gate==0:
            return code[1:]
        else:
            gate-=1
            return self.gatelist[gate]+'-'+code[1:]    
        
    def getname(self,gate):
        return self.objlist[int(gate[0])][gate[1:]].name

    # connects parent to it's child/inputs
    def connect(self,gate,child):
        gate_obj=self.getobj(gate)
        child_obj=self.getobj(child)
        val=child_obj.output
        if(val==-1):
            return
        # check for variable or probe
        if gate[0]=='8':
            if child[0]=='8':
                return
            elif child[0]=='0':
                # variable has a 0/1 input so it's not a probe
                if gate in self.probelist:
                    self.probelist.remove(gate)
                    self.varlist.append(gate)
            else:
                # a probe has a gate input
                if gate in self.varlist:
                    self.varlist.remove(gate)
                    self.probelist.append(gate)
        
        # connect child to self

        if child in gate_obj.children[val] and gate_obj.output!=-1:# no need to reconnect if connected
            return
        else:
            if gate[0]=='8' or gate[0]=='1':
                # variable and not gate will have atmost one input so i need to erase
                # child set to add new child
                gate_obj.children[val].clear()
            
            gate_obj.children[val].add(child)# add child according to it's value
        if child in gate_obj.children[val^1]:
            # if the value of a child is changed 
            # it pre exists in the other value so i have to delete it
            gate_obj.children[val^1].discard(child)
        if gate[0]=='8' or gate[0]=='1':
            # not and variable won't have variable in the other container(only one at a time)
            gate_obj.children[val^1].clear()

        # connect children to it as their parent
        if child[0]!='0' and gate_obj not in child_obj.parents:
            child_obj.parents.add(gate)
        gate_obj.process()
        self.update(gate)# renew output 

    def passive_connect(self,parent,child,child_output):
        parent_obj=self.getobj(parent)  
        child_obj=self.getobj(child)
        parent_obj.children[child_output].add(child)
        child_obj.parents.add(parent)

    # disconnects parent & child
    def disconnect_gates(self,parent,child):
        parent_obj=self.getobj(parent)
        child_obj=self.getobj(child)
        parent_obj.children[child_obj.output].discard(child)
        parent_obj.children[child_obj.output^1].discard(child)# delete child 
        if parent[0]=='8':
            self.connect(parent,'00')
        else:
            parent_obj.process()# modify output after removing child
            self.update(parent)
        child_obj.parents.discard(parent)# child disconnects with parent

    # identify parent/child
    def disconnect(self,gate1,gate2):
        
        gate1_obj=self.getobj(gate1)
        gate2_obj=self.getobj(gate2)

        # check for parenthood and delete with function
        if gate1 in gate2_obj.parents:
            self.disconnect_gates(gate1,gate2)            
        elif gate2 in gate1_obj.parents:
            self.disconnect_gates(gate2,gate1)


    # deletes component
    def deleteComponent(self,gate):
        gate_obj=self.getobj(gate)
        parent_list=list(gate_obj.parents)# set changes after deletion so i need list
        for parent in parent_list:# disconnect from parents and they will modify their output 
            self.disconnect_gates(parent,gate)
        for child in gate_obj.children[0]:# disconnect from children
            self.getobj(child).parents.discard(gate)
        for child in gate_obj.children[1]:
            self.getobj(child).parents.discard(gate)        
        if gate[0]=='8':
            if gate in self.probelist:
                self.probelist.remove(gate)
            elif gate in self.varlist:
                self.varlist.remove(gate)
                
    def renewComponent(self,gate):
        gate_obj=self.getobj(gate)
        parent_list=list(gate_obj.parents)# set changes after deletion so i need list
        for parent in parent_list:# disconnect from parents and they will modify their output 
            self.connect(parent,gate)
        for child in gate_obj.children[0]:# disconnect from children
            self.getobj(child).parents.add(gate)
        for child in gate_obj.children[1]:
            self.getobj(child).parents.add(gate)        
        if gate[0]=='8':
            if gate in self.probelist:
                self.probelist.append(gate)
            elif gate in self.varlist:
                self.varlist.append(gate)                
    
    # if my output changes i will update my parents 
    # circuit breaker breaks if a gate seen more than twice in a single operation
    def update(self,gate):
        gate_obj=self.getobj(gate)
        prev=gate_obj.prev_output
        out=gate_obj.output
        if self.circuit_breaker[gate]==-1:
            self.circuit_breaker[gate]=out
            if prev!=out or gate_obj.parity():
                for parent in gate_obj.parents:
                    self.connect(parent,gate)
                    if self.getobj(parent).output==-1:
                        gate_obj.output=-1
                        break
            self.circuit_breaker[gate]=-1
        elif self.circuit_breaker[gate]==out:
            return
        else:
            # print('Loop Detected')            
            gate_obj.output=-1

    def correction(self,gate):
        gate_obj=self.getobj(gate)
        if gate_obj.prev_output!=gate_obj.output:
            gate_obj.output=gate_obj.prev_output
            for parent in gate_obj.parents:
                parent_obj=self.getobj(parent)
                if gate not in parent_obj.children[gate_obj.output]:
                    parent_obj.children[gate_obj.output].add(gate)
                    parent_obj.children[gate_obj.output^1].discard(gate)
                self.correction(parent)
        
    # fixes the loop by breaking the connection that caused it
    def fallback(self,parent,child):
        parent_obj=self.getobj(parent)
        child_obj=self.getobj(child)
        if parent_obj.output==-1:
            parent_obj.prev_output^=1
        child_obj.parents.discard(parent)
        parent_obj.children[0].discard(child)
        parent_obj.children[1].discard(child)
        
        if parent[0]=='8':
            self.connect(parent,'00')
        else:
            self.correction(parent)


    def fix_var(self,var):
        var_obj=self.getobj(var)
        if var_obj.output!=-1:
            return
        if len(var_obj.children[0]):
            out=0
        else:
            out=1
        var_obj.output=out


    # Result 
    def output(self,gate):
        print(f'{self.getname(gate)} output is {self.getobj(gate).display_output()}')


    # Truth Table
    def truthTable(self, gate):
        if len(self.varlist) == 0:
            print('No variable for toggling')
            return
        
        if gate in self.varlist:
            print(f'{self.getname(gate)} is a variable not a gate or a probe')
            return
        
        if gate not in self.complist:
            print(f'{gate} is not a valid component in the circuit.')
            return

        n = len(self.varlist)
        rows = 1 << n

        # Collect decoded variable names and the output gate name
        var_names = [self.getname(v) for v in self.varlist]
        output_name = self.getname(gate)

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + [output_name]) + 2
        header = " | ".join(name.center(col_width) for name in var_names + [output_name])
        separator = "─" * len(header)

        # Print table header
        print("\nTruth Table for " + output_name)
        print(separator)
        print(header)
        print(separator)

        for i in range(rows):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                self.connect(var, '0' + str(bit))
                inputs.append("1" if bit else "0")

            output = self.getobj(gate).display_output()
            # Replace internal display values with clean T/F (or keep OFF/0/1 if needed)

            row = " | ".join(val.center(col_width) for val in inputs + [output])
            print(row)

        print(separator)
        print()  


    # diagnosis: this menu is AI generated and it's not the main part of code just to check errors in CLI mode
    # i modified logic in between commits
    def diagnose(self):
        print("--- Component Diagnosis ---")
        
        # Define columns dynamically (easy to add/remove in the future)
        columns = [
            ("Component", 12),
            ("Input-0", 22),
            ("Input-1", 22),
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
        
        for comp_code in self.complist:
            comp_obj = self.getobj(comp_code)
            
            # Inputs (children)
            comp_name = self.getname(comp_code)
            input_0=[]
            input_1=[]
            for i in comp_obj.children[0]:
                input_0.append(self.getname(i))
            for i in comp_obj.children[1]:
                input_1.append(self.getname(i))
            children_0 = ", ".join(sorted(input_0)) if input_0 else "None"
            children_1 = ", ".join(sorted(input_1)) if input_1 else "None"
            
            # Outputs (parents)
            parents=[]
            for i in comp_obj.parents:
                parents.append(self.getname(i))
            parents = ", ".join(sorted(parents)) if parents else "None"
            
            # State
            state = comp_obj.display_output()
            
            print(row_format.format(comp_name, children_0, children_1, parents, state))
        
        print("-" * total_width)
        
    def writetofile(self):
        # write the component list to file
        f=open('D:/Github/darion-logic-sim/file.txt','w')

        for i in self.complist:
            f.write(f'{i} ')
        f.write('\n')
        for i in self.complist:
            obj=self.getobj(i)
            # write self
            f.write(f'{i} ')
            # write children
            input_0=','.join(obj.children[0])
            if len(input_0):                
                f.write(f'{input_0} ')
            else:
                f.write('X ')   
            input_1=','.join(obj.children[1])
            if len(input_1):                
                f.write(f'{input_1} ')
            else: 
                f.write('X ')   
            # write output
            f.write(str(obj.output))
            f.write('\n')
        f.close()

    def readfromfile(self):
        f=open('D:/Github/darion-logic-sim/file.txt','r')
        self.objlist[0]['0']=Signal(self,0)
        self.objlist[0]['1']=Signal(self,1)
        components=f.readline().split(' ')
        components.pop()
        if len(components)==0:
            return
        
        # create components
        for component in components:
            self.getcomponent(component[0],component)
            if component[0]=='8':
                self.getobj(component).children[0].clear()
        connections=f.read().split('\n')
        connections.pop()
        for line in connections:
            line=line.split(' ')
            gate=line[0]
            children_0=line[1].split(',')
            if 'X' not in children_0:
                for child in children_0:
                    self.passive_connect(gate,child,0)
            children_1=line[2].split(',')
            if 'X' not in children_1:
                for child in children_1:
                    self.passive_connect(gate,child,1)
            output=line[3]
            self.getobj(gate).output=int(output)
        f.close()
    def clearcircuit(self):
        Variable.rank=0
        NOT.rank=0
        AND.rank=0
        NAND.rank=0
        OR.rank=0
        NOR.rank=0
        XOR.rank=0
        XNOR.rank=0
        
        self.circuit_breaker={}
        for i in self.objlist:
            i.clear()
        self.varlist.clear()
        self.complist.clear()
        self.probelist.clear()