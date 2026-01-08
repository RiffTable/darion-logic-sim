from Designer import Design
from readchar import readkey,key
from Gates import Variable
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


base=Design()

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
                gate=base.addcomponent(i)
                

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
                base.liveconnect(gate, child)
                if gate.output==-1:
                    print(f"Deadlock occured! please undo")                    
                else:
                    print(f"Connected {child} to {gate}.")
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
                base.livedisconnect(gate, child)
                print(f"Disconnected {child} & {gate}.")
            input('Press Enter to continue....')

        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            gatelist=[base.canvas[i] for i in gatelist]
            for gate in gatelist:
                base.livehide(gate)
                print(f"Deleted {gate}.")

        elif choice == '6':
            base.listVar()
            var = input("Enter the serial of the variable to set : ")
            if var=='':
                continue
            var=base.varlist[int(var)]
            value = input("Enter the value (0 or 1): ")
            if value in ['0','1']:
                base.input(var, value)
                print(f"Variable {var} set to {value}.")
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
            base.save('file.txt')
            print("Circuit saved to file.txt")
            input('Press Enter to continue....')

        elif choice.upper() == 'B':
            base.load('file.txt')
            print("Circuit loaded from file.txt")
            input('Press Enter to continue....')

        elif choice==key.CTRL_Z:
            base.undo()
            input('Press Enter to continue....')         

        elif choice==key.CTRL_Y:
            base.redo()
            input('Press Enter to continue....') 

        elif choice==key.CTRL_A:
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to copy: ").split()))
            gatelist=[base.canvas[i].code for i in gatelist]

            base.copy(gatelist)
            print("Copied")
            input('Press Enter to continue....')

        elif choice==key.CTRL_B:            
            base.paste()
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
