import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

_INDEX_LOCK = threading.Lock()

@dataclass
class IndexedNote:
    ruta: Path
    mtime: float
    titulo: str
    fecha: str
    etiquetas: List[str]
    vista_previa: str
    contenido_lower: str
    contenido: str

_INDEX: Dict[Path, IndexedNote] = {}

def extraer_vista_previa(contenido: str) -> str:
    """Extrae la primera línea de texto real como vista previa (máx 65 caracteres)."""
    lineas = contenido.splitlines()
    for linea in lineas:
        l = linea.strip()
        if (l.startswith("#") or 
            l.startswith("Fecha:") or 
            l.startswith("Etiquetas:") or 
            l.startswith("Tags:")):
            continue
        if l:
            if len(l) > 65:
                return l[:62] + "..."
            return l
    return "(Sin contenido adicional)"

def _parsear_contenido_y_metadatos(ruta: Path, contenido: str, mtime: float) -> IndexedNote:
    lineas = contenido.splitlines()
    nombre = ruta.stem
    partes = nombre.split("_", 1)
    if len(partes) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', partes[0]):
        fecha_respaldo, titulo_respaldo = partes
        titulo_respaldo = titulo_respaldo.replace("_", " ")
    else:
        fecha_respaldo = "Fecha DESCONOCIDA"
        titulo_respaldo = nombre.replace("_", " ")

    titulo = None
    fecha = None
    etiquetas = []

    # Extraer título y fecha de las primeras líneas
    if lineas:
        if lineas[0].startswith("#"):
            cand = lineas[0].lstrip("#").strip()
            if cand:
                titulo = cand
    if len(lineas) > 1:
        if lineas[1].startswith("Fecha:"):
            cand_f = lineas[1].replace("Fecha:", "").strip()
            if cand_f:
                fecha = cand_f

    # Extraer etiquetas de las primeras 15 líneas
    for lin in lineas[:15]:
        match = re.match(r'^(?:Etiquetas|Tags):\s*(.*)$', lin, re.IGNORECASE)
        if match:
            partes_tags = match.group(1).split(",")
            etiquetas = [p.strip() for p in partes_tags if p.strip()]
            break

    if not titulo:
        titulo = titulo_respaldo
    if not fecha:
        fecha = fecha_respaldo

    vista_previa = extraer_vista_previa(contenido)
    contenido_lower = contenido.lower()

    return IndexedNote(
        ruta=ruta,
        mtime=mtime,
        titulo=titulo,
        fecha=fecha,
        etiquetas=etiquetas,
        vista_previa=vista_previa,
        contenido_lower=contenido_lower,
        contenido=contenido
    )

def indexar_nota(ruta: Path) -> Optional[IndexedNote]:
    """Obtiene la nota indexada desde la caché si su mtime no ha cambiado, o lee el archivo una sola vez."""
    try:
        if not ruta.exists() or not ruta.is_file():
            invalidar(ruta)
            return None
        mtime = ruta.stat().st_mtime
    except OSError:
        invalidar(ruta)
        return None

    with _INDEX_LOCK:
        cached = _INDEX.get(ruta)
        if cached is not None and cached.mtime == mtime:
            return cached

    try:
        contenido = ruta.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    nota = _parsear_contenido_y_metadatos(ruta, contenido, mtime)
    with _INDEX_LOCK:
        _INDEX[ruta] = nota
    return nota

def indexar_notas(rutas: List[Path]) -> List[IndexedNote]:
    """Indexa o recupera de caché un lote de rutas."""
    res = []
    for r in rutas:
        n = indexar_nota(r)
        if n:
            res.append(n)
    return res

def obtener_nota(ruta: Path) -> Optional[IndexedNote]:
    """Retorna la nota indexada para la ruta."""
    return indexar_nota(ruta)

def invalidar(ruta: Path):
    """Invalida la caché para una ruta dada."""
    with _INDEX_LOCK:
        _INDEX.pop(ruta, None)

def actualizar(ruta: Path, contenido: str, mtime: Optional[float] = None):
    """Actualiza la entrada en el índice directamente."""
    if mtime is None:
        try:
            mtime = ruta.stat().st_mtime
        except OSError:
            mtime = 0.0
    nota = _parsear_contenido_y_metadatos(ruta, contenido, mtime)
    with _INDEX_LOCK:
        _INDEX[ruta] = nota

def limpiar():
    """Limpia todo el índice."""
    with _INDEX_LOCK:
        _INDEX.clear()

def listar_todas_etiquetas(rutas: Optional[List[Path]] = None) -> List[str]:
    """Retorna todas las etiquetas únicas sin releer archivos si ya están en caché."""
    if rutas is not None:
        notas = indexar_notas(rutas)
    else:
        with _INDEX_LOCK:
            notas = list(_INDEX.values())

    conjunto: Set[str] = set()
    for n in notas:
        for t in n.etiquetas:
            conjunto.add(t)
    return sorted(list(conjunto), key=lambda s: s.lower())

def buscar(query: str, rutas: Optional[List[Path]] = None, tag_filtro: Optional[str] = None) -> List[Path]:
    """Búsqueda ultrarrápida en memoria usando el índice."""
    if rutas is not None:
        notas = indexar_notas(rutas)
    else:
        with _INDEX_LOCK:
            notas = list(_INDEX.values())

    q = query.strip().lower()
    tag_f = tag_filtro.strip().lower() if tag_filtro else None

    coincidencias: List[Path] = []
    for n in notas:
        if tag_f:
            tags_lower = [t.lower() for t in n.etiquetas]
            if tag_f not in tags_lower:
                continue

        if not q:
            coincidencias.append(n.ruta)
            continue

        if q in n.titulo.lower():
            coincidencias.append(n.ruta)
            continue

        if any(q in t.lower() for t in n.etiquetas):
            coincidencias.append(n.ruta)
            continue

        if q in n.contenido_lower:
            coincidencias.append(n.ruta)

    return coincidencias

