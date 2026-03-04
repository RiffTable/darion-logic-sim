from typing import Callable
from core.QtCore import *



# List of all QActions in this project
# Check main.py for all the QActions
_action_list: dict[str, QAction] = {}



def get(key: str) -> QAction:
	act = _action_list.get(key, None)
	if act == None:
		raise KeyError("Requesting for a QAction before registering")
	return act


def add(parent: QWidget, key: str, text: str, slot: Callable|None = None, shortcut = None) -> QAction:
	act = QAction(text, parent)
	if slot:     act.triggered.connect(slot)
	if shortcut: act.setShortcut(shortcut)
	# act.setStatusTip("Some kind of tooltip I think")

	parent.addAction(act)
	_action_list[key] = act
	return act


def addCheckable(parent: QWidget, key: str, text: str, isChecked: bool = False, slot: Callable|None = None, shortcut = None
) -> QAction:
	act = QAction(text, parent)
	act.setCheckable(True)
	act.setChecked(isChecked)
	if slot:     act.triggered.connect(slot)
	if shortcut: act.setShortcut(shortcut)

	parent.addAction(act)
	_action_list[key] = act
	return act