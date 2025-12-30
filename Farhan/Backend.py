class Signal:
    # default signals that exist indepdently
    def __init__(self,circuit,value):
        self.circuit=circuit
        self.parents=set()
        self.output=value

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
        # each gate will have it's own unique id
        self.code=''

    def turnon(self):
        return len(self.children[0])+len(self.children[1])>=self.inputlimit

    # operates on the inputs
    def process(self):
        pass
    
    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs
    def display_output(self):
        if self.turnon()==False:
            return 'OFF'
        elif self.output==-1:
            return '0/1'
        elif self.output==0:
            return 'F'
        else:
            return 'T'


class Variable(Gate):
    # this can be both an input or output(bulb)
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)          
        self.inputlimit=1
        self.code='8'+str(Variable.rank)
        Variable.rank+=1
        self.children[0].add('00')

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
        self.circuit.update(self.code,prev)
        if self.output==-1:
            self.circuit.fix_var(self.code)

        
class NOT(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)        
        self.inputlimit=1
        NOT.rank+=1
        self.code='1'+str(NOT.rank)

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
        self.circuit.update(self.code,prev)
        
class AND(Gate):

    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)       
        AND.rank+=1
        self.code='2'+str(AND.rank)
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
        self.circuit.update(self.code,prev)

        
class NAND(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        NAND.rank+=1
        self.code='3'+str(NAND.rank)
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
        self.circuit.update(self.code,prev)

class OR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)         
        OR.rank+=1
        self.code='4'+str(OR.rank)
    def process(self):
        out=self.output
        if len(self.children[1]):
            out=1
        else: 
            out=0
        prev=self.output
        self.output=out
        self.circuit.update(self.code,prev)

class NOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        NOR.rank+=1
        self.code='5'+str(NOR.rank)
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
        self.circuit.update(self.code,prev)

class XOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)       
        XOR.rank+=1
        self.code='6'+str(XOR.rank)
    def process(self):
        out=int(len(self.children[1])%2)
        prev=self.output
        self.output=out
        self.circuit.update(self.code,prev)


class XNOR(Gate):
    rank=0
    def __init__(self,circuit):
        super().__init__(circuit)   
        XNOR.rank+=1
        self.code='7'+str(XNOR.rank)
    def process(self):
        out=int(len(self.children[1])%2==0)
        prev=self.output
        self.output=out
        self.circuit.update(self.code,prev)


