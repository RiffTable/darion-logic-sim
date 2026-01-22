from Event_Manager import Event
from readchar import readkey, key
import os
from Const import Const


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


base = Event()


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
        print("S. Simulate Circuit")
        print("F. Flip-flop Mode")
        print("R. Reset Simulation")
        print("Ctrl+Z. Undo")
        print("Ctrl+Y. Redo")
        print("Ctrl+A. Copy Components")
        print("Ctrl+B. Paste Components")

        print("Enter your choice or press ESC to quit: ", end='')
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
                i = int(i)
                gate = base.addcomponent(i)

        elif choice == '2':
            base.listComponent()
            input('Press Enter to continue....')

        elif choice == '3':
            base.listComponent()
            gate = input(
                "Enter the serial of the gate you want to connect components: ")
            if gate == '':
                continue
            gate = base.canvas[int(gate)]
            childlist = list(
                map(int, input("Enter the serial of the component to connect to: ").split()))
            for child in childlist:
                child = base.canvas[child]
                try:
                    index = int(input(
                        f"Enter the input index (0-{gate.inputlimit - 1}) for {child} -> {gate}: "))
                except ValueError:
                    print("Invalid index. Skipping.")
                    continue

                if base.liveconnect(gate, child, index):
                    print(f"Connected {child} to {gate}.")
                else:
                    print('Not connected')
            input('Press Enter to continue....')

        elif choice == '4':
            base.listComponent()
            gate = input(
                "Enter the serial of the gate you want to disconnect components: ")
            if gate == '':
                continue
            gate = base.canvas[int(gate)]
            childlist = list(
                map(int, input("Enter the serial of the component to disconnect: ").split()))
            for child in childlist:
                child = base.canvas[child]
                indices = [i for i, c in enumerate(
                    gate.children) if c == child]
                if not indices:
                    print(f"{child} is not connected to {gate} inputs.")
                for index in indices:
                    base.livedisconnect(gate, index)
                    print(f"Disconnected {child} from {gate} index {index}.")
            input('Press Enter to continue....')

        elif choice == '5':
            base.listComponent()
            gatelist = list(map(int, input(
                "Enter the serial of the components you want to delete: ").split()))
            gatelist = [base.canvas[i] for i in gatelist]
            for gate in gatelist:
                base.livehide(gate)
                print(f"Deleted {gate}.")

        elif choice == '6':
            base.listVar()
            var = input("Enter the serial of the variable to set : ")
            if var == '':
                continue
            var = base.varlist[int(var)]
            value = input("Enter the value (0 or 1): ")
            if value in ['0', '1']:
                base.input(var, value)
                print(f"Variable {var} set to {value}.")
            else:
                print("Invalid value. Please try again")
            input('Press Enter to continue....')

        elif choice == '7':
            base.listComponent()
            gate = input(
                "Enter the serial of the gate you want to see output of: ")
            if gate == '':
                continue
            gate = base.canvas[int(gate)]
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
            # Show ICs and select one to configure
            if not base.iclist:
                print("No ICs in circuit.")
                input('Press Enter to continue....')
                continue
            for i, ic in enumerate(base.iclist):
                print(f'{i}. {ic}')
            try:
                ic = base.iclist[int(input('Select IC: '))]
            except (ValueError, IndexError):
                print("Invalid selection.")
                input('Press Enter to continue....')
                continue

            while True:
                clear_screen()
                print(f"=== IC: {ic.name} ===")
                print("1. View IC Info")
                print("2. Connect Pin")
                print("3. Disconnect Pin")
                print("ESC. Back")
                ic_choice = readkey()

                if ic_choice == '1':
                    ic.info()
                    input('Press Enter to continue....')

                elif ic_choice == '2':
                    print("\nConnect: [I]nput or [O]utput pin?")
                    pin_type = readkey().upper()
                    if pin_type == 'I':
                        ic.showinputpins()
                        pin = input('Pin #: ')
                        if pin == '':
                            continue
                        pin = ic.inputs[int(pin)]
                        base.listComponent()
                        gate = input('Connect to gate #: ')
                        if gate == '':
                            continue
                        gate = base.canvas[int(gate)]
                        base.connect(pin, gate)
                        print(f"Connected {gate} -> {pin.name}")
                    elif pin_type == 'O':
                        ic.showoutputpins()
                        pin = input('Pin #: ')
                        if pin == '':
                            continue
                        pin = ic.outputs[int(pin)]
                        base.listComponent()
                        gate = input('Connect from gate #: ')
                        if gate == '':
                            continue
                        gate = base.canvas[int(gate)]
                        base.connect(gate, pin)
                        print(f"Connected {pin.name} -> {gate}")
                    input('Press Enter to continue....')

                elif ic_choice == '3':
                    print("\nDisconnect: [I]nput or [O]utput pin?")
                    pin_type = readkey().upper()
                    if pin_type == 'I':
                        ic.showinputpins()
                        pin = input('Pin #: ')
                        if pin == '':
                            continue
                        pin = ic.inputs[int(pin)]
                        base.listComponent()
                        gate = input('Disconnect from gate #: ')
                        if gate == '':
                            continue
                        gate = base.canvas[int(gate)]
                        base.disconnect(pin, gate)
                        print(f"Disconnected {gate} from {pin.name}")
                    elif pin_type == 'O':
                        ic.showoutputpins()
                        pin = input('Pin #: ')
                        if pin == '':
                            continue
                        pin = ic.outputs[int(pin)]
                        base.listComponent()
                        gate = input('Disconnect from gate #: ')
                        if gate == '':
                            continue
                        gate = base.canvas[int(gate)]
                        base.disconnect(gate, pin)
                        print(f"Disconnected {pin.name} from {gate}")
                    input('Press Enter to continue....')

                elif ic_choice == key.ESC:
                    break

        elif choice.upper() == 'E':
            base.save_as_ic('x.json')
            print("IC designed and saved to file.txt")
            input('Press Enter to continue....')

        elif choice == key.CTRL_Z:
            base.undo()
            input('Press Enter to continue....')

        elif choice == key.CTRL_Y:
            base.redo()
            input('Press Enter to continue....')

        elif choice == key.CTRL_A:
            base.listComponent()
            complist = list(
                map(int, input("Enter the serial of the components you want to copy: ").split()))
            # each gate is a component but ic will add it's components
            complist = [base.canvas[i] for i in complist]
            base.copy(complist)
            print("Copied")
            input('Press Enter to continue....')

        elif choice == key.CTRL_B:
            base.paste()
            input('Press Enter to continue....')

        elif choice.upper() == 'S':
            base.simulate(Const.SIMULATE)
            print("Simulation started.")
            input('Press Enter to continue....')

        elif choice.upper() == 'F':
            base.simulate(Const.FLIPFLOP)
            print("Flip-flop mode activated.")
            input('Press Enter to continue....')

        elif choice.upper() == 'R':
            base.reset()
            print("Simulation reset.")
            input('Press Enter to continue....')

        elif choice == key.ESC:
            Const.MODE = Const.DESIGN
            print("Exiting Circuit Simulator......")
            input('Press Enter to continue....')
            clear_screen()
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    menu()
