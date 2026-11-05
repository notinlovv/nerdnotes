import re
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import config

from services.config_service import (
    obtener_notas_fijadas, fijar_nota, desfijar_nota, es_nota_fijada, actualizar_nombre_fijada
)
from services.trash_service import (
    mover_a_papelera, listar_papelera, restaurar_nota_papelera, vaciar_papelera
)
from services.tags_service import (
    extraer_etiquetas, actualizar_etiquetas_en_contenido, listar_todas_etiquetas
)
from services.export_service import exportar_nota
from services.search_service import (
    buscar_notas_sincrono, invalidar_cache
)
from services import note_index

__all__ = [
    "sanitizar_nombre",
    "sanear_nombre_archivo",
    "escritura_atomica",
    "listar_notas",
    "obtener_metadatos",
    "crear_nota",
    "renombrar_nota",
    "leer_nota",
    "guardar_nota",
    "eliminar_nota",
    "obtener_ruta_por_indice",
    "ordenar_notas",
    "buscar_en_notas",
    "mover_a_papelera",
    "listar_papelera",
    "restaurar_nota_papelera",
    "vaciar_papelera",
    "extraer_etiquetas",
    "actualizar_etiquetas_en_contenido",
    "listar_todas_etiquetas",
    "obtener_notas_fijadas",
    "fijar_nota",
    "desfijar_nota",
    "es_nota_fijada",
    "exportar_nota",
]

CARACTERES_INVALIDOS = r'[/\\:*?"<>|\x00-\x1f]'

def escritura_atomica(ruta: Path, contenido: str, encoding: str = "utf-8") -> bool:
    """
    Escribe contenido en un archivo temporal en el mismo directorio (mismo filesystem),
    fuerza la sincronización en disco con fsync y reemplaza el archivo destino
    de forma atómica usando os.replace.
    Si ocurre una excepción, limpia el archivo temporal.
    """
    directorio = ruta.parent
    directorio.mkdir(parents=True, exist_ok=True)
    tf = None
    temp_name = None
    try:
        tf = tempfile.NamedTemporaryFile("w", dir=directorio, delete=False, encoding=encoding)
        temp_name = tf.name
        tf.write(contenido)
        tf.flush()
        os.fsync(tf.fileno())
        tf.close()
        os.replace(temp_name, str(ruta))
        return True
    except Exception as e:
        print(f"Error en escritura atómica para {ruta.name}: {e}")
        if tf and not tf.closed:
            try:
                tf.close()
            except Exception:
                pass
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        return False

def sanitizar_nombre(nombre: str, max_longitud: int = 100) -> str:
    """
    Sanitiza un nombre de archivo para evitar saltos de directorio y caracteres peligrosos.
    - Remueve o reemplaza caracteres inválidos/peligrosos (/, \\, \0, :, *, ?, ", <, >, | y de control).
    - Evita ataques o errores de salto de directorio (../).
    - Limita la longitud máxima (100 caracteres por defecto).
    - Asigna el fallback 'nota_sin_titulo' si el nombre resultante queda vacío.
    """
    if not nombre or not isinstance(nombre, str):
        return "nota_sin_titulo"

    # Reemplazar secuencias de saltos de directorio '..'
    saneado = re.sub(r'\.{2,}', '_', nombre)
    # Reemplazar caracteres prohibidos / inválidos
    saneado = re.sub(CARACTERES_INVALIDOS, '_', saneado)
    # Reemplazar espacios por guiones bajos
    saneado = saneado.replace(' ', '_')
    # Colapsar guiones bajos repetidos
    saneado = re.sub(r'_+', '_', saneado)
    # Quitar guiones bajos, puntos y espacios sobrantes de los extremos
    saneado = saneado.strip('_. ')

    # Limitar longitud máxima
    if len(saneado) > max_longitud:
        saneado = saneado[:max_longitud].rstrip('_. ')

    if not saneado:
        return "nota_sin_titulo"

    return saneado

def sanear_nombre_archivo(titulo: str) -> str:
    """
    Función de compatibilidad: sanea el título para usarlo como nombre de archivo seguro.
    """
    return sanitizar_nombre(titulo)

