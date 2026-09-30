from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import config

def listar_notas() -> List[Path]:
    config.asegurar_directorio()
    archivos = list(config.NOTES_DIR.glob(f"*{config.EXTENSION}"))
    return sorted(archivos, reverse=True)

def obtener_metadatos(archivo: Path) -> Tuple[str, str]:
    nombre = archivo.stem
    partes = nombre.split("_", 1)
    if len(partes) == 2:
        fecha, titulo = partes
        return titulo.replace("_", " "), fecha
    return nombre.replace("_", " "), "Fecha DESCONOCIDA"

def crear_nota(titulo: str, contenido: str = "") -> Path:
    config.asegurar_directorio()
    
    # Obtener fecha formateada
    ahora = datetime.now()
    fecha = ahora.strftime(config.DATE_FORMAT)  # "2026-09-09"
    
    # Crear nombre de archivo: YYYY-MM-DD_titulo.txt
    nombre_archivo = f"{fecha}_{titulo.replace(' ', '_')}{config.EXTENSION}"
    ruta = config.NOTES_DIR / nombre_archivo
    
    template = f"""# {titulo}
Fecha: {fecha}

{contenido}
"""
    
    ruta.write_text(template, encoding='utf-8')
    return ruta

def leer_nota(ruta: Path) -> str:
    return ruta.read_text(encoding='utf-8')

def eliminar_nota(ruta: Path) -> None:
    if ruta.exists():
        ruta.unlink()

def obtener_ruta_por_indice(indice: int) -> Optional[Path]:
    notas = listar_notas()
    if 1 <= indice <= len(notas):
        return notas[indice - 1]
    return None