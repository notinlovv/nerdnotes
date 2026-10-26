from pathlib import Path
from typing import List, Optional, Set
from PyQt6.QtCore import QAbstractListModel, QSortFilterProxyModel, QModelIndex, Qt
from services.note_index import extraer_vista_previa

class NoteRoles:
    PathRole = Qt.ItemDataRole.UserRole
    TitleRole = Qt.ItemDataRole.UserRole + 1
    DateRole = Qt.ItemDataRole.UserRole + 2
    PreviewRole = Qt.ItemDataRole.UserRole + 3
    TagsRole = Qt.ItemDataRole.UserRole + 4
    PinnedRole = Qt.ItemDataRole.UserRole + 5
    ContentLowerRole = Qt.ItemDataRole.UserRole + 6

class NoteItem:
    def __init__(
        self, ruta: Path, titulo: str, fecha: str, vista_previa: str = "",
        etiquetas: Optional[List[str]] = None, fijada: bool = False,
        contenido_lower: str = ""
    ):
        self.ruta = ruta
        self.titulo = titulo
        self.fecha = fecha
        self.vista_previa = vista_previa
        self.etiquetas = etiquetas or []
        self.fijada = fijada
        self.contenido_lower = contenido_lower

class NotesListModel(QAbstractListModel):
    """Modelo propio para la lista de notas."""
    def __init__(self, items: Optional[List[NoteItem]] = None, parent=None):
        super().__init__(parent)
        self.items: List[NoteItem] = list(items or [])

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None

        item = self.items[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"[{item.fecha}] {item.titulo}"
        elif role == NoteRoles.PathRole:
            return item.ruta
        elif role == NoteRoles.TitleRole:
            return item.titulo
        elif role == NoteRoles.DateRole:
            return item.fecha
        elif role == NoteRoles.PreviewRole:
            return item.vista_previa
        elif role == NoteRoles.TagsRole:
            return item.etiquetas
        elif role == NoteRoles.PinnedRole:
            return item.fijada
        elif role == NoteRoles.ContentLowerRole:
            return item.contenido_lower

        return None

    def set_items(self, items: List[NoteItem]):
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()

    def get_item(self, row: int) -> Optional[NoteItem]:
        if 0 <= row < len(self.items):
            return self.items[row]
        return None

    def find_row_by_path(self, ruta: Path) -> int:
        for i, item in enumerate(self.items):
            if item.ruta == ruta:
                return i
        return -1


class NotesFilterProxyModel(QSortFilterProxyModel):
    """
    QSortFilterProxyModel para filtrar notas en tiempo real por categoría (Todas, Fijadas, Tag)
    y por consulta de búsqueda de forma instantánea.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro_categoria: str = "todas"
        self._filtro_busqueda: str = ""
        self._coincidencias_busqueda: Optional[Set[Path]] = None
        self.setDynamicSortFilter(True)

    def set_filtro_categoria(self, categoria: str):
        self._filtro_categoria = categoria
        self.invalidateFilter()

    def set_filtro_busqueda(self, query: str, coincidencias: Optional[Set[Path]] = None):
        self._filtro_busqueda = query.strip().lower()
        self._coincidencias_busqueda = coincidencias
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model:
            return True
        idx = model.index(source_row, 0, source_parent)
        if not idx.isValid():
            return False

        # 1. Filtro por categoría (barra lateral)
        if self._filtro_categoria == "fijadas":
            if not idx.data(NoteRoles.PinnedRole):
                return False
        elif self._filtro_categoria.startswith("tag:"):
            tag_buscado = self._filtro_categoria[4:].lower()
            tags = [t.lower() for t in (idx.data(NoteRoles.TagsRole) or [])]
            if tag_buscado not in tags:
                return False

        # 2. Filtro por búsqueda
        if self._coincidencias_busqueda is not None:
            ruta = idx.data(NoteRoles.PathRole)
            return ruta in self._coincidencias_busqueda

        if self._filtro_busqueda:
            q = self._filtro_busqueda
            titulo = (idx.data(NoteRoles.TitleRole) or "").lower()
            if q in titulo:
                return True
            tags = [t.lower() for t in (idx.data(NoteRoles.TagsRole) or [])]
            if any(q in t for t in tags):
                return True
            cont_lower = idx.data(NoteRoles.ContentLowerRole) or ""
            if q in cont_lower:
                return True
            return False

        return True

    def find_proxy_index_by_path(self, ruta: Path) -> QModelIndex:
        src_model = self.sourceModel()
        if not src_model:
            return QModelIndex()
        row = src_model.find_row_by_path(ruta)
        if row >= 0:
            src_idx = src_model.index(row, 0)
            return self.mapFromSource(src_idx)
        return QModelIndex()
