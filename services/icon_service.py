from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QByteArray

ICONS_DIR = Path(__file__).parent.parent / "resources" / "icons"

def get_icon(name: str, theme: str = "dark") -> QIcon:
    """
    Carga un icono SVG desde resources/icons/ y lo colorea según el tema activo.
    """
    svg_path = ICONS_DIR / f"{name}.svg"
    if not svg_path.exists():
        return QIcon()

    color = "#e0e0e0" if theme == "dark" else "#24292f"
    try:
        content = svg_path.read_text(encoding="utf-8")
        # Sustituir el color base por el color del tema
        content = content.replace("#888888", color)
        pix = QPixmap()
        pix.loadFromData(QByteArray(content.encode("utf-8")))
        return QIcon(pix)
    except Exception as e:
        print(f"Error al cargar icono '{name}': {e}")
        return QIcon(str(svg_path))

