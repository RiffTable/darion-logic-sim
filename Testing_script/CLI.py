import os
import sys
import argparse

parser = argparse.ArgumentParser(description='Run CLI')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, unknown = parser.parse_known_args()

# Support Pyinstaller, Nuitka, and direct Python script relative paths
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
elif getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
else:
    root_dir = os.path.dirname(script_dir)

# Add control to path
sys.path.insert(0, os.path.join(root_dir, 'control'))

# Backend Selection Logic
if args.engine:
    sys.path.insert(0, os.path.join(root_dir, 'engine'))
else:
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))

try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from Event_Manager import Event
    from Control import Add, AddIC, Delete, Connect, Disconnect, Paste, Toggle, SetLimits, Rename, TransferInfo, Reorder
    from Circuit import Circuit
    from Gates import Variable, Probe
    import Const
    from IC import IC
except ImportError as e:
    print(f"FATAL ERROR: Could not import backend modules: {e}")
    sys.exit(1)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


Const.set_DEBUG()
circuit = Circuit()
base = Event()
STATUS_MESSAGE = ""

def set_status(msg):
    global STATUS_MESSAGE
    STATUS_MESSAGE = msg

# --- Helper Commands ---
def execute_cmd(cmd_obj):
    if cmd_obj.execute():
        base.register(cmd_obj)
        return True
    return False

def pause():
    input("\nPress Enter to continue...")

# --- Command Handlers --- (Components)
def add_components():
    print("\n[0:AND] [1:NAND] [2:OR] [3:NOR] [4:XOR] [5:XNOR] [6:Var] [7:NOT] [8:Probe] [9:In] [10:Out]")
    c = input("Add (space separated names/IDs): ").split()
    if not c: return
    gate_map = {"AND": 0, "NAND": 1, "OR": 2, "NOR": 3, "XOR": 4, "XNOR": 5, "VAR": 6, "VARIABLE": 6, "NOT": 7, "PROBE": 8, "IN": 9, "OUT": 10}
    added_count = 0
    for i in c:
        val = gate_map.get(i.upper(), None)
        if val is None:
            try: val = int(i)
            except ValueError: continue
        if execute_cmd(Add(circuit, val)):
            added_count += 1
    
    if added_count: set_status(f"Added {added_count} components.")

def list_components():
    circuit.listComponent()
    pause()

def connect_components():
    circuit.listComponent()
    gate_idx = input("\nEnter Target Serial: ")
    if not gate_idx: return
    try: target_component = circuit.get_components()[int(gate_idx)]
    except (ValueError, IndexError): return set_status("Invalid Target.")

    sourcelist_indices = input("Enter Source Serials: ").split()
    if not sourcelist_indices: return
    
    connected = 0
    for source_idx in sourcelist_indices:
        try: source_component = circuit.get_components()[int(source_idx)]
        except (ValueError, IndexError): continue

        actual_source = source_component
        if isinstance(source_component, IC):
            print(f"\nOutputs of '{source_component}':")
            for k, p in enumerate(source_component.outputs): print(f"  [{k}] {p}")
            try: actual_source = source_component.outputs[int(input("Select Pin: "))]
            except (ValueError, IndexError): continue

        actual_target = target_component
        target_index = 0
        if isinstance(target_component, IC):
            print(f"\nInputs of '{target_component}':")
            for k, p in enumerate(target_component.inputs): print(f"  [{k}] {p} (from {p.sources[0] if p.sources and p.sources[0] is not None else 'Empty'})")
            try: actual_target = target_component.inputs[int(input(f"[{actual_source}] -> Select Pin: "))]
            except (ValueError, IndexError): continue
        else:
            print(f"\nInputs of '{target_component}':")
            for k, c in enumerate(target_component.sources): print(f"  [{k}] <- {c if c else 'Empty'}")
            try: target_index = int(input(f"[{actual_source}] -> Select index: "))
            except ValueError: continue

        if execute_cmd(Connect(circuit, actual_target, actual_source, target_index)):
            connected += 1

    set_status(f"Connected {connected} source(s) to '{actual_target}'.")

