import os
import sys
import argparse

# Parse arguments for reactor selection
parser = argparse.ArgumentParser(description='Run Logic Sim CLI')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

# Add control to path
sys.path.append(os.path.join(root_dir, 'control'))

use_reactor = False

# Backend Selection Logic
if args.reactor:
    use_reactor = True
elif args.engine:
    use_reactor = False
else:
    # Interactive prompt
    print("\nSelect Backend:")
    print("1. Engine (Python) [Default]")
    print("2. Reactor (Cython)")
    choice = input("Choice (1/2): ").strip()
    if choice == '2':
        use_reactor = True
    else:
        use_reactor = False

# Add engine or reactor to path
if use_reactor:
    print("Using Reactor (Cython) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

try:
    from Event_Manager import Event
    from Control import Add, AddIC, Delete, Connect, Disconnect, Paste, Toggle, SetLimits, Rename
    from Circuit import Circuit
    from Gates import Variable, Probe
    import Const
    from IC import IC
except ImportError as e:
    print(f"FATAL ERROR: Could not import backend modules: {e}")
    if args.reactor:
        print("Ensure you have built the reactor (python setup.py build_ext --inplace)")
    sys.exit(1)


def clear_screen():
    # clears the clutter
    os.system('cls' if os.name == 'nt' else 'clear')


circuit = Circuit()
base = Event()

# Helper functions for commands
def addcomponent(choice):
    cmd = Add(circuit, choice)
    if cmd.execute():
        base.register(cmd)

def connect(target, source, index):
    cmd = Connect(circuit, target, source, index)
    if cmd.execute():
        base.register(cmd)
        return True
    return False

def disconnect(target, index):
    cmd = Disconnect(circuit, target, index)
    if cmd.execute():
        base.register(cmd)
        return True
    return False

def hide(gatelist):
    cmd = Delete(circuit, gatelist)
    if cmd.execute():
        base.register(cmd)

def copy(gatelist):
    circuit.copy(gatelist)

def paste():
    cmd = Paste(circuit)
    if cmd.execute():
        base.register(cmd)

def input_toggle(target, val):
    cmd = Toggle(circuit, target, val)
    if cmd.execute():
        base.register(cmd)

def setlimits(target, size):
    cmd = SetLimits(target, size)
    if cmd.execute():
        base.register(cmd)
        return True
    return False

def rename(target, new_name):
    cmd = Rename(target, new_name)
    if cmd.execute():
        base.register(cmd)
        return True
    return False

def addic(name):
    cmd = AddIC(circuit, name)
    if cmd.execute():
        base.register(cmd)
        return True
    return False



# The main loop that talks to the user
def menu():
    while True:
        clear_screen()
        print("--- Circuit Simulator ---")
        print("1. Components & Connections")
        print("2. Simulation & Analysis")
        print("3. Project Management (Files & ICs)")
        print("4. Undo")
        print("5. Redo")
        print("E. Exit")
        
        choice = input("\nEnter your choice: ").strip().upper()

        if choice == '1':
            submenu_components()
        elif choice == '2':
            submenu_simulation()
        elif choice == '3':
            submenu_project()
        elif choice == '4':
            base.undo()
            input("Undone. Press Enter...")
        elif choice == '5':
            base.redo()
            input("Redone. Press Enter...")
        elif choice == 'E':
            Const.MODE = Const.DESIGN
            print("Exiting Circuit Simulator......")
            break
        else:
            print("Invalid choice. Please try again.")
            input("Press Enter...")

def submenu_components():
    while True:
        clear_screen()
        print("--- Components & Connections ---")
        print("1. Add Component")
        print("2. List Components")
        print("3. Connect Components")
        print("4. Disconnect Components")
        print("5. Delete Components")
        print("6. Copy Selection")
        print("7. Paste Selection")
        print("8. Rename Component")
        print("9. Change Input Limit")
        print("B. Back to Main Menu")
        
        choice = input("\nSelect Option: ").strip().upper()
        
        if choice == '1':
            # Add Component section
            print("\nChoose a gate to add:")
            print("0. AND  1. NAND  2. OR  3. NOR  4. XOR")
            print("5. XNOR  6. NOT  7. Variable  8. Probe")
            print("9. InputPin  10. OutputPin")
            
            c = input("Enter choices (space separated): ").split()
            for i in c:
                try:
                    val = int(i)
                    addcomponent(val)
                except ValueError:
                    continue

        elif choice == '2':
            circuit.listComponent()
            input('Press Enter to continue....')

        elif choice == '3':
            # Connect Components section
            circuit.listComponent()
            gate_idx = input("Enter Target Serial (Target): ")
            if gate_idx == '': continue
            try:
                target_component = circuit.canvas[int(gate_idx)]
            except (ValueError, IndexError):
                print("Invalid Target.")
                input("Press Enter...")
                continue

            sourcelist_indices = list(map(int, input("Enter Source Serials (Source): ").split()))

            for source_idx in sourcelist_indices:
                try:
                    source_component = circuit.canvas[source_idx]
                except IndexError:
                    continue

                # Handle Source Selection (Source)
                actual_source = source_component
                if isinstance(source_component, IC):
                    print(f"\nSelect Output Pin for Source IC '{source_component.name}':")
                    for k, pin in enumerate(source_component.outputs):
                        print(f"{k}: {pin.name}")
                    try:
                        pin_idx = int(input(f"Select Pin (0-{len(source_component.outputs)-1}): "))
                        actual_source = source_component.outputs[pin_idx]
                    except (ValueError, IndexError):
                        print("Invalid Pin. Skipping.")
                        continue

                # Handle Target Selection (Target)
                actual_target = target_component
                target_index = 0

                if isinstance(target_component, IC):
                    print(f"\nSelect Input Pin for Target IC '{target_component.name}':")
                    for k, pin in enumerate(target_component.inputs):
                        current_source = pin.sources[0] if pin.sources and str(pin.sources[0]) != 'Empty' else "Empty"
                        print(f"{k}: {pin.name} (Current: {current_source})")
                    try:
                        pin_idx = int(input(f"Select Pin (0-{len(target_component.inputs)-1}): "))
                        actual_target = target_component.inputs[pin_idx]
                        target_index = 0
                    except (ValueError, IndexError):
                        print("Invalid Pin. Skipping.")
                        continue
                else:
                    print(f"\nTarget Gate '{target_component.name}' Inputs:")
                    for k, c in enumerate(target_component.sources):
                        print(f"Index {k}: {c}")
                    try:
                        target_index = int(input(f"Enter input index for {actual_source} -> {target_component}: "))
                    except ValueError:
                        print("Invalid index. Skipping.")
                        continue

                if connect(actual_target, actual_source, target_index):
                    print(f"Connected {actual_source} to {actual_target}.")
                else:
                    print('Not connected')
            input('Press Enter to continue....')

        elif choice == '4':
            circuit.listComponent()
            gate_idx = input("Enter Target Serial to Disconnect: ")
            if gate_idx == '': continue
            try:
                target = circuit.canvas[int(gate_idx)]
            except (ValueError, IndexError):
                print("Invalid serial.")
                input("Press Enter...")
                continue

            if isinstance(target, IC):
                print(f"\n=== IC '{target.name}' - Input Pins ===")
                has_connections = False
                for i, pin in enumerate(target.inputs):
                    source = pin.sources[0]
                    conn_str = str(source) if str(source) != 'Empty' else "Empty"
                    print(f"[{i}] {pin.name} <-- {conn_str}")
                    if str(source) != 'Empty':
                        has_connections = True
                
                if not has_connections:
                    print("No connections to disconnect.")
                    input('Press Enter...')
                    continue

                indices_input = input("\nEnter Pin indices to disconnect: ")
                if indices_input == '': continue
                try:
                    indices = list(map(int, indices_input.split()))
                    for index in indices:
                        if index < 0 or index >= len(target.inputs): continue
                        target_pin = target.inputs[index]
                        if str(target_pin.sources[0]) == 'Empty': continue
                        source_name = str(target_pin.sources[0])
                        disconnect(target_pin, 0)
                        print(f"Disconnected {source_name} from Pin {index}.")
                except ValueError: pass

            elif isinstance(target, Variable)==False:
                print(f"\n=== {target} - Input Pins ===")
                has_connections = False
                for i, source in enumerate(target.sources):
                    print(f"[{i}] -> {source}")
                    if str(source) != 'Empty': has_connections = True
                
                if not has_connections:
                    print("No connections.")
                    input('Press Enter...')
                    continue
                
                indices_input = input("\nEnter indices to disconnect: ")
                if indices_input == '': continue
                try:
                    indices = list(map(int, indices_input.split()))
                    for index in indices:
                        if index < 0 or index >= len(target.sources): continue
                        if str(target.sources[index]) == 'Empty': continue
                        disconnect(target, index)
                        print(f"Disconnected index {index}.")
                except ValueError: pass
            input('Press Enter to continue....')

        elif choice == '5':
            circuit.listComponent()
            gatelist = input("Enter serials to delete: ").split()
            gates_to_delete = []
            for i in gatelist:
                try:
                    gate = circuit.canvas[int(i)]
                    gates_to_delete.append(gate)
                except (ValueError, IndexError):
                    pass
            if gates_to_delete:
                hide(gates_to_delete)
                for gate in gates_to_delete:
                    print(f"Deleted {gate}.",end=' ')
            input("\nPress Enter...")

        elif choice == '6':
            circuit.listComponent()
            try:
                complist = list(map(int, input("Enter serials to copy: ").split()))
                complist = [circuit.canvas[i] for i in complist]
                copy(complist)
                print("Copied")
            except (ValueError, IndexError):
                print("Error in selection.")
            input('Press Enter...')

        elif choice == '7':
            paste()
            print("Pasted.")
            input('Press Enter...')

        elif choice == '8':
            circuit.listComponent()
            idx = input("Enter serial to rename: ")
            if idx == '': continue
            try:
                comp = circuit.canvas[int(idx)]
                # "Not ICs after they are imported"
                if isinstance(comp, IC):
                    print("Cannot rename imported ICs.")
                else:
                    new_name = input(f"Enter new name for {comp.name}: ")
                    if new_name:
                        rename(comp, new_name)
                        print(f"Renamed to {new_name}")
            except (ValueError, IndexError):
                print("Invalid selection.")
            input("Press Enter...")

        elif choice == '9':
            circuit.listComponent()
            idx = input("Enter serial of component to change input limit: ")
            if idx == '': continue
            try:
                comp = circuit.canvas[int(idx)]
                # ICs and Variables/Probes have fixed input limits
                if isinstance(comp, IC):
                    print("Cannot change input limit of ICs.")
                elif isinstance(comp, (Variable, Probe)):
                    print("Cannot change input limit of Variables/Probes.")
                elif not hasattr(comp, 'setlimits') or not hasattr(comp, 'inputlimit'):
                    print("This component does not support input limit changes.")
                else:
                    print(f"\nCurrent input limit: {comp.inputlimit}")
                    print("Current inputs:")
                    for i, source in enumerate(comp.sources):
                        print(f"  [{i}] -> {source}")
                    new_limit = input("Enter new input limit: ")
                    if new_limit:
                        try:
                            new_size = int(new_limit)
                            if new_size < 1:
                                print("Input limit must be at least 1.")
                            elif setlimits(comp,new_size):
                                print(f"Input limit changed to {new_size}")
                            else:
                                print("Could not change input limit. Make sure disconnected inputs are removed first.")
                        except ValueError:
                            print("Invalid number.")
            except (ValueError, IndexError):
                print("Invalid selection.")
            input("Press Enter...")

        elif choice == 'B':
            break

def submenu_simulation():
    while True:
        clear_screen()
        print("--- Simulation & Analysis ---")
        print("1. Set Variable Value")
        print("2. Show Output")
        print("3. Show Truth Table")
        print("4. Diagnose")
        print("5. Start Simulation")
        print("6. Reset Simulation")
        print("B. Back to Main Menu")
        
        choice = input("\nSelect Option: ").strip().upper()

        if choice == '1':
            circuit.listVar()
            var_idx = input("Enter variable serial: ")
            if var_idx == '': continue
            try:
                var = circuit.varlist[int(var_idx)]
                val = input("Enter value (0/1): ")
                if val in ['0', '1']:
                    input_toggle(var, int(val))
                    print(f"Set {var} to {val}")
                else:
                    print("Invalid value.")
            except (ValueError, IndexError):
                print("Invalid serial.")
            input("Press Enter...")

        elif choice == '2':
            circuit.listComponent()
            idx = input("Enter component serial: ")
            if idx == '': continue
            try:
                gate = circuit.canvas[int(idx)]
                circuit.output(gate)
            except (ValueError, IndexError):
                print("Invalid serial.")
            input("Press Enter...")

        elif choice == '3':
            print(circuit.truthTable())
            input("Press Enter...")

        elif choice == '4':
            circuit.diagnose()
            input("Press Enter...")

        elif choice == '5':
            circuit.simulate(Const.SIMULATE)
            print("Simulation Started.")
            input("Press Enter...")

        elif choice == '6':
            circuit.reset()
            print("Reset complete.")
            input("Press Enter...")

        elif choice == 'B':
            break

def submenu_project():
    while True:
        clear_screen()
        print("--- Project Management ---")
        print("1. Save Circuit")
        print("2. Load Circuit")
        print("3. Save as IC")
        print("4. Load IC")
        print("B. Back to Main Menu")

        choice = input("\nSelect Option: ").strip().upper()

        if choice == '1':
            name = input("Enter filename (e.g. Latch.json): ")
            if name:
                circuit.writetojson(name)
                print("Saved.")
            input("Press Enter...")

        elif choice == '2':
            name = input("Enter filename to load: ")
            if name:
                try:
                    circuit.readfromjson(name)
                    base.undolist.clear()
                    base.redolist.clear()
                    print("Loaded.")
                except FileNotFoundError:
                    print("File not found.")
            input("Press Enter...")

        elif choice == '3':
            ic_name = input("Enter Name for the IC (e.g. MyLatch): ")
            if not ic_name:
                print("IC Name is required.")
                input("Press Enter...")
                continue
            name = input("Enter filename for IC (e.g. my_ic.json): ")
            if name:
                circuit.save_as_ic(name, ic_name)
                base.undolist.clear()
                base.redolist.clear()
                print("IC Saved.")
            input("Press Enter...")

        elif choice == '4':
            name = input("Enter IC filename to load: ")
            if name:
                try:
                    addic(name)
                    print("IC Loaded.")
                except FileNotFoundError:
                    print("File not found.")
            input("Press Enter...")

        elif choice == 'B':
            break

if __name__ == "__main__":
    menu()
