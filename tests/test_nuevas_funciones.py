import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import config
import storage
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QKeyEvent, QTextCursor
from PyQt6.QtCore import Qt, QEvent, QTimer
from main_gui import NerdNotesApp
from ui.tag_dialogs import MultiCompleterLineEdit, EditarEtiquetasDialog, NuevaNotaDialog

app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

class TestNuevasFunciones(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        self.original_config_file = config.CONFIG_FILE

        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.CONFIG_FILE = config.NOTES_DIR / ".config.json"
        config.asegurar_directorio()

        self.nota1_path = storage.crear_nota(
            "Nota Base",
            "Texto inicial de prueba para formato.",
            etiquetas=["test", "general"]
        )
        self.gui = NerdNotesApp()
        self.gui.show()

    def tearDown(self):
        self.gui.modificado = False
        self.gui.close()
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        config.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    # --- 1. EDITAR ETIQUETAS Y CREAR NOTA CON ETIQUETAS ---
    def test_editar_etiquetas_dialogo_y_actualizacion(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        ruta = item0.data(Qt.ItemDataRole.UserRole)

        # Simular diálogo de edición de etiquetas
        with patch.object(EditarEtiquetasDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
             patch.object(EditarEtiquetasDialog, "obtener_etiquetas", return_value=["urgente", "proyecto"]):
            self.gui.editar_etiquetas_nota(ruta)

        contenido = self.gui.editor_texto.toPlainText()
        self.assertIn("Etiquetas: urgente, proyecto", contenido)
        self.assertEqual(storage.extraer_etiquetas(ruta), ["urgente", "proyecto"])

        # Verificar que la sidebar de etiquetas se refrescó
        tags_sidebar = [self.gui.tags_list.item(i).text() for i in range(self.gui.tags_list.count())]
        self.assertIn("urgente", tags_sidebar)
        self.assertIn("proyecto", tags_sidebar)

    def test_crear_nota_con_campo_etiquetas(self):
        with patch.object(NuevaNotaDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
             patch.object(NuevaNotaDialog, "obtener_datos", return_value=("Nota Con Tags", ["react", "frontend"])):
            self.gui.crear_nueva_nota()

        self.assertEqual(self.gui.lbl_titulo_actual.text(), "Nota Con Tags")
        contenido = self.gui.editor_texto.toPlainText()
        self.assertIn("Etiquetas: react, frontend", contenido)

    def test_refrescar_sidebar_al_guardar_cambio_etiquetas(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        
        # El usuario edita directamente la línea de etiquetas en el editor
        lineas = self.gui.editor_texto.toPlainText().splitlines()
        for i, l in enumerate(lineas):
            if l.startswith("Etiquetas:"):
                lineas[i] = "Etiquetas: nueva_etiqueta_manual"
        self.gui.editor_texto.setPlainText("\n".join(lineas))
        
        self.gui.guardar_nota(silencioso=True)
        tags_sidebar = [self.gui.tags_list.item(i).text() for i in range(self.gui.tags_list.count())]
        self.assertIn("nueva_etiqueta_manual", tags_sidebar)

    # --- 2. FORMATO MARKDOWN EN EL EDITOR ---
    def test_formato_markdown_negrita_y_cursiva(self):
        self.gui.editor_texto.setPlainText("palabra clave para formatear")
        
        # Seleccionar 'clave'
        cursor = self.gui.editor_texto.textCursor()
        cursor.setPosition(8)
        cursor.setPosition(13, QTextCursor.MoveMode.KeepAnchor)
        self.gui.editor_texto.setTextCursor(cursor)

        # Aplicar Negrita
        self.gui.aplicar_formato_markdown("negrita")
        self.assertIn("**clave**", self.gui.editor_texto.toPlainText())

        # Deshacer (Undo) debe volver al texto original en un solo paso
        self.gui.editor_texto.document().undo()
        self.assertEqual(self.gui.editor_texto.toPlainText(), "palabra clave para formatear")

        # Seleccionar 'palabra' y aplicar Cursiva
        cursor = self.gui.editor_texto.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(7, QTextCursor.MoveMode.KeepAnchor)
        self.gui.editor_texto.setTextCursor(cursor)

        self.gui.aplicar_formato_markdown("cursiva")
        self.assertIn("*palabra*", self.gui.editor_texto.toPlainText())

    def test_formato_markdown_encabezados(self):
        self.gui.editor_texto.setPlainText("Mi Título de Sección")
        cursor = self.gui.editor_texto.textCursor()
        cursor.setPosition(5)
        self.gui.editor_texto.setTextCursor(cursor)

        # H1
        self.gui.aplicar_formato_markdown("h1")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "# Mi Título de Sección")

        # H2 reemplaza H1
        self.gui.aplicar_formato_markdown("h2")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "## Mi Título de Sección")

        # H3 reemplaza H2
        self.gui.aplicar_formato_markdown("h3")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "### Mi Título de Sección")

    def test_formato_markdown_lista_y_checklist(self):
        self.gui.editor_texto.setPlainText("Elemento 1\nElemento 2")
        cursor = self.gui.editor_texto.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(len(self.gui.editor_texto.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        self.gui.editor_texto.setTextCursor(cursor)

        # Lista
        self.gui.aplicar_formato_markdown("lista")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "- Elemento 1\n- Elemento 2")

        # Checklist (convierte los elementos de lista en checklist)
        self.gui.aplicar_formato_markdown("checklist")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "- [ ] Elemento 1\n- [ ] Elemento 2")

        # Toggle checklist (lo quita)
        self.gui.aplicar_formato_markdown("checklist")
        self.assertEqual(self.gui.editor_texto.toPlainText(), "Elemento 1\nElemento 2")

    # --- 3. IMPORTAR .TXT / .MD ---
    def test_importar_archivo_externo(self):
        archivo_externo = Path(self.temp_dir.name) / "documento_externo.md"
        archivo_externo.write_text("Contenido importado de un archivo externo.", encoding="utf-8")

        nueva_ruta = self.gui.importar_archivo(archivo_externo)
        self.assertIsNotNone(nueva_ruta)
        self.assertTrue(nueva_ruta.exists())
        self.assertEqual(self.gui.lbl_titulo_actual.text(), "documento_externo")
        self.assertIn("Contenido importado de un archivo externo", self.gui.editor_texto.toPlainText())

        # No debe sobrescribir si se importa de nuevo
        nueva_ruta_2 = self.gui.importar_archivo(archivo_externo)
        self.assertNotEqual(nueva_ruta, nueva_ruta_2)
        self.assertTrue(nueva_ruta_2.name.endswith("_2.txt"))

    # --- 4. DUPLICAR NOTA ---
    def test_duplicar_nota(self):
        item0 = self.gui.lista_notas.item(0)
        ruta_orig = item0.data(Qt.ItemDataRole.UserRole)

        ruta_duplicada = self.gui.duplicar_nota(ruta_orig)
        self.assertIsNotNone(ruta_duplicada)
        self.assertTrue(ruta_duplicada.exists())
        self.assertIn("copia", ruta_duplicada.name)
        self.assertEqual(self.gui.lbl_titulo_actual.text(), "Nota Base (copia)")
        self.assertIn("Texto inicial de prueba para formato", self.gui.editor_texto.toPlainText())

    # --- 5. DESHACER AL MOVER A PAPELERA ---
    def test_deshacer_mover_a_papelera(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        ruta = item0.data(Qt.ItemDataRole.UserRole)

        # Mover a papelera
        self.gui.eliminar_nota_seleccionada()
        self.assertFalse(ruta.exists())
        self.assertFalse(self.gui._widget_deshacer.isHidden())
        self.assertTrue(self.gui.timer_deshacer.isActive())

        # Presionar Deshacer
        self.gui._deshacer_mover_a_papelera()
        self.assertTrue(ruta.exists())
        self.assertTrue(self.gui._widget_deshacer.isHidden())
        self.assertFalse(self.gui.timer_deshacer.isActive())
        self.assertEqual(self.gui.lista_notas.count(), 1)

    # --- 6. QFILESYSTEMWATCHER SOBRE NOTES_DIR ---
    def test_file_watcher_no_toca_editor_si_hay_cambios(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        # Modificar texto local en editor
        self.gui.editor_texto.setPlainText("Texto sin guardar en GUI")
        self.assertTrue(self.gui.modificado)

        # Simular cambio externo mediante CLI
        nueva_nota_cli = storage.crear_nota("Nota Creada Externamente", "Contenido externo")

        # Disparar watcher
        self.gui._al_disparar_watcher()

        # El editor NO debe haberse sobreescrito
        self.assertEqual(self.gui.editor_texto.toPlainText(), "Texto sin guardar en GUI")
        self.assertTrue(self.gui.modificado)

    def test_file_watcher_refresca_lista_si_no_hay_cambios(self):
        self.assertFalse(self.gui.modificado)
        cant_inicial = self.gui.lista_notas.count()

        # Crear nota externamente
        storage.crear_nota("Nota CLI", "Contenido CLI")

        # Disparar watcher
        self.gui._al_disparar_watcher()
        self.assertEqual(self.gui.lista_notas.count(), cant_inicial + 1)

    # --- 7. ESC EN EL BUSCADOR ---
    def test_esc_en_buscador_limpia_y_enfoca_lista(self):
        self.gui.buscador.setText("busqueda activa")
        self.gui.buscador.setFocus()
        self.assertEqual(self.gui.buscador.text(), "busqueda activa")

        # Simular tecla Escape en el buscador
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.gui.eventFilter(self.gui.buscador, event)

        self.assertEqual(self.gui.buscador.text(), "")
        self.assertEqual(self.gui.focusWidget(), self.gui.lista_notas)

    # --- 8. ESTADO DEL EDITOR, PLACEHOLDER Y SPLITTER ---
    def test_editor_deshabilitado_con_placeholder_si_no_hay_notas(self):
        self.gui.buscador.setText("consulta_inexistente_xyz_123")
        self.assertEqual(self.gui.lista_notas.count(), 0)
        self.gui._mostrar_estado_sin_nota()

        self.assertFalse(self.gui.editor_texto.isEnabled())
        self.assertTrue(self.gui.editor_texto.isReadOnly())
        self.assertIn("Selecciona una nota", self.gui.editor_texto.placeholderText())
        self.assertIsNone(self.gui.ruta_actual)

    def test_editor_habilitado_y_editable_al_crear_nota(self):
        with patch("ui.tag_dialogs.NuevaNotaDialog.exec", return_value=1), \
             patch("ui.tag_dialogs.NuevaNotaDialog.obtener_datos", return_value=("Nota Editable", ["test"])):
            self.gui.crear_nueva_nota()

        self.assertTrue(self.gui.editor_texto.isEnabled())
        self.assertFalse(self.gui.editor_texto.isReadOnly())
        self.assertEqual(self.gui.editor_texto.placeholderText(), "")
        self.assertEqual(
            self.gui.editor_texto.textCursor().position(),
            len(self.gui.editor_texto.toPlainText())
        )

    def test_editor_splitter_no_colapsa_a_cero(self):
        sizes = self.gui.splitter.sizes()
        self.assertEqual(len(sizes), 3)
        self.assertGreaterEqual(sizes[2], 200)
        self.assertGreaterEqual(sizes[1], 150)
        self.assertFalse(self.gui.splitter.isCollapsible(2))

    def test_editor_solo_lectura_en_papelera_y_editable_en_todas(self):
        self.gui.nav_list.setCurrentRow(2)  # Papelera
        self.assertEqual(self.gui.filtro_categoria, "papelera")
        # Si no hay notas en papelera, editor deshabilitado
        self.assertFalse(self.gui.editor_texto.isEnabled())

        self.gui.nav_list.setCurrentRow(0)  # Todas
        self.assertEqual(self.gui.filtro_categoria, "todas")
        self.assertTrue(self.gui.editor_texto.isEnabled())
        self.assertFalse(self.gui.editor_texto.isReadOnly())


if __name__ == "__main__":
    unittest.main()
