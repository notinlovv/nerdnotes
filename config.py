import os
from pathlib import Path

def _obtener_notes_dir() -> Path:
    env_dir = os.environ.get("NERDNOTES_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".nerdnotes"

NOTES_DIR = _obtener_notes_dir()
TRASH_DIR = NOTES_DIR / ".papelera"
CONFIG_FILE = NOTES_DIR / ".config.json"

DEFAULT_EDITOR = os.environ.get('EDITOR', 'nano')

EXTENSION = ".txt"

DATE_FORMAT = "%Y-%m-%d"

def asegurar_directorio():
    """Crea los directorios de notas y papelera si no existen y actualiza rutas si cambió NOTES_DIR o NERDNOTES_DIR."""
    global NOTES_DIR, TRASH_DIR, CONFIG_FILE
    env_dir = os.environ.get("NERDNOTES_DIR")
    if env_dir and NOTES_DIR != Path(env_dir):
        NOTES_DIR = Path(env_dir)
    TRASH_DIR = NOTES_DIR / ".papelera"
    CONFIG_FILE = NOTES_DIR / ".config.json"
    try:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        TRASH_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
