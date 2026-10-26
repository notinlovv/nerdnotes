#!/usr/bin/env python3
"""
Script de generación de notas para prueba de carga y benchmarking.
Genera N notas (por defecto 2000) y mide el tiempo de escaneo, ordenamiento y búsqueda.
"""

import os
import sys
import time
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

TAGS_POOL = [
    "trabajo", "personal", "ideas", "proyecto", "python", "dev",
    "urgente", "nerdnotes", "reunion", "diseño", "backend", "frontend",
    "linux", "config", "tutorial", "investigacion", "finanzas", "viajes"
]

TITULOS_TEMAS = [
    "Plan de arquitectura para el servicio de indexación",
    "Notas sobre optimización de rendimiento en bases de datos",
    "Lista de tareas pendientes para la versión 1.0",
    "Resumen de la reunión de equipo sobre diseño UX",
    "Ideas para el nuevo sistema de extensiones",
    "Comandos útiles para terminal y scripting bash",
    "Configuración del entorno de desarrollo Linux",
    "Boceto de la interfaz de tres paneles con splitter",
    "Reflexiones sobre algoritmos de búsqueda y debounce",
    "Guía rápida de atajos de teclado y productividad",
    "Pruebas de estrés y estabilidad con grandes volúmenes",
    "Documentación de APIs internas y desacoplamiento de dependencias"
]

def generar_notas(directorio: Path, cantidad: int = 2000) -> float:
    """Genera 'cantidad' de notas en 'directorio'."""
    directorio.mkdir(parents=True, exist_ok=True)
    
    fecha_base = datetime.now()
    t_inicio = time.perf_counter()

    for i in range(1, cantidad + 1):
        dias_atras = random.randint(0, 730)
        fecha_nota = (fecha_base - timedelta(days=dias_atras)).strftime("%Y-%m-%d")
        
        tema = TITULOS_TEMAS[i % len(TITULOS_TEMAS)]
        titulo = f"{tema} - Parte {i}"
        
        # Seleccionar 1 a 3 etiquetas al azar
        tags = random.sample(TAGS_POOL, k=random.randint(1, 3))
        
        # Sanear para nombre de archivo
        titulo_limpio = "".join(c if c.isalnum() else "_" for c in titulo)[:45]
        nombre_archivo = f"{fecha_nota}_{titulo_limpio}_{i}.txt"
        ruta = directorio / nombre_archivo

        contenido = f"""# {titulo}
Fecha: {fecha_nota}
Etiquetas: {', '.join(tags)}

Esta es una nota de prueba generada automáticamente (ítem #{i}).
Contiene párrafos de texto para verificar el rendimiento del índice en memoria.
- Punto clave {random.randint(1, 100)} sobre la arquitectura del sistema.
- [ ] Tarea pendiente de verificación con identificador clave_{i}.
Código o apunte relevante: `print("NerdNotes test #{i}")`.
"""
        ruta.write_text(contenido, encoding="utf-8")

    t_fin = time.perf_counter()
    return t_fin - t_inicio

def ejecutar_benchmark(directorio: Path):
    """Ejecuta mediciones de rendimiento sobre el directorio con notas."""
    # Configurar directorio para NerdNotes
    os.environ["NERDNOTES_DIR"] = str(directorio)
    import config
    config.asegurar_directorio()

    from services import note_index
    import storage

    print("\n--- INICIANDO BENCHMARK ---")
    archivos = storage.listar_notas()
    total = len(archivos)
    print(f"Total de notas encontradas en disco: {total}")

    # 1. Primer escaneo (carga fría en note_index)
    note_index.limpiar()
    t0 = time.perf_counter()
    notas_indexadas = note_index.indexar_notas(archivos)
    t_primer_escaneo = (time.perf_counter() - t0) * 1000
    print(f"1. Primer escaneo (frío, leyendo {total} archivos): {t_primer_escaneo:.2f} ms")

    # 2. Segundo escaneo (carga caliente con caché en memoria)
    t0 = time.perf_counter()
    notas_calientes = note_index.indexar_notas(archivos)
    t_segundo_escaneo = (time.perf_counter() - t0) * 1000
    print(f"2. Segundo escaneo (caliente, usando mtime): {t_segundo_escaneo:.2f} ms")

    # 3. Ordenamiento de notas (usando note_index)
    t0 = time.perf_counter()
    ordenadas = storage.ordenar_notas(archivos, criterio="fecha", descendente=True)
    t_orden = (time.perf_counter() - t0) * 1000
    print(f"3. Ordenamiento por fecha ({total} notas): {t_orden:.2f} ms")

    # 4. Listado de etiquetas únicas (usando note_index)
    t0 = time.perf_counter()
    etiquetas = note_index.listar_todas_etiquetas()
    t_etiquetas = (time.perf_counter() - t0) * 1000
    print(f"4. Listar etiquetas únicas ({len(etiquetas)} encontradas): {t_etiquetas:.2f} ms")

    # 5. Búsqueda de texto en memoria (título y contenido)
    terminos_busqueda = ["arquitectura", "clave_100", "python", "inexistente_xyz"]
    print("5. Búsqueda en memoria:")
    for term in terminos_busqueda:
        t0 = time.perf_counter()
        matches = note_index.buscar(term, archivos)
        t_busqueda = (time.perf_counter() - t0) * 1000
        print(f"   - Buscar '{term}': {len(matches)} coincidencias en {t_busqueda:.2f} ms")

    # Comprobar criterio de rendimiento: < 300 ms tras el primer escaneo
    print("\n--- RESULTADOS ---")
    if t_segundo_escaneo < 300:
        print(f"✅ ÉXITO: Tiempo de escaneo caliente {t_segundo_escaneo:.2f} ms < 300 ms objetivo!")
    else:
        print(f"❌ FALLO: Tiempo {t_segundo_escaneo:.2f} ms supera el límite de 300 ms.")

def main():
    parser = argparse.ArgumentParser(description="Generador de notas de prueba y benchmark.")
    parser.add_argument("--count", type=int, default=2000, help="Cantidad de notas a generar (por defecto: 2000)")
    parser.add_argument("--dir", type=str, default="", help="Directorio destino (por defecto: temporal)")
    parser.add_argument("--solo-benchmark", action="store_true", help="Solo ejecutar benchmark en el directorio sin generar")

    args = parser.parse_args()

    import tempfile
    if args.dir:
        destino = Path(args.dir)
    else:
        temp_dir = tempfile.mkdtemp(prefix="nerdnotes_loadtest_")
        destino = Path(temp_dir)

    print(f"Directorio de notas: {destino}")

    if not args.solo_benchmark:
        print(f"Generando {args.count} notas...")
        t_gen = generar_notas(destino, args.count)
        print(f"Generación completada en {t_gen:.2f} s ({args.count / t_gen:.1f} notas/s).")

    ejecutar_benchmark(destino)

if __name__ == "__main__":
    main()

