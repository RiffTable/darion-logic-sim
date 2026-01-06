from Circuit import Circuit
from readchar import readkey,key
from Gates import Variable
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

undolist=[]
redolist=[]
def addtoundo(undo,redo,token):
    undo.append(token)
    redo.clear
def popfromundo(undo,redo):
    x=undo.pop()
    redo.append(x)
    return x
def popfromredo(undo,redo):
    x=redo.pop()
    undo.append(x)
    return x
# Usage
base=Circuit()

def menu():

    while True:
        clear_screen()
        print("--- Circuit Simulator Menu ---")
        print("1. Add Component")
        print("2. List Components")
        print("3. Connect Components")
        print("4. Disconnect Components")
        print("5. Delete Components")
        print("6. Set Input Variable Value")
        print("7. Show Output of a Component")
        print("8. Show Truth Table of a Component")
        print("9. Diagnose Components")
        print("A. Save Circuit to File")
        print("B. Load Circuit from File")
        print("Ctrl+Z. Undo")
        print("Ctrl+Y. Redo")

        print("Enter your choice or press ESC to quit: ",end='')
        choice = readkey()

        print()
        clear_screen()
        if choice == '1':
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
                gate=base.getcomponent(i,'')
                token='1 '+gate.code
                addtoundo(undolist,redolist,token)

        elif choice == '2':
            base.listComponent()
            input('Press Enter to continue....')

        elif choice == '3':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to connect components: ")
            if gate=='':
                continue
            gate=base.complist[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to connect to: ").split()))
            for child in childlist:
                child=base.complist[child]
                base.connect(gate, child)
                if gate.output==-1:
                    print(f"Deadlock occured! please undo")
                    token='3 '+gate.code+' '+ child.code
                    addtoundo(undolist,redolist,token)
                elif child==-1:
                    print(f'Cannot connect {child} to {gate}')
                else:
                    print(f"Connected {child} to {gate}.")
                    token='3 '+gate.code+' '+ child.code
                    addtoundo(undolist,redolist,token)
            input('Press Enter to continue....')

        elif choice == '4':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to disconnect components: ")
            if gate=='':
                continue
            gate=base.complist[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to disconnect to: ").split()))
            for child in childlist:
                child=base.complist[child]
                base.disconnect(gate, child)
                print(f"Disconnected {child} & {gate}.")
                token='4 '+gate.code+' '+ child.code
                addtoundo(undolist,redolist,token)
            input('Press Enter to continue....')

        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            gatelist=[base.complist[i] for i in gatelist]
            exclusionlist=[]
            for gate in gatelist:
                base.deleteComponent(gate)
                print(f"Deleted {gate}.")
                exclusionlist.append(gate)
            for gate in exclusionlist:
                base.complist.remove(gate)
                token='2 '+gate.code
                addtoundo(undolist,redolist,token)

        elif choice == '6':
            base.listVar()
            var = input("Enter the serial of the variable to set : ")
            if var=='':
                continue
            var=base.varlist[int(var)]
            value = input("Enter the value (0 or 1): ")
            if value in ['0', '1']:
                base.switch(var, value)
                print(f"Variable {var} set to {value}.")
                token='3 '+var.code
                addtoundo(undolist,redolist,token)
            else:
                print("Invalid value. Please try again")
            input('Press Enter to continue....')

        elif choice == '7':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to see output of: ")
            if gate=='':
                continue
            gate=base.complist[int(gate)]
            base.output(gate)
            input('Press Enter to continue....')
            
        elif choice == '8':
            print(base.truthTable())
            input('Press Enter to continue....')

        elif choice == '9':
            base.diagnose()
            input('Press Enter to continue....')
            
        elif choice.upper() == 'A':
            base.writetofile('file.txt')
            print("Circuit saved to file.txt")
            input('Press Enter to continue....')

        elif choice.upper() == 'B':
            base.clearcircuit()
            undolist.clear()
            redolist.clear()
            base.readfromfile('file.txt')
            print("Circuit loaded from file.txt")
            input('Press Enter to continue....')

        elif choice==key.CTRL_Z:
            if len(undolist)==0:
                continue
            event=popfromundo(undolist,redolist)
            event=event.split()
            command =event[0]            

            if command=='1':
                gate=base.getobj(event[1])
                base.deleteComponent(gate)
                base.complist.remove(gate)

            elif command=='2':
                gate=base.getobj(event[1])
                base.renewComponent(gate)
                base.complist.append(gate)

            elif command=='3':
                gate1=base.getobj(event[1])
                if isinstance(gate1,Variable):
                    base.switch(gate1,str(gate1.output^1))
                    continue
                gate2=base.getobj(event[2])               
                base.disconnect(gate1,gate2)

            elif command=='4':
                gate1=base.getobj(event[1])
                gate2=base.getobj(event[2])
                base.connect(gate1,gate2)

            elif command=='5':
                gates=event[2].split(',')
                for i in gates:
                    i=base.getobj(i)
                    base.deleteComponent(i)
                    del base.circuit_breaker[i]
                    del base.objlist[i.code]
                    base.complist.remove(i)
                base.rank_reset()
            input('Press Enter to continue....')         

        elif choice==key.CTRL_Y:
            if len(redolist)==0:
                continue
            event=popfromredo(undolist,redolist)
            event=event.split()
            command =event[0]   

            if command=='1':
                gate=base.getobj(event[1])
                base.renewComponent(gate)
                base.complist.append(gate)
                
            elif command=='2':
                gate=base.getobj(event[1])
                base.deleteComponent(gate)
                base.complist.remove(gate)
                
            elif command=='3':
                gate1=base.getobj(event[1])
                if isinstance(gate1,Variable):
                    base.switch(gate1,str(gate1.output^1))
                    continue
                gate2=base.getobj(event[2])               
                base.connect(gate1,gate2)
                
            elif command=='4':
                gate1=base.getobj(event[1])
                gate2=base.getobj(event[2])
                base.disconnect(gate1,gate2)

            elif command=='5':
                gates=event[1].split(',')
                base.copy(gates)
                base.paste()
            input('Press Enter to continue....') 

        elif choice==key.CTRL_A:
            components=[]
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to copy: ").split()))
            gatelist=[base.complist[i].code for i in gatelist]
            for gate in gatelist:
                components.append(gate)
            base.copy(components)
            print("Copied")
            input('Press Enter to continue....')

        elif choice==key.CTRL_B:            
            if len(base.copydata):
                source=base.copydata[0]
                gates=base.paste()
                gates=','.join(gates)
                addtoundo(undolist,redolist,'5 '+source+' '+gates)
                print("Pasted")
            else:
                print('Nothing to paste')         
            input('Press Enter to continue....')

        elif choice == key.ESC:            
            print("Exiting Circuit Simulator......")
            input('Press Enter to continue....')
            clear_screen()
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    menu()
