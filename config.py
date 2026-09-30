import os
from pathlib import Path

NOTES_DIR = Path.home() / ".nerdnotes"

DEFAULT_EDITOR = os.environ.get('EDITOR', 'nano')

EXTENSION = ".txt"

DATE_FORMAT = "%Y-%m-%d"

def asegurar_directorio():
    "Crea el directo de notas si no existe"
    NOTES_DIR.mkdir(parents=True, exist_ok=True)