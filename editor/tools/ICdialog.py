from core.QtCore import *

class ICSetupDialog(QDialog):
    def __init__(self, parent: QWidget|None = None) -> None:
        super().__init__(parent)
        
        self.setWindowTitle("Saving Project As IC")
        self.name = QLineEdit(self)
        self.tag = QLineEdit(self)
        self.desc = QTextEdit(self)

        self.name.setPlaceholderText("IC")
        self.tag.setPlaceholderText("IC")

        layout = QFormLayout(self)
        explanation = QLabel("Converting the entire project into an IC will wipe all components in the canvas. Provide metadata for the new IC")
        explanation.setWordWrap(True)

        layout.addRow(explanation) 
        layout.addRow(QLabel(""))
        layout.addRow("Name: ", self.name)
        layout.addRow("tag: ", self.tag)
        layout.addRow("Description: ", self.desc)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
    
    @classmethod
    def showForm(cls, parent: QWidget|None = None):
        dialog = ICSetupDialog(parent)
        res = dialog.exec()
        return {
            "accepted": res == QDialog.DialogCode.Accepted,
            "name": dialog.name.text().strip(),
            "tag":  dialog.tag.text().strip(),
            "desc": dialog.desc.toPlainText().strip(),
        }