def listar_notas() -> List[Path]:
    """
    Lista todos los archivos de notas ordenados descendentemente por nombre.
    Ignora archivos ocultos, .papelera y archivos de configuración.
    """
    try:
        config.asegurar_directorio()
        archivos = [
            f for f in config.NOTES_DIR.glob(f"*{config.EXTENSION}")
            if f.is_file() and not f.name.startswith(".")
        ]
        return sorted(archivos, reverse=True)
    except Exception as e:
        print(f"Error al listar notas: {e}")
        return []

def obtener_metadatos(archivo: Path) -> Tuple[str, str]:
    """
    Obtiene el título y la fecha de la nota utilizando la caché de note_index.
    Lee el título desde la primera línea '# ...' del archivo,
    con el nombre del archivo como respaldo si no existe o no se puede leer.
    """
    nota = note_index.indexar_nota(archivo)
    if nota:
        return nota.titulo, nota.fecha

    nombre = archivo.stem
    partes = nombre.split("_", 1)
    if len(partes) == 2:
        fecha_respaldo, titulo_respaldo = partes
        titulo_respaldo = titulo_respaldo.replace("_", " ")
    else:
        fecha_respaldo = "Fecha DESCONOCIDA"
        titulo_respaldo = nombre.replace("_", " ")

    return titulo_respaldo, fecha_respaldo

def crear_nota(titulo: str, contenido: str = "", etiquetas: Optional[List[str]] = None) -> Optional[Path]:
    """
    Crea una nueva nota de forma atómica. Evita sobrescrituras añadiendo sufijos (_2, _3...).
    Sanea el nombre del archivo pero conserva el título original en la primera línea.
    """
    try:
        config.asegurar_directorio()
        
        ahora = datetime.now()
        fecha = ahora.strftime(config.DATE_FORMAT)
        
        titulo_saneado = sanitizar_nombre(titulo)
        base_nombre = f"{fecha}_{titulo_saneado}"
        nombre_archivo = f"{base_nombre}{config.EXTENSION}"
        ruta = config.NOTES_DIR / nombre_archivo
        
        contador = 2
        while ruta.exists():
            nombre_archivo = f"{base_nombre}_{contador}{config.EXTENSION}"
            ruta = config.NOTES_DIR / nombre_archivo
            contador += 1

        titulo_encabezado = titulo if (titulo and titulo.strip()) else "nota_sin_titulo"
        linea_etiquetas = f"Etiquetas: {', '.join(etiquetas)}\n" if etiquetas else "Etiquetas:\n"
        template = f"""# {titulo_encabezado}
Fecha: {fecha}
{linea_etiquetas}
{contenido}
"""
        exito = escritura_atomica(ruta, template)
        if exito:
            note_index.actualizar(ruta, template)
            invalidar_cache(ruta)
            return ruta
        return None
    except Exception as e:
        print(f"Error al crear nota: {e}")
        return None

def renombrar_nota(ruta_actual: Path, nuevo_titulo: str) -> Optional[Path]:
    """
    Renombra una nota de forma atómica: actualiza su nombre de archivo y el encabezado '# ...'.
    Preserva la fecha original del nombre de archivo.
    Evita sobrescribir si ya existe otro archivo con ese nombre agregando sufijos.
    """
    try:
        config.asegurar_directorio()
        if not ruta_actual.exists() or not ruta_actual.is_file():
            return None

        nuevo_titulo = nuevo_titulo.strip()
        if not nuevo_titulo:
            return None

        # Obtener fecha existente del archivo o usar hoy
        nombre_viejo = ruta_actual.stem
        partes = nombre_viejo.split("_", 1)
        if len(partes) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', partes[0]):
            fecha = partes[0]
        else:
            fecha = datetime.now().strftime(config.DATE_FORMAT)

        titulo_saneado = sanitizar_nombre(nuevo_titulo)
        base_nombre = f"{fecha}_{titulo_saneado}"
        nuevo_nombre = f"{base_nombre}{config.EXTENSION}"
        nueva_ruta = config.NOTES_DIR / nuevo_nombre

        # Leer y actualizar encabezado
        contenido = ruta_actual.read_text(encoding="utf-8")
        lineas = contenido.splitlines()
        if lineas and lineas[0].startswith("#"):
            lineas[0] = f"# {nuevo_titulo}"
        else:
            lineas.insert(0, f"# {nuevo_titulo}")
        nuevo_contenido = "\n".join(lineas)

        # Si el nombre no cambia en disco, solo actualizamos el encabezado atómicamente
        if nueva_ruta == ruta_actual:
            if escritura_atomica(ruta_actual, nuevo_contenido):
                note_index.actualizar(ruta_actual, nuevo_contenido)
                invalidar_cache(ruta_actual)
                return ruta_actual
            return None

        # Evitar colisión con otros archivos
        contador = 2
        while nueva_ruta.exists() and nueva_ruta != ruta_actual:
            nuevo_nombre = f"{base_nombre}_{contador}{config.EXTENSION}"
            nueva_ruta = config.NOTES_DIR / nuevo_nombre
            contador += 1

        # Escribir atómicamente en la nueva ruta y eliminar la anterior
        if escritura_atomica(nueva_ruta, nuevo_contenido):
            try:
                ruta_actual.unlink()
            except OSError:
                pass

            # Si estaba fijada, actualizar su nombre en la configuración
            actualizar_nombre_fijada(ruta_actual.name, nueva_ruta.name)

            note_index.invalidar(ruta_actual)
            note_index.actualizar(nueva_ruta, nuevo_contenido)
            invalidar_cache(ruta_actual)
            invalidar_cache(nueva_ruta)
            return nueva_ruta
        return None
    except Exception as e:
        print(f"Error al renombrar nota: {e}")
        return None

