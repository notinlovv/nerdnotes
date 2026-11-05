import subprocess
from pathlib import Path
from typing import Optional, Callable

import config

# Soporte opcional para PyQt6 para no romper ejecución de CLI en entornos sin interfaz
try:
    from PyQt6.QtWidgets import QTextEdit
    from PyQt6.QtCore import QTimer, pyqtSignal, QObject
    _PYQT6_DISPONIBLE = True
except (ImportError, TypeError, AttributeError):
    _PYQT6_DISPONIBLE = False
    QTextEdit = object
    QObject = object
    def pyqtSignal(*args, **kwargs):
        class _DummySignal:
            def connect(self, *a, **k): pass
            def emit(self, *a, **k): pass
        return _DummySignal()
    class QTimer:
        def __init__(self, *args, **kwargs): pass
        def setSingleShot(self, *args): pass
        def setInterval(self, *args): pass
        def start(self, *args): pass
        def stop(self): pass
        def isActive(self): return False
        timeout = pyqtSignal()

def abrir_editor(ruta: Path) -> bool:
    """
    Abre la ruta especificada con el editor configurado,
    con fallback real: DEFAULT_EDITOR/EDITOR -> nano -> vi.
    """
    candidatos = []
    if config.DEFAULT_EDITOR:
        candidatos.append(config.DEFAULT_EDITOR)
    for alt in ['nano', 'vi']:
        if alt not in candidatos:
            candidatos.append(alt)

    for i, editor in enumerate(candidatos):
        if i > 0:
            print(f"Usando {editor} como alternativa")
        try:
            subprocess.call([editor, str(ruta)])
            return True
        except FileNotFoundError:
            print(f"No se encontró el editor '{editor}'")
            continue
        except Exception as e:
            print(f"Error al abrir editor '{editor}': {e}")
            continue

    print("Error: No se encontró ningún editor disponible (probados: EDITOR, nano, vi).")
    return False

def editar_nota(ruta: Path) -> None:
    if not ruta.exists():
        print("NO SE ENCONTRÓ NINGUNA NOTA")
        return 
    abrir_editor(ruta)


class NoteEditor(QTextEdit):
    """
    Componente de edición de notas con soporte para autoguardado inteligente,
    debouncing configurable (500 ms por defecto), indicador de estado sucio
    y método explícito flush().
    """
    INTERVALO_AUTOGUARDADO: int = 500

    ha_cambiado = pyqtSignal(bool)
    guardar_solicitado = pyqtSignal(str)
    autoguardado_realizado = pyqtSignal()

    def __init__(self, parent=None, callback_guardar: Optional[Callable[[str], bool]] = None, intervalo_ms: int = 500):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
        self.callback_guardar = callback_guardar
        self._is_dirty: bool = False
        self._ignorando_cambios: bool = False

        self.autosave_timer = QTimer(self if _PYQT6_DISPONIBLE else None)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(intervalo_ms)
        if _PYQT6_DISPONIBLE:
            self.autosave_timer.timeout.connect(self._al_timeout_autosave)
            self.textChanged.connect(self._al_cambiar_texto)

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, valor: bool):
        val_bool = bool(valor)
        if self._is_dirty != val_bool:
            self._is_dirty = val_bool
            self.ha_cambiado.emit(val_bool)

    @property
    def ha_cambiado_estado(self) -> bool:
        """Alias para is_dirty."""
        return self._is_dirty

    @property
    def modificado(self) -> bool:
        return self._is_dirty

    @modificado.setter
    def modificado(self, valor: bool):
        self.is_dirty = valor

    def cargar_texto(self, texto: str):
        """Carga texto sin marcar como sucio ni iniciar el temporizador."""
        self._ignorando_cambios = True
        try:
            if hasattr(self.autosave_timer, "isActive") and self.autosave_timer.isActive():
                self.autosave_timer.stop()
            if _PYQT6_DISPONIBLE:
                self.setPlainText(texto)
            self._is_dirty = False
            self.ha_cambiado.emit(False)
        finally:
            self._ignorando_cambios = False

    def _al_cambiar_texto(self):
        if self._ignorando_cambios:
            return
        if _PYQT6_DISPONIBLE and self.isReadOnly():
            return
        self.is_dirty = True
        self.autosave_timer.start(self.INTERVALO_AUTOGUARDADO)

    def _al_timeout_autosave(self):
        if self._is_dirty:
            if not _PYQT6_DISPONIBLE or not self.isReadOnly():
                exito = self.flush()
                if exito:
                    self.autoguardado_realizado.emit()

    def flush(self) -> bool:
        """Fuerza el guardado inmediato de cambios pendientes deteniendo el temporizador."""
        if hasattr(self.autosave_timer, "isActive") and self.autosave_timer.isActive():
            self.autosave_timer.stop()

        if not self._is_dirty:
            return True

        if _PYQT6_DISPONIBLE and self.isReadOnly():
            return True

        contenido = self.toPlainText() if _PYQT6_DISPONIBLE else ""
        exito = True
        if self.callback_guardar:
            try:
                res = self.callback_guardar(contenido)
                if res is False:
                    exito = False
            except Exception:
                exito = False

        if exito:
            self.is_dirty = False
            self.guardar_solicitado.emit(contenido)
        return exito


class AutoSaveDebouncer(QObject):
    """
    Manejador desacoplado de temporizador de autoguardado (debouncing)
    con control de estado sucio y flush inmediato.
    """
    ha_cambiado = pyqtSignal(bool)
    guardar_solicitado = pyqtSignal()

    def __init__(self, callback_guardar: Optional[Callable[[], bool]] = None, intervalo_ms: int = 500, parent=None):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
        self.callback_guardar = callback_guardar
        self._is_dirty: bool = False
        self.timer = QTimer(self if _PYQT6_DISPONIBLE else None)
        self.timer.setSingleShot(True)
        self.timer.setInterval(intervalo_ms)
        if _PYQT6_DISPONIBLE:
            self.timer.timeout.connect(self._al_timeout)

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, valor: bool):
        val_bool = bool(valor)
        if self._is_dirty != val_bool:
            self._is_dirty = val_bool
            self.ha_cambiado.emit(val_bool)

    def registrar_cambio(self):
        self.is_dirty = True
        self.timer.start()

    def _al_timeout(self):
        if self._is_dirty:
            self.flush()

    def flush(self) -> bool:
        if hasattr(self.timer, "isActive") and self.timer.isActive():
            self.timer.stop()
        if not self._is_dirty:
            return True
        exito = True
        if self.callback_guardar:
            try:
                res = self.callback_guardar()
                if res is False:
                    exito = False
            except Exception:
                exito = False
        if exito:
            self.is_dirty = False
            self.guardar_solicitado.emit()
        return exito


# Aliases
Editor = NoteEditor
AutoSaveEditor = NoteEditor
EditorController = AutoSaveDebouncer
