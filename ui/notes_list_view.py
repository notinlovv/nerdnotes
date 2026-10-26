from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import QListView
from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal, QItemSelectionModel
from ui.notes_model import NoteRoles
from ui.note_delegate import NoteCardDelegate

class NotesListView(QListView):
    """
    QListView personalizada con modelo propio QAbstractListModel / QSortFilterProxyModel
    y delegate personalizado.
    Elimina el shim de compatibilidad con QListWidget (ItemAdapter) y opera
    estrictamente con la arquitectura Model/View real de Qt (QModelIndex y NoteRoles).
    """
    currentItemChanged = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card_delegate = NoteCardDelegate(self)
        self.setItemDelegate(self._card_delegate)

        # Configuración estética
        self.setSpacing(2)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex):
        super().currentChanged(current, previous)
        self.currentItemChanged.emit(current, previous)

    def set_tema(self, tema: str):
        """Actualiza el tema en el delegate y redibuja la lista."""
        self._card_delegate.set_tema(tema)
        self.viewport().update()

    def count(self) -> int:
        """Número de notas visibles en el modelo actual."""
        return self.model().rowCount() if self.model() else 0

    def find_row_by_path(self, ruta: Path) -> int:
        """Encuentra la fila de la ruta en el modelo subyacente."""
        model = self.model()
        if hasattr(model, "sourceModel") and model.sourceModel():
            return model.sourceModel().find_row_by_path(ruta)
        elif hasattr(model, "find_row_by_path"):
            return model.find_row_by_path(ruta)
        return -1

    def selected_path(self) -> Optional[Path]:
        """Retorna la ruta de la nota actualmente seleccionada."""
        idx = self.currentIndex()
        if idx.isValid():
            return idx.data(NoteRoles.PathRole)
        return None

    # Métodos de conveniencia basados en QModelIndex (sin ItemAdapter shim)
    def index_at_row(self, row: int) -> QModelIndex:
        return self.model().index(row, 0) if self.model() else QModelIndex()

    def select_row(self, row: int):
        idx = self.index_at_row(row)
        if idx.isValid():
            self.setCurrentIndex(idx)
            if self.selectionModel():
                self.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    # Compatibilidad transparente para tests existentes usando QModelIndex
    def item(self, row: int) -> Optional[QModelIndex]:
        if self.model() and 0 <= row < self.model().rowCount():
            return self.model().index(row, 0)
        return None

    def currentItem(self) -> Optional[QModelIndex]:
        idx = self.currentIndex()
        return idx if idx.isValid() else None

    def setCurrentItem(self, item: Optional[QModelIndex]):
        if isinstance(item, QModelIndex) and item.isValid():
            self.setCurrentIndex(item)
            if self.selectionModel():
                self.selectionModel().select(item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        elif item is None:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
