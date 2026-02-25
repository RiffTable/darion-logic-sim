from __future__ import annotations
from core.QtCore import *
from editor.styles import Color, Font

from editor.circuit.compitem import CompItem


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._comp: CompItem|None = None
        self.buildUI()
        self.hide()

    def buildUI(self):
        self.setFixedWidth(175)
        self.setStyleSheet(f"""
            PropertiesPanel {{
                background: {Color.secondary_bg.name()};
                border-radius: 8px;
            }}
            QLabel#title {{
                font-size: 13px;
                font-weight: bold;
                color: {Color.text.name()};
                padding-bottom: 4px;
            }}
            QLabel {{
                color: {Color.text.name()};
                font-size: 11px;
            }}
            QSpinBox {{
                background: {Color.primary_bg.name()};
                color: {Color.text.name()};
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Title
        self.title = QLabel("Properties")
        self.title.setObjectName("title")
        outer.addWidget(self.title)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        outer.addWidget(line)

        # Form
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.label_inputs = QLabel("No of Inputs:")
        self.spin_inputs  = QSpinBox()
        self.spin_inputs.setMinimum(1)
        self.spin_inputs.setMaximum(69)
        self.spin_inputs.valueChanged.connect(self._on_input_count_changed)
        form.addRow(self.label_inputs, self.spin_inputs)

        self.val_facing = QLabel("-")
        self.val_tag    = QLabel("-")
        form.addRow("Facing:", self.val_facing)
        form.addRow("Tag:",    self.val_tag)

        outer.addLayout(form)
        outer.addStretch()
    

    def selectionChanged(self, selectedItems: list[QGraphicsItem]):
        # print(selectedItems)
        if len(selectedItems) > 1: return
        elif len(selectedItems) == 0:
            self.clear()
        elif isinstance(selectedItems[0], CompItem):
            self.updateTab(selectedItems[0])


    def updateTab(self, comp: CompItem):
        self._comp = comp
        proplist = comp.getProperties()

        # Display name
        tag = proplist["tag"]
        self.title.setText(f"Properties: {tag}")

        # Variable inputs for gates
        inputs = proplist.get("input_count")
        if inputs:
            self.spin_inputs.blockSignals(True)
            # Why did I remove the limits? :thinking:
            # self.spin_inputs.setMinimum(comp.minInput)
            # self.spin_inputs.setMaximum(comp.maxInput)
            self.spin_inputs.setValue(inputs)
            self.spin_inputs.blockSignals(False)

        self.val_facing.setText(comp.facing.name.capitalize())
        self.val_tag.setText(tag)

        self.show()

    def refresh(self):
        """Call after external changes (rotate, flip, etc.)"""
        if self._comp:
            self.updateTab(self._comp)

    def clear(self):
        self._comp = None
        self.hide()


    def _on_input_count_changed(self, value: int):
        from editor.circuit.gates import GateItem
        if self._comp and isinstance(self._comp, GateItem):
            self._comp.setInputCount(value)