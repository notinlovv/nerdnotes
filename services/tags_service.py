import re
from pathlib import Path
from typing import List, Union

def extraer_etiquetas(contenido_o_ruta: Union[str, Path]) -> List[str]:
    """
    Extrae la lista de etiquetas desde el contenido de una nota o archivo.
    Busca una línea como 'Etiquetas: trabajo, ideas' o 'Tags: a, b'.
    """
    contenido = ""
    if isinstance(contenido_o_ruta, Path):
        try:
            from services import note_index
            nota = note_index.indexar_nota(contenido_o_ruta)
            if nota:
                return list(nota.etiquetas)
        except Exception:
            pass
        try:
            if contenido_o_ruta.exists() and contenido_o_ruta.is_file():
                contenido = contenido_o_ruta.read_text(encoding="utf-8")
        except Exception:
            return []
    else:
        contenido = str(contenido_o_ruta)

    lineas = contenido.splitlines()[:15]  # Buscar en las primeras 15 líneas
    for linea in lineas:
        match = re.match(r'^(?:Etiquetas|Tags):\s*(.*)$', linea, re.IGNORECASE)
        if match:
            partes = match.group(1).split(',')
            etiquetas = [p.strip() for p in partes if p.strip()]
            return etiquetas
    return []

def actualizar_etiquetas_en_contenido(contenido: str, etiquetas: List[str]) -> str:
    """
    Actualiza o inserta la línea 'Etiquetas: ...' en el encabezado del contenido.
    """
    linea_etiquetas = f"Etiquetas: {', '.join(etiquetas)}" if etiquetas else "Etiquetas: "
    lineas = contenido.splitlines()
    reemplazado = False

    for i in range(min(15, len(lineas))):
        if re.match(r'^(?:Etiquetas|Tags):', lineas[i], re.IGNORECASE):
            lineas[i] = linea_etiquetas
            reemplazado = True
            break

    if not reemplazado:
        # Insertar después de Fecha: o después del título
        pos_insercion = 0
        for i in range(min(5, len(lineas))):
            if lineas[i].startswith("Fecha:") or lineas[i].startswith("#"):
                pos_insercion = i + 1
        lineas.insert(pos_insercion, linea_etiquetas)

    return "\n".join(lineas)

def listar_todas_etiquetas(notas: List[Path]) -> List[str]:
    """
    Recorre las notas y devuelve una lista ordenada de todas las etiquetas únicas.
    Utiliza note_index para evitar releer archivos desde disco.
    """
    try:
        from services import note_index
        return note_index.listar_todas_etiquetas(notas)
    except Exception:
        conjunto = set()
        for nota in notas:
            for tag in extraer_etiquetas(nota):
                conjunto.add(tag)
        return sorted(list(conjunto), key=lambda s: s.lower())

