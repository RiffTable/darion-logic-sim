from Designer import Design
from readchar import readkey,key
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Usage
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
        print("6. Simulate")
        print("7. Show History")
      
        print("9. Diagnose Components")
        

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
                gate=base.stage_gate(i,'')

        elif choice == '2':
            base.liststage()
            input('Press Enter to continue....')

        elif choice == '3':
            base.liststage()
            gate = input("Enter the serial of the gate you want to connect components: ")
            if gate=='':
                continue
            gate=base.stage[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to connect to: ").split()))
            for child in childlist:
                child=base.stage[child]
                base.stage_connect(gate, child)
                print(f"Connected {child} to {gate}.")
            input('Press Enter to continue....')

        elif choice == '4':
            base.liststage()
            gate = input("Enter the serial of the gate you want to disconnect components: ")
            if gate=='':
                continue
            gate=base.stage[int(gate)]
            childlist = list(map(int,input("Enter the serial of the component to disconnect to: ").split()))
            for child in childlist:
                child=base.canvas[child]
                base.disconnect(gate, child)
                print(f"Disconnected {child} & {gate}.")
            input('Press Enter to continue....')

        elif choice == '5':
            base.liststage()
            gatelist = list(map(int,input("Enter the serial of the components you want to delete: ").split()))
            gatelist=[base.stage[i] for i in gatelist]
            for gate in gatelist:
                base.stage_delete(gate)
                print(f"Deleted {gate}.")
               
       #simulate 
        elif choice=='6':
            base.simulate()
            input('Press Enter to continue')
        elif choice=='7':
            # show history
            for keys,val in base.history.items():
                print(f'{keys}, {val}')
            input('Press Enter to continue')
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