def disconnect_components():
    circuit.listComponent()
    gate_idx = input("\nEnter Target Serial to Disconnect: ")
    if not gate_idx: return
    try: target = circuit.get_components()[int(gate_idx)]
    except (ValueError, IndexError): return set_status("Invalid serial.")

    if isinstance(target, IC):
        pins = [(i, p, p.sources[0]) for i, p in enumerate(target.inputs) if p.sources and p.sources[0] is not None]
        if not pins: return set_status("No connections.")
        print(f"\nConnected Pins of '{target}':")
        for i, p, s in pins: print(f"  [{i}] {p} <- {s}")
        indices = input("Enter Pin indices to disconnect: ").split()
        for i_str in indices:
            try:
                index = int(i_str)
                if 0 <= index < len(target.inputs) and target.inputs[index].sources[0] is not None:
                    execute_cmd(Disconnect(circuit, target.inputs[index], 0))
            except ValueError: pass
        set_status("Disconnected specified pins.")
    elif not isinstance(target, Variable):
        conns = [(i, s) for i, s in enumerate(target.sources) if s is not None]
        if not conns: return set_status("No connections.")
        print(f"\nConnections of '{target}':")
        for i, s in conns: print(f"  [{i}] <- {s}")
        indices = input("Enter indices to disconnect: ").split()
        for i_str in indices:
            try:
                index = int(i_str)
                if 0 <= index < len(target.sources) and target.sources[index] is not None:
                    execute_cmd(Disconnect(circuit, target, index))
            except ValueError: pass
        set_status("Disconnected specified inputs.")

def delete_components():
    circuit.listComponent()
    gatelist = input("\nEnter serials to delete: ").split()
    to_delete = [circuit.get_components()[int(i)] for i in gatelist if i.isdigit() and int(i) < len(circuit.get_components())]
    if to_delete and execute_cmd(Delete(circuit, to_delete)):
        set_status(f"Deleted {len(to_delete)} component(s).")
    else: set_status("No components deleted.")

def copy_selection():
    circuit.listComponent()
    try:
        complist = [circuit.get_components()[int(i)] for i in input("\nEnter serials to copy: ").split()]
        circuit.copy(complist)
        set_status(f"Copied {len(complist)} component(s).")
    except (ValueError, IndexError): set_status("Copy failed due to invalid selection.")

def paste_selection():
    if execute_cmd(Paste(circuit)): set_status("Pasted successfully.")
    else: set_status("Nothing to paste.")

def rename_component():
    circuit.listComponent()
    try:
        indices = [int(i) for i in input("\nEnter serial(s) to rename: ").split()]
        renamed = 0
        for idx in indices:
            comp = circuit.get_components()[idx]
            if isinstance(comp, IC): continue
            new_name = input(f"New name for {comp.codename} (blank to skip): ").strip()
            if new_name and execute_cmd(Rename(comp, new_name)): renamed += 1
        set_status(f"Renamed {renamed} component(s).")
    except (ValueError, IndexError): set_status("Rename failed due to invalid selection.")

def change_input_limit():
    circuit.listComponent()
    try:
        comp = circuit.get_components()[int(input("\nEnter serial of component: "))]
        if isinstance(comp, (IC, Variable, Probe)) or not hasattr(comp, 'setlimits') or not hasattr(comp, 'inputlimit'):
            return set_status("Cannot change input limit for this component.")
        new_limit = input(f"Current limit {comp.inputlimit}. Enter new limit: ")
        if new_limit and int(new_limit) >= 1 and execute_cmd(SetLimits(comp, int(new_limit))):
            set_status(f"Input limit changed to {new_limit}.")
        else: set_status("Failed to change limit.")
    except (ValueError, IndexError): set_status("Invalid selection.")

def transfer_info():
    circuit.listComponent()
    try:
        comp = circuit.get_components()[int(input("\nEnter serial of component to change type: "))]
        if isinstance(comp, IC): return set_status("Cannot change type of ICs.")
        print("[0:AND] [1:NAND] [2:OR] [3:NOR] [4:XOR] [5:XNOR] [6:Var] [7:NOT] [8:Probe] [9:In] [10:Out]")
        new_id_str = input("Select new gate type (0-10): ")
        if new_id_str and 0 <= int(new_id_str) <= 10 and execute_cmd(TransferInfo(circuit, comp, int(new_id_str))):
            set_status(f"Transferred type to {new_id_str}.")
        else: set_status("Type transfer failed.")
    except (ValueError, IndexError): set_status("Invalid selection.")

