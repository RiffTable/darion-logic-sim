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
        print("Ctrl+A. Copy Components")
        print("Ctrl+B. Paste Components")

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
                base.solder(gate)
                addtoundo(undolist,redolist,(1,gate))

        elif choice == '2':
            base.listComponent()
            input('Press Enter to continue....')

        elif choice == '3':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to connect components: ")
            if gate=='':
                continue
            gate=base.canvas[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to connect to: ").split()))
            for child in childlist:
                child=base.canvas[child]
                base.connect(gate, child)
                if gate.output==-1:
                    print(f"Deadlock occured! please undo")                    
                else:
                    print(f"Connected {child} to {gate}.")
                addtoundo(undolist,redolist,(3,gate,child))
            input('Press Enter to continue....')

        elif choice == '4':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to disconnect components: ")
            if gate=='':
                continue
            gate=base.canvas[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to disconnect to: ").split()))
            for child in childlist:
                child=base.canvas[child]
                base.disconnect(gate, child)
                print(f"Disconnected {child} & {gate}.")
                addtoundo(undolist,redolist,(4,gate,child))
            input('Press Enter to continue....')

        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            gatelist=[base.canvas[i] for i in gatelist]
            for gate in gatelist:
                base.hideComponent(gate)
                print(f"Deleted {gate}.")
                addtoundo(undolist,redolist,(2,gate))

        elif choice == '6':
            base.listVar()
            var = input("Enter the serial of the variable to set : ")
            if var=='':
                continue
            var=base.varlist[int(var)]
            value = input("Enter the value (0 or 1): ")
            if value in ['0','1']:
                base.connect(var, base.sign_1 if value=='1' else base.sign_0)
                print(f"Variable {var} set to {value}.")
                addtoundo(undolist,redolist,(3,var))
            else:
                print("Invalid value. Please try again")
            input('Press Enter to continue....')

        elif choice == '7':
            base.listComponent()
            gate = input("Enter the serial of the gate you want to see output of: ")
            if gate=='':
                continue
            gate=base.canvas[int(gate)]
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
            command =event[0]            

            if command==1:
                base.hideComponent(event[1])

            elif command==2:
                base.renewComponent(event[1])

            elif command==3:
                gate1=event[1]
                if isinstance(gate1,Variable):
                    base.connect(gate1,base.sign_1 if gate1.output==0 else base.sign_0)
                    continue
                gate2=event[2]              
                base.disconnect(gate1,gate2)

            elif command==4:
                base.connect(event[1],event[2])

            elif command==5:
                gates=event[2].split(',')
                for i in gates:
                    base.terminate(base.getobj(i))
                base.rank_reset()
            input('Press Enter to continue....')         

        elif choice==key.CTRL_Y:
            if len(redolist)==0:
                continue
            event=popfromredo(undolist,redolist)
            command =event[0]   

            if command==1:
                base.renewComponent(event[1])
                
            elif command==2:
                base.hideComponent(event[1])
                
            elif command==3:
                gate1=event[1]
                if isinstance(gate1,Variable):
                    base.connect(gate1,base.sign_1 if gate1.output==0 else base.sign_0)
                    continue
                gate2=event[2]              
                base.connect(gate1,gate2)
                
            elif command==4:
                base.disconnect(event[1],event[2])

            elif command==5:
                gates=event[1].split(',')
                base.copy(gates)
                base.paste()
            input('Press Enter to continue....') 

        elif choice==key.CTRL_A:
            components=[]
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to copy: ").split()))
            gatelist=[base.canvas[i].code for i in gatelist]
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
                addtoundo(undolist,redolist,(5,source,gates))
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
