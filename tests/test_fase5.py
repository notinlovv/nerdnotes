import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QKeyEvent, QKeySequence

import config
import storage
from editor import NoteEditor, NoteTitleEdit, NoteFormatToolbar
from ui.markdown_highlighter import MarkdownHighlighter
from main_gui import NerdNotesApp

app = QApplication.instance() or QApplication(sys.argv)


class TestFase5MarkdownFormat(unittest.TestCase):
    def setUp(self):
        self.editor = NoteEditor()

    def test_formato_negrita_contextual_y_undo(self):
        # 1. Envolver selección
        self.editor.setPlainText("texto a formatear")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("negrita")
        self.assertEqual(self.editor.toPlainText(), "**texto** a formatear")

        # 2. Toggle off si ya está envuelto
        self.editor.aplicar_formato("negrita")
        self.assertEqual(self.editor.toPlainText(), "texto a formatear")

        # 3. Undo atómico
        self.editor.aplicar_formato("negrita")
        self.assertEqual(self.editor.toPlainText(), "**texto** a formatear")
        self.editor.document().undo()
        self.assertEqual(self.editor.toPlainText(), "texto a formatear")

        # 4. Sin selección sobre espacio en blanco -> inserta **** y cursor en medio
        self.editor.setPlainText("")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)
        self.editor.aplicar_formato("negrita")
        self.assertEqual(self.editor.toPlainText(), "****")
        self.assertEqual(self.editor.textCursor().position(), 2)

    def test_formato_cursiva_contextual(self):
        self.editor.setPlainText("palabra clave")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(7, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("cursiva")
        self.assertEqual(self.editor.toPlainText(), "*palabra* clave")

        # Toggle off
        self.editor.aplicar_formato("cursiva")
        self.assertEqual(self.editor.toPlainText(), "palabra clave")

    def test_formato_codigo_inline_y_bloque(self):
        # Inline code
        self.editor.setPlainText("variable_x = 10")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("codigo")
        self.assertEqual(self.editor.toPlainText(), "`variable_x` = 10")

        # Multiline code block
        self.editor.setPlainText("def foo():\n    return 42")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(len(self.editor.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("codigo")
        self.assertEqual(self.editor.toPlainText(), "```\ndef foo():\n    return 42\n```")

        # Sin selección -> plantilla con cursor en el cuerpo
        self.editor.setPlainText("")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)
        self.editor.aplicar_formato("codigo")
        self.assertEqual(self.editor.toPlainText(), "```\n\n```")
        self.assertEqual(self.editor.textCursor().position(), 4)

    def test_formato_cita(self):
        self.editor.setPlainText("Primera linea\nSegunda linea")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(len(self.editor.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("cita")
        self.assertEqual(self.editor.toPlainText(), "> Primera linea\n> Segunda linea")

        # Toggle off
        self.editor.aplicar_formato("cita")
        self.assertEqual(self.editor.toPlainText(), "Primera linea\nSegunda linea")

    def test_formato_enlace(self):
        # Con texto seleccionado
        self.editor.setPlainText("visita Google hoy")
        cursor = self.editor.textCursor()
        cursor.setPosition(7)
        cursor.setPosition(13, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("enlace")
        self.assertEqual(self.editor.toPlainText(), "visita [Google](url) hoy")

        # Con URL seleccionada
        self.editor.setPlainText("link: https://example.com")
        cursor = self.editor.textCursor()
        cursor.setPosition(6)
        cursor.setPosition(len(self.editor.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.editor.aplicar_formato("enlace")
        self.assertEqual(self.editor.toPlainText(), "link: [enlace](https://example.com)")

        # Sin selección
        self.editor.setPlainText("")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)
        self.editor.aplicar_formato("enlace")
        self.assertEqual(self.editor.toPlainText(), "[texto](url)")

    def test_atajos_teclado_en_editor(self):
        self.editor.setPlainText("atajo negrita")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        # Simular Ctrl+B
        event_ctrl_b = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
        self.editor.keyPressEvent(event_ctrl_b)
        self.assertEqual(self.editor.toPlainText(), "**atajo** negrita")

        # Simular Ctrl+I
        cursor = self.editor.textCursor()
        cursor.setPosition(10)
        cursor.setPosition(17, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        event_ctrl_i = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
        self.editor.keyPressEvent(event_ctrl_i)
        self.assertEqual(self.editor.toPlainText(), "**atajo** *negrita*")

        # Simular Ctrl+K
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)

        event_ctrl_k = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        self.editor.keyPressEvent(event_ctrl_k)
        self.assertIn("[texto](url)", self.editor.toPlainText())


class TestFase5ToolbarYHighlighter(unittest.TestCase):
    def setUp(self):
        self.editor = NoteEditor()
        self.toolbar = NoteFormatToolbar(self.editor)

    def test_toolbar_botones_y_focus_policy(self):
        self.assertTrue(hasattr(self.toolbar, "btn_bold"))
        self.assertTrue(hasattr(self.toolbar, "btn_italic"))
        self.assertTrue(hasattr(self.toolbar, "btn_h1"))
        self.assertTrue(hasattr(self.toolbar, "btn_h2"))
        self.assertTrue(hasattr(self.toolbar, "btn_bullet"))
        self.assertTrue(hasattr(self.toolbar, "btn_checklist"))
        self.assertTrue(hasattr(self.toolbar, "btn_quote"))
        self.assertTrue(hasattr(self.toolbar, "btn_code"))
        self.assertTrue(hasattr(self.toolbar, "btn_link"))

        # Todos los botones deben tener NoFocus para no deseleccionar el texto en el editor
        for btn in (
            self.toolbar.btn_bold, self.toolbar.btn_italic, self.toolbar.btn_h1,
            self.toolbar.btn_bullet, self.toolbar.btn_checklist, self.toolbar.btn_code
        ):
            self.assertEqual(btn.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_toolbar_clicks_invocan_formato(self):
        self.editor.setPlainText("prueba toolbar")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.toolbar.btn_bold.click()
        self.assertEqual(self.editor.toPlainText(), "**prueba** toolbar")

        # Cita
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(len(self.editor.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.toolbar.btn_quote.click()
        self.assertEqual(self.editor.toPlainText(), "> **prueba** toolbar")

    def test_markdown_highlighter_reglas_y_bloques(self):
        highlighter = self.editor.highlighter
        self.assertIsNotNone(highlighter)

        self.editor.setPlainText(
            "# Encabezado Principal\n"
            "Texto con **negrita** y *cursiva* y `codigo_inline`\n"
            "- [x] Tarea terminada\n"
            "- [ ] Tarea pendiente\n"
            "> Cita importante\n"
            "```\n"
            "linea dentro de bloque\n"
            "```\n"
        )

        doc = self.editor.document()
        block_h1 = doc.findBlockByLineNumber(0)
        self.assertTrue(highlighter.RE_HEADING.match(block_h1.text()))

        block_code_fence = doc.findBlockByLineNumber(5)
        self.assertTrue(block_code_fence.text().startswith("```"))

        # Cambio de tema no lanza excepciones
        highlighter.set_theme("light")
        self.assertEqual(highlighter.theme, "light")
        highlighter.set_theme("dark")
        self.assertEqual(highlighter.theme, "dark")


class TestFase5GUIControles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher_notes = patch.object(config, "NOTES_DIR", Path(self.temp_dir.name))
        self.patcher_trash = patch.object(config, "TRASH_DIR", Path(self.temp_dir.name) / ".papelera")
        self.patcher_notes.start()
        self.patcher_trash.start()
        config.asegurar_directorio()

        self.gui = NerdNotesApp()
        self.gui.show()

    def tearDown(self):
        self.gui.close()
        self.patcher_notes.stop()
        self.patcher_trash.stop()
        self.temp_dir.cleanup()

    def test_boton_pin_en_header_editor(self):
        self.assertTrue(hasattr(self.gui, "btn_pin"))
        ruta = storage.crear_nota("Nota Para Fijar", "Contenido de la nota")
        self.gui.cargar_lista_notas(seleccionar_ruta=ruta)
        self.gui.cargar_nota_por_ruta(ruta)

        self.assertTrue(self.gui.btn_pin.isEnabled())
        self.assertFalse(self.gui.btn_pin.isChecked())
        self.assertEqual(self.gui.btn_pin.toolTip(), "Fijar nota arriba")

        # Clic en el botón pin
        self.gui.btn_pin.click()
        self.assertTrue(self.gui.btn_pin.isChecked())
        self.assertTrue(storage.es_nota_fijada(ruta.name))
        self.assertEqual(self.gui.btn_pin.toolTip(), "Desfijar nota")

        # Clic de nuevo para desfijar
        self.gui.btn_pin.click()
        self.assertFalse(self.gui.btn_pin.isChecked())
        self.assertFalse(storage.es_nota_fijada(ruta.name))

    def test_gestion_rapida_etiquetas_y_metadatos(self):
        self.assertTrue(hasattr(self.gui, "btn_etiquetas"))
        ruta = storage.crear_nota("Nota Etiquetas Rapidas", "Contenido base", etiquetas=["alpha"])
        self.gui.cargar_lista_notas(seleccionar_ruta=ruta)
        self.gui.cargar_nota_por_ruta(ruta)

        self.assertTrue(self.gui.btn_etiquetas.isEnabled())
        self.assertTrue(self.gui.btn_etiquetas.isVisible())
        self.assertIn("alpha", self.gui.lbl_metadata_nota.text())

        # Simular edición de etiquetas desde el diálogo rápido
        with patch("main_gui.EditarEtiquetasDialog") as mock_dlg:
            mock_dlg.return_value.exec.return_value = 1  # Accepted
            mock_dlg.return_value.obtener_etiquetas.return_value = ["alpha", "beta_rapida"]
            self.gui.btn_etiquetas.click()

            self.assertIn("beta_rapida", self.gui.editor_texto.toPlainText())
            self.assertIn("beta_rapida", self.gui.lbl_metadata_nota.text())

    def test_toolbar_desactivada_en_vista_previa(self):
        ruta = storage.crear_nota("Nota Preview Toolbar", "Contenido")
        self.gui.cargar_lista_notas(seleccionar_ruta=ruta)
        self.gui.cargar_nota_por_ruta(ruta)

        self.assertTrue(self.gui.toolbar_formato.isVisible())
        self.gui.alternar_vista_previa()
        self.assertFalse(self.gui.toolbar_formato.isVisible())
        self.gui.alternar_vista_previa()
        self.assertTrue(self.gui.toolbar_formato.isVisible())

    def test_compatibilidad_sin_pyqt6(self):
        # Asegurar que editor y highlighter se pueden importar sin PyQt6
        cmd = (
            "./.venv/bin/python -c \""
            "import sys; sys.modules['PyQt6']=None; sys.modules['PyQt6.QtWidgets']=None; "
            "sys.modules['PyQt6.QtCore']=None; sys.modules['PyQt6.QtGui']=None; "
            "import editor; from ui.markdown_highlighter import MarkdownHighlighter; "
            "print('OK Headless')\""
        )
        res = os.system(cmd)
        self.assertEqual(res, 0)


if __name__ == "__main__":
    unittest.main()
