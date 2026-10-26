from pathlib import Path
from typing import Optional

def exportar_a_pdf(contenido: str, ruta_salida: Path) -> bool:
    """
    Exporta el contenido Markdown a un archivo PDF usando QPdfWriter y QTextDocument.
    Importa PyQt6 de forma perezosa solo cuando se requiere exportar a PDF.
    """
    try:
        from PyQt6.QtGui import QPdfWriter, QTextDocument, QPageSize, QPageLayout
        from PyQt6.QtCore import QMarginsF
    except ImportError as e:
        print(f"Error: Se requiere PyQt6 para exportar a PDF: {e}")
        return False

    try:
        doc = QTextDocument()
        doc.setMarkdown(contenido)
        writer = QPdfWriter(str(ruta_salida))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        doc.print(writer)
        return True
    except Exception as e:
        print(f"Error al exportar a PDF: {e}")
        return False

def exportar_a_markdown(contenido: str, ruta_salida: Path) -> bool:
    """Exporta el contenido a un archivo con formato Markdown (.md)."""
    try:
        ruta_salida.write_text(contenido, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error al exportar a Markdown: {e}")
        return False

def exportar_a_txt(contenido: str, ruta_salida: Path) -> bool:
    """Exporta el contenido a un archivo de texto plano (.txt)."""
    try:
        ruta_salida.write_text(contenido, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error al exportar a TXT: {e}")
        return False

def exportar_nota(contenido: str, ruta_salida: Path, formato: str = "pdf") -> bool:
    """
    Exporta una nota según el formato indicado ('pdf', 'md', 'txt').
    """
    formato_lower = formato.lower().strip('.')
    if formato_lower == "pdf":
        return exportar_a_pdf(contenido, ruta_salida)
    elif formato_lower in ("md", "markdown"):
        return exportar_a_markdown(contenido, ruta_salida)
    elif formato_lower in ("txt", "texto"):
        return exportar_a_txt(contenido, ruta_salida)
    else:
        return exportar_a_txt(contenido, ruta_salida)
