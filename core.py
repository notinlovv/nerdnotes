from typing import Optional
from pathlib import Path
import storage
import editor

def crear_nueva_nota(titulo: Optional[str] = None) -> None:
    if not titulo:
        titulo = input("TITULO DE LA NOTA: ")
        if not titulo:
            print("EL TITULO NO PUEDE ESTAR VACIO")
            return

    ruta = storage.crear_nota(titulo)
    print(f"Nota creada: {ruta.name}")

    editor.abrir_editor(ruta)

def listar_todas_notas() -> None:
    notas = storage.listar_notas()

    if not notas:
        print("No hay notas aún | CREAR CON: 'notas new'")
        return

    print("\n Tus notas:")
    print("-" * 50)
    for i, archivo in enumerate(notas, 1):
        titulo, fecha = storage.obtener_metadatos(archivo)
        if len(titulo) > 40:
            titulo = titulo[:37] + "..."
        print(f"{i:2}. [{fecha}] {titulo}")
    print("-" * 50)
    print(f"Total: {len(notas)} notas\n")

def mostrar_nota(indice: int) -> None:
    ruta = storage.obtener_ruta_por_indice(indice)
    if not ruta:
        print(f"Nota #{indice} no encontrada")
        return

    contenido = storage.leer_nota(ruta)
    titulo, fecha = storage.obtener_metadatos(ruta)

    print("\n" + "=" * 60)
    print(contenido)
    print("\n" + "=" * 60)

def editar_nota_existente(indice: int) -> None:
    ruta = storage.obtener_ruta_por_indice(indice)
    if not ruta:
        print(f"Nota #{indice} no encontrada")
        return
    print(f"Editando: {ruta.name}") 
    editor.editar_nota(ruta) 
    print(f"Nota actualizada")

def eliminar_nota_existente(indice: int) -> None:
    ruta = storage.obtener_ruta_por_indice(indice)
    if not ruta:
        print(f"Nota #{indice} no encontrada")
        return

    titulo, _ = storage.obtener_metadatos(ruta)
    confirmacion = input(f"Desea eliminar '{titulo}'? [s/N]").lower()
    if confirmacion in ('s', 'si', 'sí'):
        storage.eliminar_nota(ruta)
        print(f"Nota eliminada")
    else:
        print("Operacion cancelada")