def leer_nota(ruta: Path) -> str:
    """Lee y retorna el contenido de la nota de forma segura."""
    try:
        if not ruta.exists():
            return ""
        return ruta.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error al leer la nota {ruta.name}: {e}")
        return ""

def guardar_nota(ruta: Path, contenido: str) -> bool:
    """Guarda el contenido en el archivo de forma atómica y segura."""
    try:
        exito = escritura_atomica(ruta, contenido)
        if exito:
            note_index.actualizar(ruta, contenido)
            invalidar_cache(ruta)
            return True
        return False
    except Exception as e:
        print(f"Error al guardar la nota {ruta.name}: {e}")
        return False

def eliminar_nota(ruta: Path) -> bool:
    """
    Elimina permanentemente una nota.
    """
    try:
        if ruta.exists():
            ruta.unlink()
            desfijar_nota(ruta.name)
            note_index.invalidar(ruta)
            invalidar_cache(ruta)
            return True
        return False
    except Exception as e:
        print(f"Error al eliminar la nota {ruta.name}: {e}")
        return False

def obtener_ruta_por_indice(indice: int) -> Optional[Path]:
    """Retorna la ruta de la nota según su índice (1-based)."""
    notas = listar_notas()
    if 1 <= indice <= len(notas):
        return notas[indice - 1]
    return None

def ordenar_notas(notas: List[Path], criterio: str = "fecha", descendente: bool = True) -> List[Path]:
    """
    Ordena una lista de notas por fecha, título o fecha de modificación usando la caché de note_index.
    Las notas fijadas (pinned) se colocan siempre arriba manteniendo el criterio.
    Las notas con fecha desconocida se colocan siempre al final en el ordenamiento por fecha.
    """
    from services.config_service import obtener_notas_fijadas_set
    pinned_set = obtener_notas_fijadas_set()

    def clave_orden(p: Path):
        nota = note_index.indexar_nota(p)
        if criterio == "titulo":
            return nota.titulo.lower() if nota else p.stem.lower()
        elif criterio == "modificacion":
            return nota.mtime if nota else 0.0
        else:  # "fecha"
            fecha = nota.fecha if nota else "Fecha DESCONOCIDA"
            if not re.match(r'^\d{4}-\d{2}-\d{2}', fecha):
                return "0000-00-00" if descendente else "9999-99-99"
            return fecha

    fijadas = [p for p in notas if p.name in pinned_set]
    no_fijadas = [p for p in notas if p.name not in pinned_set]

    fijadas.sort(key=clave_orden, reverse=descendente)
    no_fijadas.sort(key=clave_orden, reverse=descendente)

    return fijadas + no_fijadas

def buscar_en_notas(query: str, notas: Optional[List[Path]] = None, etiqueta_filtro: Optional[str] = None) -> List[Path]:
    """Busca notas por título, contenido o etiquetas usando búsqueda ultrarrápida indexada."""
    if notas is None:
        notas = listar_notas()
    return note_index.buscar(query, notas, etiqueta_filtro)
