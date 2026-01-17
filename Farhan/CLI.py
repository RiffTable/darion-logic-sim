from Designer import Design
from readchar import readkey,key
import os
from IC import IC
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
        print("C. Load IC")        
        print("D. Configure IC")
        print("E. Save as IC")
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
            print("9. Probe")
            print("10. InputPin")
            print("11. OutputPin")
            choice = input("Enter your choice: ").split()
            for i in choice:
                i=int(i)
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
                if base.liveconnect(gate, child):                
                    print(f"Connected {child} to {gate}.")
                else:
                    print('Not connected')
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
            base.save('Latch.json')
            print("Circuit saved to file.txt")
            input('Press Enter to continue....')

        elif choice.upper() == 'B':
            base.load('Latch.json')
            print("Circuit loaded from file.txt")
            input('Press Enter to continue....')

        elif choice.upper() == 'C':
            base.getIC('x.json')
            print("IC created from file.txt")
            input('Press Enter to continue....')            

        elif choice.upper() == 'D':
            # show input and output gates of first list the ICs
            for i,ic in enumerate(base.iclist):
                print(f'{i}. {ic}')
            ic=base.iclist[int(input('Enter the serial of the IC you want to configure: '))]
            while True:
                clear_screen()
                print(f"--- Configuring IC: {ic.name} ---")
                print("1. Show Input Pins")
                print("2. Show Output Pins")
                print("3. Show IC Info")                
                print("4. Connect Input Pin")
                print("5. Disconnect Input Pin")
                print("6. Connect Output Pin")
                print("7. Disconnect Output Pin")
                print("ESC. Back")
                ic_choice=readkey()
                if ic_choice=='1':
                    ic.showinputpins()
                    input('Press Enter to continue....')
                elif ic_choice=='2':
                    ic.showoutputpins()
                    input('Press Enter to continue....')
                   
                elif ic_choice=='3':
                    ic.info()
                    input('Press Enter to continue....')
                                   
                elif ic_choice=='4':
                    ic.showinputpins()
                    pin=input('Enter the serial of the pin: ')
                    if pin=='':
                        continue
                    pin=ic.inputs[int(pin)]
                    base.listComponent()
                    gate=input('Enter the serial of the gate you want to connect: ')
                    if gate=='':
                        continue
                    gate=base.canvas[int(gate)]
                    base.connect(pin,gate)
                    input('Press Enter to continue....')  

                elif ic_choice=='5':
                    ic.showinputpins()
                    pin=input('Enter the serial of the pin: ')
                    if pin=='':
                        continue
                    pin=ic.inputs[int(pin)]
                    base.listComponent()
                    gate=input('Enter the serial of the gate you want to disconnect: ')
                    if gate=='':
                        continue
                    gate=base.canvas[int(gate)]
                    base.disconnect(pin,gate)
                    input('Press Enter to continue....')
                elif ic_choice=='6':
                    ic.showoutputpins()
                    pin=input('Enter the serial of the pin: ')
                    if pin=='':
                        continue
                    pin=ic.outputs[int(pin)]
                    base.listComponent()
                    gate=input('Enter the serial of the gate you want to connect: ')
                    if gate=='':
                        continue
                    gate=base.canvas[int(gate)]
                    base.connect(gate,pin)
                    input('Press Enter to continue....')
                elif ic_choice=='7':
                    ic.showoutputpins()
                    pin=input('Enter the serial of the pin: ')
                    if pin=='':
                        continue
                    pin=ic.outputs[int(pin)]
                    base.listComponent()
                    gate=input('Enter the serial of the gate you want to disconnect: ')
                    if gate=='':
                        continue
                    gate=base.canvas[int(gate)]
                    base.disconnect(gate,pin)
                    input('Press Enter to continue....')
                elif ic_choice==key.ESC:
                    break

        elif choice.upper() == 'E':
            base.save_as_ic('x.json')
            print("IC designed and saved to file.txt")
            input('Press Enter to continue....')
            

        elif choice==key.CTRL_Z:
            base.undo()
            input('Press Enter to continue....')         

        elif choice==key.CTRL_Y:
            base.redo()
            input('Press Enter to continue....') 

        elif choice==key.CTRL_A:
            base.listComponent()
            complist = list(map(int,input("Enter the serial of the components you want to copy: ").split()))
            # each gate is a component but ic will add it's components
            complist=[base.canvas[i] for i in complist]
            base.copy(complist)
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
