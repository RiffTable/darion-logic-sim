from Backend import Circuit
from readchar import readkey,key
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
                token='1 '+gate
                addtoundo(undolist,redolist,token)

        elif choice == '2':
            base.listComponent()
            input('Press Enter to continue....')

        elif choice == '3':
            base.listComponent()
            gate_code = input("Enter the serial of the gate you want to connect components: ")
            if gate_code=='':
                continue
            gate_code=base.complist[int(gate_code)]
            childlist = list(map(int,input("Enter the serial of the component to connect to: ").split()))
            for child in childlist:
                child=base.complist[child]
                base.connect(gate_code, child)

                if base.getobj(gate_code).output==-1:
                    print(f"Deadlock occured! please disconnect gates")
                    token='3 '+gate_code+' '+ child
                    addtoundo(undolist,redolist,token)
                elif base.getobj(child)==-1:
                    print(f'Cannot connect {base.decode(child)} to {base.decode(gate_code)}')
                else:
                    print(f"Connected {base.decode(child)} to {base.decode(gate_code)}.")
                    token='3 '+gate_code+' '+ child
                    addtoundo(undolist,redolist,token)
            input('Press Enter to continue....')

        elif choice == '4':
            base.listComponent()
            gate_code = input("Enter the serial of the gate you want to disconnect components: ")
            if gate_code=='':
                continue
            gate_code=base.complist[int(gate_code)]

            childlist = list(map(int,input("Enter the serial of the component to disconnect to: ").split()))
            for child in childlist:
                base.disconnect(gate_code, base.complist[child])
                print(f"Disconnected {base.decode(base.complist[child])} & {base.decode(gate_code)}.")
                token='4 '+gate_code+' '+ child
                addtoundo(undolist,redolist,token)
            input('Press Enter to continue....')

        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            exclusionlist=[]
            for gate in gatelist:
                gate=base.complist[int(gate)]
                base.deleteComponent(gate)
                print(f"Deleted {base.decode(gate)}.")
                exclusionlist.append(gate)
            for gate in exclusionlist:
                base.complist.remove(gate)
                token='2 '+gate
                addtoundo(undolist,redolist,token)

        elif choice == '6':
            base.listVar()
            var = input("Enter the serial of the variable to set : ")
            if var=='':
                continue
            var=base.varlist[int(var)]
            if var in base.varlist:
                value = input("Enter the value (0 or 1): ")
                if value in ['0', '1']:
                    base.connect(var, '0'+value)
                    base.fix_var(var)
                    print(f"Variable {base.decode(var)} set to {value}.")
                    token='3 '+var+' '+ '0'+value
                    addtoundo(undolist,redolist,token)
                else:
                    print("Invalid value. Please try again")
            input('Press Enter to continue....')

        elif choice == '7':
            base.listComponent()
            gate_code = input("Enter the serial of the gate you want to see output of: ")
            if gate_code=='':
                continue
            gate_code=base.complist[int(gate_code)]
            base.output(gate_code)
            input('Press Enter to continue....')
            
        elif choice == '8':
            base.listComponent()
            gate_code = input("Enter the serial of the gate you want to see Truth Table of: ")
            if gate_code=='':
                continue
            gate_code=base.complist[int(gate_code)]
            base.truthTable(gate_code)
            input('Press Enter to continue....')

        elif choice == '9':
            base.diagnose()
            input('Press Enter to continue....')
            
        elif choice.upper() == 'A':
            base.writetofile()
            print("Circuit saved to file.txt")
            input('Press Enter to continue....')

        elif choice.upper() == 'B':
            base.clearcircuit()
            undolist.clear()
            redolist.clear()
            base.readfromfile()
            print("Circuit loaded from file.txt")
            input('Press Enter to continue....')

        elif choice==key.CTRL_Z:
            if len(undolist)==0:
                continue
            event=popfromundo(undolist,redolist)
            event=event.split()
            command =event[0]            
            if command=='1':
                gate=event[1]
                base.deleteComponent(gate)
                base.complist.remove(gate)
            elif command=='2':
                gate=event[1]
                base.renewComponent(gate)
                base.complist.append(gate)
            elif command=='3':
                gate1=event[1]
                gate2=event[2]
                if gate1[0]=='8' and gate2[0]=='0':
                    if gate2[1]=='0':
                        base.connect(gate1,'0'+'1')
                    elif gate2[1]=='1':
                        base.connect(gate1,'0'+'0')
                else:
                    if base.getobj(gate1).output==-1:
                        base.fallback(gate1,gate2)
                    else: 
                        base.disconnect(gate1,gate2)
            elif command=='4':
                gate1=event[1]
                gate2=event[2]
                base.connect(gate1,gate2)
            input('Press Enter to continue....')

            
        elif choice==key.CTRL_Y:
            if len(redolist)==0:
                continue
            event=popfromredo(undolist,redolist)
            event=event.split()
            command =event[0]            
            if command=='1':
                gate=event[1]
                base.renewComponent(gate)
                base.complist.append(gate)
                
            elif command=='2':
                gate=event[1]
                base.deleteComponent(gate)
                base.complist.remove(gate)
                
            elif command=='3':
                gate1=event[1]
                gate2=event[2]
                base.connect(gate1,gate2)
                
            elif command=='4':
                gate1=event[1]
                gate2=event[2]
                base.disconnect(gate1,gate2)

        elif choice == key.ESC:            
            print("Exiting Circuit Simulator......")
            input('Press Enter to continue....')
            clear_screen()
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    menu()
