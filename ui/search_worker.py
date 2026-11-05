from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from services.search_service import buscar_notas_sincrono

class SearchWorker(QObject):
    """
    Worker que corre en un hilo secundario de QThread para ejecutar búsquedas
    sin congelar la interfaz de usuario, emitiendo un query_id para descartar resultados obsoletos.
    Soporta cancelación reactiva mediante banderas de interrupción (is_interrupted / _abort).
    """
    resultados_listos = pyqtSignal(list, str, int)  # (coincidencias, query, query_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._abort = False
        self._current_query_id = 0

    def abortar(self):
        """Activa la bandera de interrupción para cancelar la búsqueda en curso."""
        self._abort = True

    def cancelar(self):
        """Alias para abortar."""
        self.abortar()

    @property
    def is_interrupted(self):
        class _InterruptFlag:
            def __init__(self, worker):
                self._worker = worker
            def __bool__(self):
                return bool(self._worker._abort)
            def __call__(self):
                return bool(self._worker._abort)
        return _InterruptFlag(self)

    @is_interrupted.setter
    def is_interrupted(self, val: bool):
        self._abort = bool(val)

    def buscar(self, notas: List[Path], query: str, etiqueta_filtro: Optional[str], query_id: int):
        if bool(self.is_interrupted):
            return

        self._current_query_id = query_id

        def _check_interrupted() -> bool:
            return bool(self.is_interrupted) or (self._current_query_id != query_id)

        coincidencias = buscar_notas_sincrono(
            notas=notas,
            query=query,
            etiqueta_filtro=etiqueta_filtro,
            is_interrupted=_check_interrupted
        )

        if bool(self.is_interrupted) or self._current_query_id != query_id:
            return

        self.resultados_listos.emit(coincidencias, query, query_id)

