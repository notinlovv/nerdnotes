import subprocess
from pathlib import Path
import config

def abrir_editor(ruta: Path) -> bool:
    """
    Abre la ruta especificada con el editor configurado,
    con fallback real: DEFAULT_EDITOR/EDITOR -> nano -> vi.
    """
    candidatos = []
    if config.DEFAULT_EDITOR:
        candidatos.append(config.DEFAULT_EDITOR)
    for alt in ['nano', 'vi']:
        if alt not in candidatos:
            candidatos.append(alt)

    for i, editor in enumerate(candidatos):
        if i > 0:
            print(f"Usando {editor} como alternativa")
        try:
            subprocess.call([editor, str(ruta)])
            return True
        except FileNotFoundError:
            print(f"No se encontró el editor '{editor}'")
            continue
        except Exception as e:
            print(f"Error al abrir editor '{editor}': {e}")
            continue

    print("Error: No se encontró ningún editor disponible (probados: EDITOR, nano, vi).")
    return False

def editar_nota(ruta: Path) -> None:
    if not ruta.exists():
        print("NO SE ENCONTRÓ NINGUNA NOTA")
        return 
    abrir_editor(ruta)
