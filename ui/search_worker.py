from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from services.search_service import buscar_notas_sincrono

class SearchWorker(QObject):
    """
    Worker que corre en un hilo secundario de QThread para ejecutar búsquedas
    sin congelar la interfaz de usuario, emitiendo un query_id para descartar resultados obsoletos.
    """
    resultados_listos = pyqtSignal(list, str, int)  # (coincidencias, query, query_id)

    def __init__(self, parent=None):
        super().__init__(parent)

    def buscar(self, notas: List[Path], query: str, etiqueta_filtro: Optional[str], query_id: int):
        coincidencias = buscar_notas_sincrono(notas, query, etiqueta_filtro)
        self.resultados_listos.emit(coincidencias, query, query_id)

