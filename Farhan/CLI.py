from Backend import Circuit
from readchar import readkey,key
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

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

        print("Enter your choice or press ESC to quit: ",end='')
        choice = readkey()

        print()
        clear_screen()
        if choice == '1':
            base.addComponent()

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
                base.connect(gate_code, base.complist[child])
                if base.objlist[gate_code].output==-1:
                    base.fix(gate_code,base.complist[child])
                    print(f"Cannot connect {base.decode(base.complist[child])} & {base.decode(gate_code)} due to deadlock")
                else:    
                    print(f"Connected {base.decode(base.complist[child])} to {base.decode(gate_code)}.")
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
            input('Press Enter to continue....')
        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            for gate in gatelist:
                base.deleteComponent(base.complist[gate])
                print(f"Deleted {base.decode(base.complist[gate])}.")
                del base.complist[gate]
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
                    print(f"Variable {var} set to {value}.")
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
        elif choice == key.ESC:
            print("Exiting Circuit Simulator......")
            input('Press Enter to continue....')
            clear_screen()
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    menu()