def reorder_component():
    circuit.listComponent()
    try:
        comp = circuit.get_components()[int(input("\nEnter serial to reorder: "))]
        new_idx = input(f"Current rank index {comp.code[1]}. Enter new position: ")
        if new_idx and execute_cmd(Reorder(circuit, comp, int(new_idx))):
            set_status("Reordered successfully.")
        else: set_status("Reorder failed.")
    except (ValueError, IndexError): set_status("Invalid selection.")

def clear_circuit():
    confirm = input("Are you sure you want to clear the circuit? (y/n): ").strip().lower()
    if confirm == 'y':
        comps = circuit.get_components()
        if comps and execute_cmd(Delete(circuit, comps)): set_status("Circuit cleared. (Undo available)")
        else: set_status("Circuit is already empty.")

def rank_reset():
    circuit.rank_reset()
    set_status("Rank reset executed (internal lists trimmed).")

def ic_pin_change():
    circuit.ic_pin_change()
    set_status("Changed all variables/probes to IC I/O pins.")

# --- Simulation & Analysis Handlers ---
def set_variable():
    variables = circuit.get_variables()
    if not variables: return set_status("No variables exist.")
    for i, v in enumerate(variables): print(f"{i}. {v} (Val: {v.value})")
    try:
        var = variables[int(input("Enter variable index: "))]
        val = int(input("Enter value (0/1): "))
        if val in [0, 1]:
            execute_cmd(Toggle(circuit, var, val))
            set_status(f"Set {var} to {val}")
        else: set_status("Invalid value.")
    except (ValueError, IndexError): set_status("Invalid selection.")

def show_output():
    circuit.listComponent()
    try:
        gate = circuit.get_components()[int(input("\nEnter component serial: "))]
        circuit.output(gate)
        pause()
    except (ValueError, IndexError): set_status("Invalid selection.")

def show_truth_table():
    if Const.get_MODE() != Const.SIMULATE:
        return set_status("Switch to Simulation Mode (Option 5) before generating a Truth Table!")
    
    circuit.listVar()
    var_str = input("Enter Variable Serials from above (space-separated, in desired order, blank for all): ").strip()
    
    variables = []
    if var_str:
        for idx_str in var_str.split():
            try:
                comp = circuit.get_variables()[int(idx_str)]
                variables.append(comp)
            except (ValueError, IndexError):
                pass
    else:
        variables = None

    print("\n--- Available Components for Output ---")
    components = circuit.get_components()
    for i, comp in enumerate(components):
        if comp.id != Const.VARIABLE_ID:
            print(f"{i}. {comp}")
            
    out_str = input("Enter Gate/IC Serials for outputs (space-separated, blank for all): ").strip()
    
    outputs = []
    if out_str:
        for idx_str in out_str.split():
            try:
                comp = components[int(idx_str)]
                if comp.id == Const.VARIABLE_ID:
                    continue
                elif comp.id == Const.IC_ID:
                    print(f"\nOutputs of IC '{comp.codename}':")
                    for k, p in enumerate(comp.outputs):
                        print(f"  [{k}] {p}")
                    pin_str = input(f"Select Output Pins from IC '{comp.codename}' (space-separated, blank for all): ").strip()
                    if pin_str:
                        for pin_idx in pin_str.split():
                            try:
                                outputs.append(comp.outputs[int(pin_idx)])
                            except (ValueError, IndexError):
                                pass
                    else:
                        outputs.extend(comp.outputs)
                else:
                    outputs.append(comp)
            except (ValueError, IndexError):
                pass
    else:
        outputs = None
        
    table = circuit.truthTable(variables, outputs)
    if not table: return set_status("Cannot generate Truth Table. Need 1-16 Variables.")
    print(table)
    fname = input("Save to file (Enter filename or press Enter for 'truth_table.txt'): ").strip() or 'truth_table.txt'
    try:
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(table)
            set_status(f"Saved to '{fname}'.")
    except OSError as e: set_status(f"Error saving: {e}")
    pause()

def diagnose():
    circuit.diagnose()
    pause()

def start_simulation():
    circuit.simulate(Const.SIMULATE)
    set_status("Simulation Started.")

