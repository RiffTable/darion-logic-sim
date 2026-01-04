from Gates import *

class Circuit:
    def __init__(self):
        self.objlist=[{} for i in range(9)]# holds the objects with code name
        self.complist=[]# displays the components 
        self.varlist=[]# holds variables with 0/1 input
        self.circuit_breaker={}# checks for loops while connecting
        self.gatelist=['NOT', 'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR']
        self.objlist[0]['0']=Signal(self,0)
        self.objlist[0]['1']=Signal(self,1)
        self.objlist[0]['-1']=Signal(self,-1)
        self.copydata=[]

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

        if gate[0]=='8' and child[0]!='0':
            return

        if child in gate_obj.children[val]:# no need to reconnect if connected
            return

        if gate[0]=='8' or gate[0]=='1':
            # variable and not gate will have atmost one input so i need to erase
            # child set to add new child
            for input in [0,1,-1]:

                cuccoo=[i for i in gate_obj.children[input] ]
                for exclude_child in cuccoo:                    
                    self.getobj(exclude_child).parents.discard(gate)
                    gate_obj.children[input].discard(exclude_child)            

        for remove_from in [0,1,-1] :
            if remove_from!=val:
                if child in gate_obj.children[remove_from]:
                    # if the value of a child is changed 
                    # it pre exists in the other value so i have to delete it
                    gate_obj.children[remove_from].discard(child)
        gate_obj.children[val].add(child)        

        # connect children to it as their parent
        if child[0]!='0' and gate not in child_obj.parents:
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
        parent_obj.children[0].discard(child)
        parent_obj.children[1].discard(child)# delete child 
        parent_obj.children[-1].discard(child)
        child_obj.parents.discard(parent)
        if parent[0]=='8':
            self.connect(parent,'00')
        else:
            child_obj.process()
            self.update(child)
            parent_obj.process()# modify output after removing child
            self.update(parent)

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
        if gate[0]=='8' and gate in self.varlist:
                self.varlist.remove(gate)
        gate_obj.parents=set(parent for parent in parent_list)
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
            # i removed parity check here so if i get errors it's because of this
            if prev!=out:
                for parent in gate_obj.parents:
                    self.connect(parent,gate)
                    if self.getobj(parent).output==-1:
                        break
            self.circuit_breaker[gate]=-1
        elif self.circuit_breaker[gate]==out:
            return
        else:
            # print('Loop Detected')  
            gate_obj.prev_output=gate_obj.output
            gate_obj.output=-1
            self.poison(gate)
        

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

        child_obj.parents.discard(parent)
        parent_obj.children[0].discard(child)
        parent_obj.children[1].discard(child)
        
        if parent[0]=='8':
            self.connect(parent,'00')
        else:
            self.correction(parent)

    def poison(self,gate):
        gate_obj=self.getobj(gate)
        gate_obj.output=-1
        for parent in gate_obj.parents:
            parent_obj=self.getobj(parent)
            parent_obj.children[-1].add(gate)
            parent_obj.children[0].discard(gate)
            parent_obj.children[1].discard(gate)
            if parent_obj.output!=-1:
                self.poison(parent)

    # Result 
    def output(self,gate):
        print(f'{self.getname(gate)} output is {self.getobj(gate).getoutput()}')


    # Truth Table
    def truthTable(self):
        if len(self.varlist) == 0:
            return
        
        output_list=[i for i in self.complist if i not in self.varlist]
        n = len(self.varlist)
        rows = 1 << n
        output_list.sort()
        # Collect decoded variable names and the output gate name
        var_names = [self.getname(v) for v in self.varlist]
        output_name=[self.getname(v) for v in output_list]

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
                self.connect(var, '0' + str(bit))
                inputs.append("1" if bit else "0")
            output=[self.getobj(gate).getoutput() for gate in output_list]
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
        
        for comp_code in self.complist:
            comp_obj = self.getobj(comp_code)
            
            # Inputs (children)
            comp_name = self.getname(comp_code)
            input_0=[]
            input_1=[]
            Error=[]
            for i in comp_obj.children[0]:
                input_0.append(self.getname(i))
            for i in comp_obj.children[1]:
                input_1.append(self.getname(i))
            for i in comp_obj.children[-1]:
                Error.append(self.getname(i))
            children_0 = ", ".join(sorted(input_0)) if input_0 else "None"
            children_1 = ", ".join(sorted(input_1)) if input_1 else "None"
            children_neg = ", ".join(sorted(Error)) if Error else "None"
            
            # Outputs (parents)
            parents=[]
            for i in comp_obj.parents:
                parents.append(self.getname(i))
            parents = ", ".join(sorted(parents)) if parents else "None"
            
            # State
            state = comp_obj.getoutput()
            
            print(row_format.format(comp_name, children_0, children_1,children_neg, parents, state))
        
        print("-" * total_width)
        
    def writetofile(self,address):
        # write the component list to file
        f=open(address,'w')

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

    # read from file
    def readfromfile(self,address):
        f=open(address,'r')        
        components=f.readline().split(' ')
        components.pop()
        if len(components)==0:
            return
        pivot=[0,NOT.rank,AND.rank,NAND.rank,OR.rank,NOR.rank,XOR.rank,XNOR.rank,Variable.rank]   
        pseudo={}
        pseudo['00']='00'
        pseudo['01']='01'

        # create components
        for component in components:
            old_rank=int(component[1:])
            identity=component[0]
            new_code=identity+str(old_rank+pivot[int(identity)])
            self.getcomponent(identity,new_code)
            if identity=='8':
                self.getobj(component).children[0].clear()
            pseudo[component]=new_code
        connections=f.read().split('\n')
        connections.pop()
        for line in connections:
            line=line.split(' ')
            gate=line[0]
            children_0=line[1].split(',')
            if 'X' not in children_0:
                for child in children_0:
                    self.passive_connect(pseudo[gate],pseudo[child],0)
            children_1=line[2].split(',')
            if 'X' not in children_1:
                for child in children_1:
                    self.passive_connect(pseudo[gate],pseudo[child],1)
            output=line[3]
            self.getobj(gate).output=int(output)
        f.close()

    def rank_reset(self):
        if len(self.objlist[1]):
            NOT.rank=int(max(self.objlist[1]))
        else:
            NOT.rank=0
        if len(self.objlist[2]):
            AND.rank=int(max(self.objlist[2]))
        else:
            AND.rank=0
        if len(self.objlist[3]):
            NAND.rank=int(max(self.objlist[3]))
        else:
            NAND.rank=0
        if len(self.objlist[4]):
            OR.rank=int(max(self.objlist[4]))
        else:
            OR.rank=0
        if len(self.objlist[5]):
            NOR.rank=int(max(self.objlist[5]))
        else:
            NOR.rank=0
        if len(self.objlist[6]):
            XOR.rank=int(max(self.objlist[6]))
        else:
            XOR.rank=0
        if len(self.objlist[7]):
            XNOR.rank=int(max(self.objlist[7]))
        else:
            XNOR.rank=0
        if len(self.objlist[8]):
            Variable.rank=int(max(self.objlist[8]))+1
        else:
            Variable.rank=0
            
            
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
        for i in range(1,len(self.objlist)):
            self.objlist[i].clear()
        self.varlist.clear()
        self.complist.clear()

    def copy(self,components):
        if len(components)==0:
            return
        self.copydata.clear()
        self.copydata.append(','.join(components))
        for component in components:
            obj=self.getobj(component)
            info=component
            info+=' '
            children=obj.children[0]|obj.children[1]|obj.children[-1]
            copychild=[]
            for child in children:
                if child in components or child[0]=='0':
                    copychild.append(child)
            copychild=','.join(copychild)
            if len(copychild)==0:
                copychild='X'
            info+=copychild
            self.copydata.append(info)

    def paste(self):
        pivot=[0,NOT.rank,AND.rank,NAND.rank,OR.rank,NOR.rank,XOR.rank,XNOR.rank,Variable.rank]   
        if len(self.copydata)==0:
            return
        components=self.copydata[0]
        pseudo={}
        pseudo['00']='00'
        pseudo['01']='01'
        new_items=[]
        for component in components.split(','):
            old_rank=int(component[1:])
            identity=component[0]
            new_code=identity+str(old_rank+pivot[int(identity)])
            self.getcomponent(identity,new_code)
            pseudo[component]=new_code
            new_items.append(new_code)
        connections=[self.copydata[i] for i in range(1,len(self.copydata))]
        for line in connections:
            line=line.split(' ')
            gate=line[0]
            children=line[1].split(',')
            if 'X' not in children:
                for child in children :
                    self.connect(pseudo[gate],pseudo[child])
        return new_items


        