# inventory
class Circuit:
    def __init__(self):
        self.objlist={}# holds the objects with code name
        self.complist=[]# displays the components 
        self.varlist=[]# holds variables with 0/1 input
        self.probelist=[]# variables with gate input or these are probes
        self.circuit_breaker={}# checks for loops while connecting
        self.gatelist=['NOT', 'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR']
        self.objlist['00']=Signal(self,0)
        self.objlist['01']=Signal(self,1)

    # show component
    def listComponent(self):
        for i in range(len(self.complist)):
            comp=self.decode(self.complist[i])
            print(f'{i}. {comp}')

    # show variables
    def listVar(self):
        for i in range(len(self.varlist)):
            var=self.decode(self.varlist[i])
            print(f'{i}. {var}')

    # name suggests it
    def getcomponent(self,i):

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
        self.objlist[gt.code]=gt
        self.complist.append(gt.code)
        self.circuit_breaker[gt.code]=-1

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

    

    def addComponent(self):
        print("Choose a gate to add to the circuit:")
        
        print("1. NOT")
        print("2. AND")
        print("3. NAND")
        print("4. OR")
        print("5. NOR")  
        print("6. XOR")
        print("7. XNOR")
        print("8. Variable")  
        # 1 should be variable and then others change the entire print list order as in 2 NOT 3 AND   
        choice = input("Enter your choice: ").split()
        for i in choice:
            self.getcomponent(i)

    # connects parent to it's child/inputs
    def connect(self,gate,child):
        gate_obj=self.objlist[gate]
        child_obj=self.objlist[child]
        # check for variable or probe
        if isinstance(gate_obj,Variable):
            if isinstance(child_obj,Signal):
                # variable has a 0/1 input so it's not a probe
                if gate in self.probelist:
                    self.probelist.remove(gate)
                    self.varlist.append(gate)
            else:
                # a probe has a gate input
                if gate in self.varlist:
                    self.varlist.remove(gate)
                    self.probelist.append(gate)
        val=child_obj.output
        # connect child to self

        if child in gate_obj.children[val] and gate_obj.output!=-1:# no need to reconnect if connected
            return
        else:
            if isinstance(gate_obj,Variable) or isinstance(gate_obj,NOT):
                # variable and not gate will have atmost one input so i need to erase
                # child set to add new child
                gate_obj.children[val].clear()
            
            gate_obj.children[val].add(child)# add child according to it's value
        if child in gate_obj.children[val^1]:
            # if the value of a child is changed 
            # it pre exists in the other value so i have to delete it
            gate_obj.children[val^1].discard(child)
        if isinstance(gate_obj,Variable) or isinstance(gate_obj,NOT):
            # not and variable won't have variable in the other container(only one at a time)
            gate_obj.children[val^1].clear()

        # connect children to it as their parent
        if isinstance(child_obj,Signal)==False and gate_obj not in child_obj.parents:
            child_obj.parents.add(gate)
        gate_obj.process()# renew output 


    # disconnects parent & child
    def disconnect_gates(self,parent,child):
        parent_obj=self.objlist[parent]
        child_obj=self.objlist[child]
        parent_obj.children[child_obj.output].discard(child)# delete child 
        parent_obj.process()# modify output after removing child
        child_obj.parents.discard(parent)# child disconnects with parent

    # identify parent/child
    def disconnect(self,gate1,gate2):
        
        gate1_obj=self.objlist[gate1]
        gate2_obj=self.objlist[gate2]

        # check for parenthood and delete with function
        if gate1 in gate2_obj.parents:
            self.disconnect_gates(gate1,gate2)            
        elif gate2 in gate1_obj.parents:
            self.disconnect_gates(gate2,gate1)
        else:
            print(f'{gate1} & {gate2} are not connected')

    # deletes component
    def deleteComponent(self,gate):
        gate_obj=self.objlist[gate]
        parent_list=list(gate_obj.parents)# set changes after deletion so i need list
        for parent in parent_list:# disconnect from parents and they will modify their output 
            self.disconnect_gates(parent,gate)
        for child in gate_obj.children[0]:# disconnect from children
            self.objlist[child].parents.discard(gate)
        for child in gate_obj.children[1]:
            self.objlist[child].parents.discard(gate)        
        del self.objlist[gate] # delete from objlist
      
    # if my output changes i will update my parents 
    # circuit breaker breaks if a gate seen more than twice in a single operation
    def update(self,gate,prev):
        gate_obj=self.objlist[gate]
        out=gate_obj.output
        if self.circuit_breaker[gate]==-1:
            self.circuit_breaker[gate]=out
            if gate_obj.turnon() and prev!=out:
                for parent in gate_obj.parents:
                    self.connect(parent,gate)
                    if self.objlist[parent].output==-1:
                        gate_obj.output=-1
                        break
            self.circuit_breaker[gate]=-1
        elif self.circuit_breaker[gate]==out:
            return
        else:
            # print('Loop Detected')
            gate_obj.output=-1
        
    # fixes the loop by breaking the connection that caused it
    def fix(self,parent,child):
        parent_obj=self.objlist[parent]
        child_obj=self.objlist[child]

        child_obj.parents.discard(parent)
        parent_obj.children[0].discard(child)
        parent_obj.children[1].discard(child)
        
        if isinstance(parent_obj,Variable):
            self.connect(parent,'0')
        else:
            parent_obj.process()


    def fix_var(self,var):
        var_obj=self.objlist[var]
        if len(var_obj.children[0]):
            out=0
        else:
            out=1
        var_obj.output=out


    # Result 
    def output(self,gate):
        print(f'{self.decode(gate)} output is {self.objlist[gate].display_output()}')


    # Truth Table
    def truthTable(self, gate):
        if len(self.varlist) == 0:
            print('No variable for toggling')
            return
        
        if gate in self.varlist:
            print(f'{self.decode(gate)} is a variable not a gate or a probe')
            return
        
        if gate not in self.complist:
            print(f'{gate} is not a valid component in the circuit.')
            return

        n = len(self.varlist)
        rows = 1 << n

        # Collect decoded variable names and the output gate name
        var_names = [self.decode(v) for v in self.varlist]
        output_name = self.decode(gate)

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + [output_name]) + 2
        header = " | ".join(name.center(col_width) for name in var_names + [output_name])
        separator = "─" * len(header)

        # Print table header
        print("\nTruth Table for " + output_name)
        print(separator)
        print(header)
        print(separator)

        # Generate all input combinations and outputs
        for i in range(rows):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                self.connect(var, '0' + str(bit))
                inputs.append("1" if bit else "0")

            output = self.objlist[gate].display_output()
            # Replace internal display values with clean T/F (or keep OFF/0/1 if needed)
            clean_output = output if output in ['OFF', '0/1'] else ('T' if output == 'T' else 'F')

            row = " | ".join(val.center(col_width) for val in inputs + [clean_output])
            print(row)

        print(separator)
        print()  # empty line at the end


    # diagnosis: this menu is AI generated and it's not the main part of code just to check errors in CLI mode
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
            comp_obj = self.objlist[comp_code]
            
            # Inputs (children)
            comp_name = self.decode(comp_code)
            input_0=[]
            input_1=[]
            for i in comp_obj.children[0]:
                input_0.append(self.decode(i))
            for i in comp_obj.children[1]:
                input_1.append(self.decode(i))
            children_0 = ", ".join(sorted(input_0)) if input_0 else "None"
            children_1 = ", ".join(sorted(input_1)) if input_1 else "None"
            
            # Outputs (parents)
            parents=[]
            for i in comp_obj.parents:
                parents.append(self.decode(i))
            parents = ", ".join(sorted(parents)) if parents else "None"
            
            # State
            state = comp_obj.display_output()
            
            print(row_format.format(comp_name, children_0, children_1, parents, state))
        
        print("-" * total_width)