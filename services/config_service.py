import os
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import config

_CACHE_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_MTIME: float = -1.0
_CONFIG_PATH: Optional[Path] = None

def invalidar_cache_config():
    """Invalida la caché de configuración en memoria."""
    global _CACHE_CONFIG, _CONFIG_MTIME, _CONFIG_PATH
    _CACHE_CONFIG = None
    _CONFIG_MTIME = -1.0
    _CONFIG_PATH = None

def cargar_config() -> Dict[str, Any]:
    """Carga la configuración desde .config.json cacheando en memoria según su mtime."""
    global _CACHE_CONFIG, _CONFIG_MTIME, _CONFIG_PATH
    try:
        config.asegurar_directorio()
        ruta = config.CONFIG_FILE
        if ruta.exists() and ruta.is_file():
            try:
                mtime = ruta.stat().st_mtime
                if _CACHE_CONFIG is not None and _CONFIG_MTIME == mtime and _CONFIG_PATH == ruta:
                    return _CACHE_CONFIG
                contenido = ruta.read_text(encoding="utf-8")
                _CACHE_CONFIG = json.loads(contenido)
                _CONFIG_MTIME = mtime
                _CONFIG_PATH = ruta
                return _CACHE_CONFIG
            except Exception as e:
                print(f"Error al leer configuración: {e}")
        else:
            _CACHE_CONFIG = {"pinned": []}
            _CONFIG_MTIME = -1.0
            _CONFIG_PATH = ruta
            return _CACHE_CONFIG
    except Exception as e:
        print(f"Error general en configuración: {e}")
    return _CACHE_CONFIG if _CACHE_CONFIG is not None else {"pinned": []}

def guardar_config(datos: Dict[str, Any]) -> bool:
    """Guarda los datos de configuración en .config.json de forma atómica y actualiza la caché."""
    global _CACHE_CONFIG, _CONFIG_MTIME, _CONFIG_PATH
    temp_name = None
    try:
        config.asegurar_directorio()
        texto = json.dumps(datos, indent=2, ensure_ascii=False)
        directorio = config.CONFIG_FILE.parent
        with tempfile.NamedTemporaryFile("w", dir=directorio, delete=False, encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
            temp_name = f.name
        os.replace(temp_name, str(config.CONFIG_FILE))
        _CACHE_CONFIG = dict(datos)
        _CONFIG_PATH = config.CONFIG_FILE
        try:
            _CONFIG_MTIME = config.CONFIG_FILE.stat().st_mtime
        except OSError:
            _CONFIG_MTIME = -1.0
        return True
    except Exception as e:
        print(f"Error al guardar configuración: {e}")
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        return False

def obtener_notas_fijadas() -> List[str]:
    """Retorna la lista de nombres de archivos fijados."""
    datos = cargar_config()
    return datos.get("pinned", [])

def obtener_notas_fijadas_set() -> Set[str]:
    """Retorna un conjunto de nombres de archivos fijados para búsqueda O(1)."""
    return set(obtener_notas_fijadas())

def es_nota_fijada(nombre_archivo: str) -> bool:
    """Indica si una nota está fijada arriba."""
    return nombre_archivo in obtener_notas_fijadas_set()

def fijar_nota(nombre_archivo: str, fijar: bool = True) -> bool:
    """Fija o desfija una nota."""
    datos = cargar_config()
    fijadas = datos.get("pinned", [])
    if fijar and nombre_archivo not in fijadas:
        fijadas.append(nombre_archivo)
    elif not fijar and nombre_archivo in fijadas:
        fijadas.remove(nombre_archivo)
    datos["pinned"] = fijadas
    return guardar_config(datos)

def desfijar_nota(nombre_archivo: str) -> bool:
    """Desfija una nota."""
    return fijar_nota(nombre_archivo, fijar=False)

def actualizar_nombre_fijada(antiguo_nombre: str, nuevo_nombre: str) -> bool:
    """Actualiza el nombre de una nota fijada al renombrarla."""
    datos = cargar_config()
    fijadas = datos.get("pinned", [])
    if antiguo_nombre in fijadas:
        idx = fijadas.index(antiguo_nombre)
        fijadas[idx] = nuevo_nombre
        datos["pinned"] = fijadas
        return guardar_config(datos)
    return False
