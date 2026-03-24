from typing import Callable
from core.QtCore import *



_action_list: dict[str, QAction] = {}
_menu_list: dict[str, QMenu] = {}



def get(key: str) -> QAction:
    act = _action_list.get(key, None)
    if act is None:
        raise RuntimeError(f"Requesting for QAction `{key}` before registering")
    return act
def getMenu(key: str) -> QMenu:
    menu = _menu_list.get(key, None)
    if menu is None:
        raise RuntimeError(f"Requesting for QMenu `{key}` before registering")
    return menu



def add(parent: QWidget, key: str, text: str, slot: Callable|None = None, shortcut = None) -> QAction:
    act = QAction(text, parent)

    if slot:     act.triggered.connect(slot)
    if shortcut: act.setShortcut(shortcut)
    # act.setStatusTip("Some kind of tooltip I think")

    parent.addAction(act)
    _action_list[key] = act
    return act

def addCheckable(parent: QWidget, key: str, text: str, isChecked: bool = False, slot: Callable|None = None, shortcut = None) -> QAction:
    act = QAction(text, parent)

    act.setCheckable(True)
    act.setChecked(isChecked)
    if slot:     act.toggled.connect(slot)
    if shortcut: act.setShortcut(shortcut)

    parent.addAction(act)
    _action_list[key] = act
    return act

def addSettingsCheckable(parent: QWidget, key: str, text: str, defaultValue: bool, slot: Callable[[bool], None], shortcut = None) -> QAction:
    """Creates Checkable QAction also able to read and write from QSettings"""
    act = QAction(text, parent)
    state = bool(QSettings().value(f"settings/{key}", defaultValue, type=bool))

    act.setCheckable(True)
    act.setChecked(state)

    def on_toggle(checked: bool):
        QSettings().setValue(f"settings/{key}", checked)
        slot(checked)
    
    act.toggled.connect(on_toggle)
    if shortcut: act.setShortcut(shortcut)

    parent.addAction(act)
    _action_list[key] = act
    return act

def createSubMenu(parent: QWidget, key: str, text: str, default_key: str, slot: Callable[[str], None], options: dict[str, str]) -> QMenu:
    """`options` is dict: {`key`, `label`}:\\
    Where `key` is the _action_list key and also the function input,\\
    And `label` is what the user will see in the drop-down list"""
    menu = QMenu(text, parent)
    group = QActionGroup(parent)
    group.setExclusive(True)
    
    style = QSettings().value(f"settings/{key}", default_key, type=str)
    
    for opt_key, label in options.items():
        act = QAction(label, parent)
        act.setData(opt_key)
        act.setCheckable(True)
        if opt_key == style: act.setChecked(True)
            
        def make_trigger(checked, k=opt_key):
            QSettings().setValue(f"settings/{key}", k)
            slot(k)
            
        act.triggered.connect(make_trigger)
        
        group.addAction(act)
        menu.addAction(act)
        _action_list[f"{key}_{opt_key}"] = act
    
    _menu_list[key] = menu

    return menu