def reset_simulation():
    circuit.reset()
    set_status("Reset complete.")

# --- Project Management Handlers ---
def save_circuit():
    name = input("Enter filename (e.g. Latch.json): ").strip()
    if name:
        circuit.writetojson(name)
        set_status("Saved.")

def load_circuit():
    name = input("Enter filename to load: ").strip()
    if name:
        try:
            circuit.readfromjson(name)
            base.undolist.clear()
            base.redolist.clear()
            set_status("Loaded.")
        except FileNotFoundError: set_status("File not found.")

def save_as_ic():
    ic_name = input("Enter Name for the IC (e.g. MyLatch): ").strip()
    if not ic_name: return set_status("IC Name is required.")
    name = input("Enter filename for IC (e.g. my_ic.json): ").strip()
    if name:
        circuit.save_as_ic(name, ic_name, "", "", None)
        base.undolist.clear()
        base.redolist.clear()
        set_status("IC Saved.")

def load_ic():
    name = input("Enter IC filename to load: ").strip()
    if name:
        try:
            if execute_cmd(AddIC(circuit, name)): set_status("IC Loaded.")
        except FileNotFoundError: set_status("File not found.")

def undo_action():
    base.undo()
    set_status("Undone last action.")

def redo_action():
    base.redo()
    set_status("Redone last action.")

# --- Menus ---
def generic_menu(title, options):
    global STATUS_MESSAGE
    while True:
        clear_screen()
        print(f"--- {title} ---")
        if STATUS_MESSAGE:
            print(f"[*] {STATUS_MESSAGE}")
            STATUS_MESSAGE = ""
            print("-" * (8 + len(title)))
            
        for key, (desc, _) in options.items():
            print(f"{key}. {desc}")
        
        choice = input("\nSelect Option: ").strip().upper()
        if choice in options:
            func = options[choice][1]
            if func is None: break
            try:
                func()
            except Exception as e:
                set_status(f"Operation Failed ({type(e).__name__}): {e}")
        else: set_status("Invalid choice.")

def submenu_components():
    generic_menu("Components & Connections", {
        '1': ("Add Component", add_components),
        '2': ("List Components", list_components),
        '3': ("Connect Components", connect_components),
        '4': ("Disconnect Components", disconnect_components),
        '5': ("Delete Components", delete_components),
        '6': ("Rename Component", rename_component),
        '7': ("Change Input Limit", change_input_limit),
        '8': ("Clear Circuit", clear_circuit),
        'M': ("More Options (Copy/Paste, Transfer, Reorder, Pins)", submenu_components_more),
        'B': ("Back", None)
    })

def submenu_components_more():
    generic_menu("More Component Options", {
        '1': ("Copy Selection", copy_selection),
        '2': ("Paste Selection", paste_selection),
        '3': ("Transfer Info (Change Gate Type)", transfer_info),
        '4': ("Reorder Component", reorder_component),
        '5': ("Rank Reset", rank_reset),
        '6': ("IC Pin Change", ic_pin_change),
        'B': ("Back", None)
    })

def submenu_simulation():
    generic_menu("Simulation & Analysis", {
        '1': ("Set Variable Value", set_variable),
        '2': ("Show Output", show_output),
        '3': ("Show Truth Table", show_truth_table),
        '4': ("Diagnose", diagnose),
        '5': ("Start Simulation", start_simulation),
        '6': ("Reset Simulation", reset_simulation),
        'B': ("Back", None)
    })

def submenu_project():
    generic_menu("Project Management", {
        '1': ("Save Circuit", save_circuit),
        '2': ("Load Circuit", load_circuit),
        '3': ("Save as IC", save_as_ic),
        '4': ("Load IC", load_ic),
        'B': ("Back", None)
    })

def menu():
    generic_menu("Circuit Simulator Main Menu", {
        '1': ("Components & Connections", submenu_components),
        '2': ("Simulation & Analysis", submenu_simulation),
        '3': ("Project Management", submenu_project),
        '4': ("Undo", undo_action),
        '5': ("Redo", redo_action),
        'E': ("Exit", exit_app)
    })

def exit_app():
    Const.MODE = Const.DESIGN
    print("Exiting Circuit Simulator......")
    sys.exit(0)

if __name__ == "__main__":
    menu()
