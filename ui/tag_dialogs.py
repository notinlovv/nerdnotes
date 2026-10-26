from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QCompleter, QDialogButtonBox
)
from PyQt6.QtCore import Qt

class MultiCompleterLineEdit(QLineEdit):
    """QLineEdit con soporte para autocompletar etiquetas separadas por comas usando QCompleter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._completer = None

    def set_multi_completer(self, completer: QCompleter):
        self._completer = completer
        self._completer.setWidget(self)
        self._completer.activated[str].connect(self._insert_completion)

    def _insert_completion(self, completion: str):
        text = self.text()
        partes = [p.strip() for p in text.split(",")]
        if partes:
            partes[-1] = completion
            self.setText(", ".join(partes) + ", ")
            self.setCursorPosition(len(self.text()))

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if self._completer:
            text = self.text()
            current_prefix = text.split(",")[-1].strip()
            self._completer.setCompletionPrefix(current_prefix)
            if current_prefix:
                self._completer.complete()

class EditarEtiquetasDialog(QDialog):
    """Diálogo para editar las etiquetas de una nota con QCompleter."""
    def __init__(self, parent=None, etiquetas_actuales: Optional[List[str]] = None, todas_etiquetas: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Editar etiquetas")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel("Etiquetas (separadas por coma):")
        layout.addWidget(lbl)

        self.txt_etiquetas = MultiCompleterLineEdit(self)
        self.txt_etiquetas.setPlaceholderText("ej. trabajo, urgente, proyecto")
        if etiquetas_actuales:
            self.txt_etiquetas.setText(", ".join(etiquetas_actuales))

        if todas_etiquetas:
            completer = QCompleter(todas_etiquetas, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.txt_etiquetas.set_multi_completer(completer)

        layout.addWidget(self.txt_etiquetas)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def obtener_etiquetas(self) -> List[str]:
        raw = self.txt_etiquetas.text()
        return [p.strip() for p in raw.split(",") if p.strip()]

class NuevaNotaDialog(QDialog):
    """Diálogo para crear una nueva nota con título y campo opcional de etiquetas."""
    def __init__(self, parent=None, todas_etiquetas: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Nueva Nota")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl_tit = QLabel("Título de la nota:")
        layout.addWidget(lbl_tit)
        self.txt_titulo = QLineEdit()
        self.txt_titulo.setPlaceholderText("Título...")
        layout.addWidget(self.txt_titulo)

        lbl_tags = QLabel("Etiquetas (opcional, separadas por coma):")
        layout.addWidget(lbl_tags)
        self.txt_etiquetas = MultiCompleterLineEdit(self)
        self.txt_etiquetas.setPlaceholderText("ej. trabajo, personal")
        if todas_etiquetas:
            completer = QCompleter(todas_etiquetas, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.txt_etiquetas.set_multi_completer(completer)
        layout.addWidget(self.txt_etiquetas)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Crear")
        btn_box.accepted.connect(self._al_aceptar)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _al_aceptar(self):
        if not self.txt_titulo.text().strip():
            self.txt_titulo.setFocus()
            return
        self.accept()

    def obtener_datos(self) -> Tuple[str, List[str]]:
        titulo = self.txt_titulo.text().strip()
        tags_raw = self.txt_etiquetas.text()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        return titulo, tags

