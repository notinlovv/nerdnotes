import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from services.tags_service import extraer_etiquetas

# Lock para sincronizar el acceso a la caché global entre hilos
_cache_lock = threading.Lock()

# Caché en memoria: ruta -> (mtime, contenido_lower, titulo_lower, etiquetas_lower)
_CACHE_BUSQUEDA: Dict[Path, Tuple[float, str, str, List[str]]] = {}

def obtener_datos_cache(ruta: Path) -> Tuple[str, str, List[str]]:
    """Obtiene o actualiza la caché de búsqueda para un archivo de forma thread-safe."""
    try:
        mtime = ruta.stat().st_mtime
    except Exception:
        mtime = 0.0

    with _cache_lock:
        if ruta in _CACHE_BUSQUEDA:
            cached_mtime, cont, tit, tags = _CACHE_BUSQUEDA[ruta]
            if cached_mtime == mtime:
                return cont, tit, tags

    # Cargar y procesar fuera del lock para no bloquear lecturas concurrentes
    try:
        contenido = ruta.read_text(encoding="utf-8")
        cont_lower = contenido.lower()
        
        # Extraer título
        lineas = contenido.splitlines()
        titulo = ruta.stem
        for l in lineas[:5]:
            if l.startswith("#"):
                titulo = l.lstrip("#").strip()
                break
        tit_lower = titulo.lower()

        # Extraer etiquetas
        tags = [t.lower() for t in extraer_etiquetas(contenido)]

        with _cache_lock:
            _CACHE_BUSQUEDA[ruta] = (mtime, cont_lower, tit_lower, tags)
        return cont_lower, tit_lower, tags
    except Exception:
        return "", ruta.stem.lower(), []

def invalidar_cache(ruta: Optional[Path] = None):
    """Invalida la caché de búsqueda de forma thread-safe."""
    with _cache_lock:
        if ruta and ruta in _CACHE_BUSQUEDA:
            del _CACHE_BUSQUEDA[ruta]
        elif ruta is None:
            _CACHE_BUSQUEDA.clear()
    try:
        from services import note_index
        if ruta:
            note_index.invalidar(ruta)
        else:
            note_index.limpiar()
    except Exception:
        pass

def buscar_notas_sincrono(notas: List[Path], query: str, etiqueta_filtro: Optional[str] = None) -> List[Path]:
    """
    Busca notas que coincidan con query (título, contenido o etiquetas)
    y opcionalmente filtren por etiqueta.
    Función pura de Python sin dependencias de GUI o Qt.
    """
    query_lower = query.lower().strip()
    tag_filtro_lower = etiqueta_filtro.lower().strip() if etiqueta_filtro else None

    coincidencias = []
    for nota in notas:
        cont_lower, tit_lower, tags_lower = obtener_datos_cache(nota)

        # Filtro de etiqueta
        if tag_filtro_lower and tag_filtro_lower not in tags_lower:
            continue

        # Si no hay texto de búsqueda, pasa el filtro de etiqueta
        if not query_lower:
            coincidencias.append(nota)
            continue

        # Búsqueda en título, contenido o etiquetas
        if (query_lower in tit_lower or 
            query_lower in cont_lower or 
            any(query_lower in t for t in tags_lower)):
            coincidencias.append(nota)

    return coincidencias
