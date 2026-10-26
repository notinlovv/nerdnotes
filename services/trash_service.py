import shutil
from pathlib import Path
from typing import List, Optional
import config
from services.config_service import desfijar_nota

def asegurar_papelera():
    """Asegura que el directorio .papelera exista."""
    try:
        config.TRASH_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

def listar_papelera() -> List[Path]:
    """Lista las notas que se encuentran en la papelera."""
    try:
        asegurar_papelera()
        archivos = [f for f in config.TRASH_DIR.glob(f"*{config.EXTENSION}") if f.is_file()]
        return sorted(archivos, reverse=True)
    except Exception as e:
        print(f"Error al listar papelera: {e}")
        return []

def mover_a_papelera(ruta: Path) -> Optional[Path]:
    """
    Mueve un archivo de nota a la papelera.
    Si ya existe un archivo con el mismo nombre en la papelera, añade sufijo _2, _3...
    """
    try:
        asegurar_papelera()
        if not ruta.exists() or not ruta.is_file():
            return None

        # Desfijar la nota si estaba fijada
        desfijar_nota(ruta.name)

        nombre_base = ruta.stem
        destino = config.TRASH_DIR / ruta.name
        contador = 2
        while destino.exists():
            destino = config.TRASH_DIR / f"{nombre_base}_{contador}{config.EXTENSION}"
            contador += 1

        shutil.move(str(ruta), str(destino))
        from services import note_index
        note_index.invalidar(ruta)
        note_index.invalidar(destino)
        return destino
    except Exception as e:
        print(f"Error al mover nota a papelera: {e}")
        return None

def restaurar_nota_papelera(ruta_papelera: Path) -> Optional[Path]:
    """
    Restaura una nota desde la papelera a NOTES_DIR.
    Si colisiona con una nota activa existente, añade sufijo _2, _3...
    """
    try:
        config.asegurar_directorio()
        if not ruta_papelera.exists() or not ruta_papelera.is_file():
            return None

        nombre_base = ruta_papelera.stem
        destino = config.NOTES_DIR / ruta_papelera.name
        contador = 2
        while destino.exists():
            destino = config.NOTES_DIR / f"{nombre_base}_{contador}{config.EXTENSION}"
            contador += 1

        shutil.move(str(ruta_papelera), str(destino))
        from services import note_index
        note_index.invalidar(ruta_papelera)
        note_index.invalidar(destino)
        return destino
    except Exception as e:
        print(f"Error al restaurar nota desde papelera: {e}")
        return None

def vaciar_papelera() -> int:
    """Elimina definitivamente todos los archivos de la papelera."""
    try:
        asegurar_papelera()
        archivos = list(config.TRASH_DIR.glob(f"*{config.EXTENSION}"))
        eliminados = 0
        from services import note_index
        for f in archivos:
            if f.is_file():
                note_index.invalidar(f)
                f.unlink()
                eliminados += 1
        return eliminados
    except Exception as e:
        print(f"Error al vaciar papelera: {e}")
        return 0

