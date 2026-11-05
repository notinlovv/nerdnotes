import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import config

_INDEX_LOCK = threading.RLock()

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

def _normalizar_ruta(ruta: Path) -> Path:
    """Retorna la ruta absoluta para indexar la caché."""
    if not isinstance(ruta, Path):
        ruta = Path(ruta)
    try:
        return ruta.absolute()
    except Exception:
        return ruta

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
    clave = _normalizar_ruta(ruta)
    try:
        stat_res = os.stat(clave)
        mtime = stat_res.st_mtime
    except OSError:
        invalidar(clave)
        return None

    with _INDEX_LOCK:
        cached = _INDEX.get(clave)
        if cached is not None and cached.mtime == mtime:
            return cached

    try:
        contenido = clave.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    nota = _parsear_contenido_y_metadatos(clave, contenido, mtime)
    with _INDEX_LOCK:
        _INDEX[clave] = nota
    return nota

def sincronizar_indice(directorio: Optional[Path] = None) -> List[IndexedNote]:
    """
    Sincroniza el índice en memoria con los archivos en disco:
    - Obtiene el listado de archivos .txt en el directorio de notas.
    - Consulta metadatos de cada archivo con os.stat() y extrae st_mtime.
    - Reutiliza objetos en caché si st_mtime no ha cambiado (sin abrir el archivo).
    - Lee y parsea si es nuevo o st_mtime cambió.
    - Purga de la caché los archivos que ya no existan en el sistema de archivos.
    """
    if directorio is None:
        directorio = config.NOTES_DIR

    dir_norm = _normalizar_ruta(directorio)
    try:
        if not dir_norm.exists() or not dir_norm.is_dir():
            limpiar()
            return []
        archivos_en_disco = [
            f for f in dir_norm.glob(f"*{config.EXTENSION}")
            if f.is_file() and not f.name.startswith(".")
        ]
    except Exception:
        archivos_en_disco = []

    archivos_set = {_normalizar_ruta(f) for f in archivos_en_disco}

    # Purgar de la caché los archivos que ya no existan
    with _INDEX_LOCK:
        claves_a_purgar = [
            k for k in list(_INDEX.keys())
            if (k.parent == dir_norm and k not in archivos_set) or not k.exists()
        ]
        for k in claves_a_purgar:
            _INDEX.pop(k, None)

    # Indexar o reutilizar cada archivo
    resultado: List[IndexedNote] = []
    for f in archivos_en_disco:
        n = indexar_nota(f)
        if n:
            resultado.append(n)

    return resultado

def refrescar_indice(directorio: Optional[Path] = None) -> List[IndexedNote]:
    """Alias para sincronizar_indice."""
    return sincronizar_indice(directorio)

def actualizar_indice(directorio: Optional[Path] = None) -> List[IndexedNote]:
    """Alias para sincronizar_indice."""
    return sincronizar_indice(directorio)

def indexar_notas(rutas: Optional[List[Path]] = None) -> List[IndexedNote]:
    """Indexa o recupera de caché un lote de rutas. Si rutas es None, sincroniza el índice."""
    if rutas is None:
        return sincronizar_indice()

    rutas_norm = [_normalizar_ruta(r) for r in rutas]
    with _INDEX_LOCK:
        for r in rutas_norm:
            if not r.exists():
                _INDEX.pop(r, None)

    res = []
    for r in rutas_norm:
        n = indexar_nota(r)
        if n:
            res.append(n)
    return res

def obtener_nota(ruta: Path) -> Optional[IndexedNote]:
    """Retorna la nota indexada para la ruta."""
    return indexar_nota(ruta)

def invalidar(ruta: Path):
    """Invalida la caché para una ruta dada de forma thread-safe."""
    clave = _normalizar_ruta(ruta)
    with _INDEX_LOCK:
        _INDEX.pop(clave, None)

def actualizar(ruta: Path, contenido: str, mtime: Optional[float] = None):
    """Actualiza la entrada en el índice directamente."""
    clave = _normalizar_ruta(ruta)
    if mtime is None:
        try:
            stat_res = os.stat(clave)
            mtime = stat_res.st_mtime
        except OSError:
            mtime = 0.0
    nota = _parsear_contenido_y_metadatos(clave, contenido, mtime)
    with _INDEX_LOCK:
        _INDEX[clave] = nota

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
        if not notas:
            notas = sincronizar_indice()

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
        if not notas:
            notas = sincronizar_indice()

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

