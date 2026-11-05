import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QEasingCurve, QModelIndex
from PyQt6.QtGui import QTextBlockFormat, QFont, QImage, QPainter

import config
import storage
from editor import NoteEditor, NoteTitleEdit, NoteFormatToolbar, NoteEditorCanvas
from ui.note_delegate import NoteCardDelegate
from ui.notes_model import NotesListModel, NoteItem
from main_gui import NerdNotesApp

app = QApplication.instance() or QApplication(sys.argv)


class TestFase6TipografiaYCanvas(unittest.TestCase):
    def test_qss_tipografia_y_escala_1080p(self):
        dark_qss = Path("resources/dark.qss").read_text(encoding="utf-8")
        light_qss = Path("resources/light.qss").read_text(encoding="utf-8")

        pila_esperada = "'Inter', 'Noto Sans', 'Segoe UI', 'Ubuntu', sans-serif"
        self.assertIn(pila_esperada, dark_qss)
        self.assertIn(pila_esperada, light_qss)

        # Título de la nota: 22px, font-weight 600
        self.assertIn("font-size: 22px", dark_qss)
        self.assertIn("font-weight: 600", dark_qss)
        self.assertIn("font-size: 22px", light_qss)
        self.assertIn("font-weight: 600", light_qss)

        # Editor de texto: 15px
        self.assertIn("font-size: 15px", dark_qss)
        self.assertIn("font-size: 15px", light_qss)

        # Metadatos y contador: 12px, #71717a
        self.assertIn("font-size: 12px", dark_qss)
        self.assertIn("#71717a", dark_qss)

    def test_editor_interlineado_160_y_titulo_22px(self):
        editor = NoteEditor()
        editor.setPlainText("Línea 1\nLínea 2")
        cursor = editor.textCursor()
        # line-height 1.6 (160%)
        self.assertEqual(cursor.blockFormat().lineHeight(), 160.0)

        title = NoteTitleEdit()
        font = title.font()
        self.assertEqual(font.pixelSize(), 22)
        self.assertEqual(font.weight(), QFont.Weight.DemiBold.value)

    def test_canvas_centrado_confinado(self):
        canvas = NoteEditorCanvas(max_width=800)
        self.assertGreaterEqual(canvas.maximumWidth(), 760)
        self.assertLessEqual(canvas.maximumWidth(), 840)
        self.assertEqual(canvas.objectName(), "container_documento")


class TestFase6ToolbarPro(unittest.TestCase):
    def setUp(self):
        self.editor = NoteEditor()
        self.toolbar = NoteFormatToolbar(self.editor)

    def test_toolbar_dimensiones_y_estilos_botones(self):
        botones = [
            self.toolbar.btn_bold, self.toolbar.btn_italic, self.toolbar.btn_h1,
            self.toolbar.btn_h2, self.toolbar.btn_bullet, self.toolbar.btn_checklist,
            self.toolbar.btn_quote, self.toolbar.btn_code, self.toolbar.btn_link
        ]
        for btn in botones:
            self.assertEqual(btn.height(), 28)
            self.assertGreaterEqual(btn.minimumWidth(), 28)
            self.assertTrue(len(btn.toolTip()) > 0)

        # Botones con atajos asignados
        self.assertIn("Ctrl+B", self.toolbar.btn_bold.toolTip())
        self.assertIn("Ctrl+I", self.toolbar.btn_italic.toolTip())
        self.assertIn("Ctrl+K", self.toolbar.btn_link.toolTip())

        dark_qss = Path("resources/dark.qss").read_text(encoding="utf-8")
        self.assertIn("border-radius: 5px", dark_qss)
        self.assertIn("height: 14px", dark_qss)


class TestFase6AnimacionesYDelegate(unittest.TestCase):
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

    def test_animacion_sidebar_180ms_inoutquad(self):
        self.gui.anim_sidebar = None
        self.gui.animar_sidebar()

        self.assertIsNotNone(self.gui.anim_sidebar)
        self.assertEqual(self.gui.anim_sidebar.duration(), 180)
        self.assertEqual(self.gui.anim_sidebar.easingCurve().type(), QEasingCurve.Type.InOutQuad)
        self.assertEqual(self.gui.anim_sidebar.propertyName(), b"maximumWidth")

    def test_animacion_feedback_guardado_fade_in(self):
        self.gui.lbl_estado_guardado.setText("• Modificado")
        self.gui._actualizar_indicador_dirty(False)

        self.assertTrue(hasattr(self.gui, "anim_guardado"))
        self.assertIsNotNone(self.gui.anim_guardado)
        self.assertEqual(self.gui.anim_guardado.duration(), 200)
        self.assertEqual(self.gui.anim_guardado.easingCurve().type(), QEasingCurve.Type.InOutQuad)
        self.assertEqual(self.gui.anim_guardado.startValue(), 0.2)
        self.assertEqual(self.gui.anim_guardado.endValue(), 1.0)
        self.assertIsInstance(self.gui.lbl_estado_guardado.graphicsEffect(), QGraphicsOpacityEffect)

    def test_note_delegate_padding_y_alto_contraste(self):
        delegate = NoteCardDelegate()
        opt = QStyleOptionViewItem()
        opt.rect.setWidth(260)
        opt.rect.setHeight(100)

        model = NotesListModel()
        item1 = NoteItem(
            ruta=Path(self.temp_dir.name) / "nota1.txt",
            titulo="Nota 1",
            fecha="05/11",
            vista_previa="Extracto de prueba legible",
            etiquetas=["test", "fase6"]
        )
        item2 = NoteItem(
            ruta=Path(self.temp_dir.name) / "nota2.txt",
            titulo="Nota 2",
            fecha="05/11",
            vista_previa="Sin etiquetas",
            etiquetas=[]
        )
        model.set_items([item1, item2])

        idx_con_tags = model.index(0, 0)
        idx_sin_tags = model.index(1, 0)

        # Padding vertical amplio: tarjetas respiran con altura >= 80px (con tags) y >= 70px (sin tags)
        hint_con = delegate.sizeHint(opt, idx_con_tags)
        hint_sin = delegate.sizeHint(opt, idx_sin_tags)
        self.assertGreaterEqual(hint_con.height(), 80)
        self.assertGreaterEqual(hint_sin.height(), 70)
        self.assertGreater(hint_con.height(), hint_sin.height())

        # Pintado sin errores con contraste nítido
        img = QImage(300, hint_con.height(), QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        opt.rect.setRect(0, 0, 300, hint_con.height())
        delegate.paint(painter, opt, idx_con_tags)
        painter.end()


if __name__ == "__main__":
    unittest.main()
