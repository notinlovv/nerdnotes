import subprocess
import config
from pathlib import Path

def abrir_editor(ruta: Path) -> None:
    try:
        subprocess.call([config.DEFAULT_EDITOR, str(ruta)])
    except FileNotFoundError:
        print(f"NO HAY '{config.DEFAULT_EDITOR}'")
        print(f"Usando nano como alternativa")
    except Exception as e:
        print(f"Error al abrir editor: {e}")

def editar_nota(ruta: Path) -> None:
    if not ruta.exists():
        print("NO SE ENCONTRÓ NINGUNA NOTA")
        return 
    abrir_editor(ruta)
