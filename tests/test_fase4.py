import tempfile
import unittest
from pathlib import Path

import config
import storage
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem, QLineEdit
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QPainter, QImage
from main_gui import NerdNotesApp
from editor import NoteEditor, NoteTitleEdit
from ui.note_delegate import NoteCardDelegate
from ui.notes_model import NotesListModel, NotesFilterProxyModel, NoteItem

app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

class TestFase4(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        self.original_config_file = config.CONFIG_FILE

        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.CONFIG_FILE = config.NOTES_DIR / ".config.json"
        config.asegurar_directorio()

        storage.crear_nota(
            "Nota Estilo Visual",
            "Contenido con margen amplio e interlineado proporcional.",
            etiquetas=["ui", "design"]
        )
        self.gui = NerdNotesApp()

    def tearDown(self):
        self.gui.modificado = False
        self.gui.close()
        self.gui.deleteLater()
        app.processEvents()
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        config.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def test_jerarquia_qss_y_estilos_paneles(self):
        dark_qss_path = Path("resources/dark.qss")
        self.assertTrue(dark_qss_path.exists())
        qss_text = dark_qss_path.read_text(encoding="utf-8")

        # 1. Jerarquía de fondos de tres niveles de profundidad
        self.assertIn("#widget_sidebar", qss_text)
        self.assertIn("#widget_lista", qss_text)
        self.assertIn("#widget_editor", qss_text)
        self.assertIn("#121214", qss_text)
        self.assertIn("#161618", qss_text)
        self.assertIn("#1a1a1e", qss_text)

        # 2. QSplitter handle de 1px en #26262a
        self.assertIn("QSplitter::handle", qss_text)
        self.assertIn("#26262a", qss_text)

        # 3. Franja superior uniforme de 44px
        self.assertIn("#header_panel", qss_text)
        self.assertIn("border-bottom: 1px solid", qss_text)

        # 4. Campo de título grande H1 sin bordes
        self.assertIn("QLineEdit#editor_titulo", qss_text)
        self.assertIn("font-size: 22px", qss_text)

        # 5. Inputs y ComboBox homogeneizados (32px, border-radius 6px)
        self.assertIn("min-height: 32px", qss_text)
        self.assertIn("max-height: 32px", qss_text)
        self.assertIn("border-radius: 6px", qss_text)

    def test_editor_margen_e_interlineado(self):
        # 1. Document margin generoso de 24px
        self.assertEqual(self.gui.editor_texto.document().documentMargin(), 24.0)

        # 2. Interlineado proporcional adecuado (140% - 160%)
        cursor = self.gui.editor_texto.textCursor()
        self.assertIn(cursor.blockFormat().lineHeight(), (140.0, 160.0))

        # 3. Cargar nuevo texto preserva documentMargin e interlineado
        self.gui.editor_texto.cargar_texto("Nueva línea 1\nNueva línea 2")
        self.assertEqual(self.gui.editor_texto.document().documentMargin(), 24.0)
        self.assertIn(self.gui.editor_texto.textCursor().blockFormat().lineHeight(), (140.0, 160.0))

        # 4. Instancia standalone de NoteEditor también aplica márgenes e interlineado
        standalone = NoteEditor()
        self.assertEqual(standalone.document().documentMargin(), 24.0)
        self.assertIn(standalone.textCursor().blockFormat().lineHeight(), (140.0, 160.0))

    def test_note_delegate_render_y_chips(self):
        delegate = NoteCardDelegate()
        self.assertEqual(delegate.tema, "dark")

        # Probar tamaño con etiquetas vs sin etiquetas
        item_con_tags = NoteItem(
            ruta=Path("test1.txt"),
            titulo="Con Tags",
            fecha="2026-11-05",
            vista_previa="Texto",
            etiquetas=["tag1", "tag2"]
        )
        item_sin_tags = NoteItem(
            ruta=Path("test2.txt"),
            titulo="Sin Tags",
            fecha="2026-11-05",
            vista_previa="Texto",
            etiquetas=[]
        )

        model = NotesListModel([item_con_tags, item_sin_tags])
        idx_con_tags = model.index(0, 0)
        idx_sin_tags = model.index(1, 0)

        opt = QStyleOptionViewItem()
        opt.rect.setWidth(260)
        opt.rect.setHeight(100)

        hint_con_tags = delegate.sizeHint(opt, idx_con_tags)
        hint_sin_tags = delegate.sizeHint(opt, idx_sin_tags)
        self.assertGreater(hint_con_tags.height(), hint_sin_tags.height())

        # Probar pintado en canvas offscreen sin errores
        img = QImage(300, 100, QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        opt.rect.setRect(0, 0, 300, hint_con_tags.height())
        delegate.paint(painter, opt, idx_con_tags)
        delegate.paint(painter, opt, idx_sin_tags)
        painter.end()

    def test_main_gui_layout_y_alineacion(self):
        # 1. Splitter handle de 1px y colapsabilidad
        self.assertEqual(self.gui.splitter.handleWidth(), 1)
        self.assertTrue(self.gui.splitter.isCollapsible(0))
        self.assertFalse(self.gui.splitter.isCollapsible(1))
        self.assertFalse(self.gui.splitter.isCollapsible(2))

        # 2. Rango permitido de ancho para paneles laterales
        self.assertEqual(self.gui.widget_sidebar.minimumWidth(), 180)
        self.assertEqual(self.gui.widget_sidebar.maximumWidth(), 260)
        self.assertEqual(self.gui.widget_lista.minimumWidth(), 260)
        self.assertEqual(self.gui.widget_lista.maximumWidth(), 360)
        self.assertGreaterEqual(self.gui.widget_editor.minimumWidth(), 300)

        # 3. Horizonte uniforme de 44px en las cabeceras
        self.assertEqual(self.gui.header_sidebar.height(), 44)
        self.assertEqual(self.gui.header_lista.height(), 44)
        self.assertEqual(self.gui.header_editor.height(), 44)

        # 4. Título H1 como QLineEdit editable y barra de metadatos sutil
        self.assertIsInstance(self.gui.lbl_titulo_actual, QLineEdit)
        self.assertIsInstance(self.gui.lbl_titulo_actual, NoteTitleEdit)
        self.assertTrue(hasattr(self.gui, "lbl_metadata_nota"))
        self.assertIn("ui", self.gui.lbl_metadata_nota.text())

    def test_edicion_titulo_en_editor_actualiza_nota(self):
        # La nota actual se titula "Nota Estilo Visual"
        self.assertEqual(self.gui.lbl_titulo_actual.text(), "Nota Estilo Visual")

        # Modificar el título en el QLineEdit
        self.gui.lbl_titulo_actual.setText("Titulo Modificado Inline")
        self.gui.lbl_titulo_actual.editingFinished.emit()

        # El archivo en disco debe haberse renombrado
        self.assertTrue(self.gui.ruta_actual.exists())
        self.assertIn("Titulo_Modificado_Inline", self.gui.ruta_actual.name)
        self.assertEqual(self.gui.lbl_titulo_actual.text(), "Titulo Modificado Inline")


if __name__ == "__main__":
    unittest.main()
