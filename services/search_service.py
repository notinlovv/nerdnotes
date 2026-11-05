import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable
from services.tags_service import extraer_etiquetas
from services import note_index

# Lock para compatibilidad hacia atrás
_cache_lock = threading.Lock()
_CACHE_BUSQUEDA: Dict[Path, Tuple[float, str, str, List[str]]] = {}

def obtener_datos_cache(ruta: Path) -> Tuple[str, str, List[str]]:
    """Obtiene datos parseados consultando la caché centralizada de note_index."""
    nota = note_index.indexar_nota(ruta)
    if nota:
        return nota.contenido_lower, nota.titulo.lower(), [t.lower() for t in nota.etiquetas]
    return "", ruta.stem.lower(), []

def invalidar_cache(ruta: Optional[Path] = None):
    """Invalida la caché de búsqueda de forma thread-safe en el índice centralizado."""
    with _cache_lock:
        if ruta and ruta in _CACHE_BUSQUEDA:
            del _CACHE_BUSQUEDA[ruta]
        elif ruta is None:
            _CACHE_BUSQUEDA.clear()
    if ruta:
        note_index.invalidar(ruta)
    else:
        note_index.limpiar()

def buscar_notas_sincrono(
    notas: Optional[List[Path]] = None,
    query: str = "",
    etiqueta_filtro: Optional[str] = None,
    is_interrupted: Optional[Callable[[], bool]] = None
) -> List[Path]:
    """
    Busca notas que coincidan con query (título, contenido o etiquetas)
    y opcionalmente filtren por etiqueta, consultando la caché centralizada de note_index
    en lugar de listar directamente el directorio físico en cada query.
    Permite cancelación reactiva mediante is_interrupted.
    """
    if notas is None:
        notas_indexadas = note_index.sincronizar_indice()
    else:
        notas_indexadas = []
        for n in notas:
            if is_interrupted and is_interrupted():
                return []
            n_obj = note_index.indexar_nota(n)
            if n_obj:
                notas_indexadas.append(n_obj)

    query_lower = query.lower().strip()
    tag_filtro_lower = etiqueta_filtro.lower().strip() if etiqueta_filtro else None

    coincidencias = []
    for nota in notas_indexadas:
        if is_interrupted and is_interrupted():
            return []

        # Filtro de etiqueta
        if tag_filtro_lower:
            tags_lower = [t.lower() for t in nota.etiquetas]
            if tag_filtro_lower not in tags_lower:
                continue

        # Si no hay texto de búsqueda, pasa el filtro de etiqueta
        if not query_lower:
            coincidencias.append(nota.ruta)
            continue

        # Búsqueda en título, contenido o etiquetas
        if (query_lower in nota.titulo.lower() or 
            query_lower in nota.contenido_lower or 
            any(query_lower in t.lower() for t in nota.etiquetas)):
            coincidencias.append(nota.ruta)

    return coincidencias
