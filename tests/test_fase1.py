import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import config
import storage
import editor
import core
import main

from PyQt6.QtWidgets import QApplication, QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt
from main_gui import NerdNotesApp
from ui.notes_model import NoteRoles

app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.asegurar_directorio()

    def tearDown(self):
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        self.temp_dir.cleanup()

    def test_evitar_sobrescritura_con_sufijos(self):
        r1 = storage.crear_nota("Mi Idea")
        self.assertTrue(r1.exists())
        self.assertTrue(r1.name.endswith("_Mi_Idea.txt"))

        r2 = storage.crear_nota("Mi Idea")
        self.assertTrue(r2.exists())
        self.assertTrue(r2.name.endswith("_Mi_Idea_2.txt"))
        self.assertNotEqual(r1, r2)

        r3 = storage.crear_nota("Mi Idea")
        self.assertTrue(r3.exists())
        self.assertTrue(r3.name.endswith("_Mi_Idea_3.txt"))

    def test_sanear_titulo_y_preservar_original_en_contenido(self):
        titulo_raro = "Proyecto: A/B *Prueba* <1> | \"Final\"?"
        r = storage.crear_nota(titulo_raro)
        self.assertTrue(r.exists())
        # El nombre del archivo no debe tener caracteres prohibidos
        for prohibido in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            self.assertNotIn(prohibido, r.name)

        # La primera línea debe conservar el título original exacto
        lineas = r.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lineas[0], f"# {titulo_raro}")

    def test_sanitizar_nombre_y_prevencion_salto_ruta(self):
        # 1. Caracteres inválidos / peligrosos
        nombre_invalido = 'nota/con\\slash:dos_puntos*asterisco?pregunta"comillas<menor>mayor|pipe\0null'
        saneado = storage.sanitizar_nombre(nombre_invalido)
        for prohibido in ['/', '\\', '\0', ':', '*', '?', '"', '<', '>', '|']:
            self.assertNotIn(prohibido, saneado)

        # 2. Saltos de directorio
        self.assertNotIn("..", storage.sanitizar_nombre("../../etc/passwd"))
        self.assertEqual(storage.sanitizar_nombre(".."), "nota_sin_titulo")
        self.assertEqual(storage.sanitizar_nombre("../"), "nota_sin_titulo")
        self.assertEqual(storage.sanitizar_nombre("...."), "nota_sin_titulo")

        # 3. Nombres vacíos o con solo espacios / caracteres inválidos
        self.assertEqual(storage.sanitizar_nombre(""), "nota_sin_titulo")
        self.assertEqual(storage.sanitizar_nombre("   "), "nota_sin_titulo")
        self.assertEqual(storage.sanitizar_nombre("///:::***"), "nota_sin_titulo")
        self.assertEqual(storage.sanitizar_nombre(None), "nota_sin_titulo")

        # 4. Longitud máxima
        nombre_largo = "a" * 200
        saneado_largo = storage.sanitizar_nombre(nombre_largo)
        self.assertLessEqual(len(saneado_largo), 100)

        # 5. Crear nota con intento de salto de ruta debe quedar confinada dentro de NOTES_DIR
        r = storage.crear_nota("../../intento_escape")
        self.assertTrue(r.exists())
        self.assertEqual(r.parent.resolve(), config.NOTES_DIR.resolve())

    def test_escritura_atomica_reemplazo_y_limpieza_error(self):
        # 1. Escritura y reemplazo exitoso
        archivo = config.NOTES_DIR / "nota_atomica.txt"
        archivo.write_text("Contenido inicial original", encoding="utf-8")

        nuevo_contenido = "# Título Actualizado\nNuevo contenido seguro."
        exito = storage.guardar_nota(archivo, nuevo_contenido)
        self.assertTrue(exito)
        self.assertEqual(archivo.read_text(encoding="utf-8"), nuevo_contenido)

        # Verificar que no quedaron temporales residuales
        archivos_temp = [f for f in config.NOTES_DIR.iterdir() if f.name.startswith("tmp") or f.name.endswith(".tmp")]
        self.assertEqual(len(archivos_temp), 0)

        # 2. Manejo de excepciones: simular fallo durante os.fsync
        with patch("os.fsync", side_effect=OSError("Fallo de I/O simulado")):
            fallo = storage.guardar_nota(archivo, "Contenido que debe fallar")
            self.assertFalse(fallo)

        # El archivo original debe permanecer intacto
        self.assertEqual(archivo.read_text(encoding="utf-8"), nuevo_contenido)

        # El archivo temporal debe haberse limpiado
        archivos_temp = [f for f in config.NOTES_DIR.iterdir() if f.name.startswith("tmp") or f.name.endswith(".tmp")]
        self.assertEqual(len(archivos_temp), 0)

    def test_papelera_evita_colisiones_con_mismo_nombre(self):
        # 1. Crear primera nota y moverla a la papelera
        r1 = storage.crear_nota("Nota Colision", "Contenido primera version")
        self.assertTrue(r1.exists())
        nombre_original = r1.name

        p1 = storage.mover_a_papelera(r1)
        self.assertIsNotNone(p1)
        self.assertTrue(p1.exists())
        self.assertFalse(r1.exists())
        self.assertEqual(p1.name, nombre_original)

        # 2. Crear segunda nota con el mismo título/nombre (al no existir en NOTES_DIR tomará el mismo nombre)
        r2 = storage.crear_nota("Nota Colision", "Contenido segunda version")
        self.assertTrue(r2.exists())
        self.assertEqual(r2.name, nombre_original)

        # 3. Mover la segunda nota a la papelera: no debe sobrescribir p1
        p2 = storage.mover_a_papelera(r2)
        self.assertIsNotNone(p2)
        self.assertTrue(p2.exists())
        self.assertFalse(r2.exists())

        # 4. Ambos archivos deben coexistir con rutas distintas y contenido íntegro
        self.assertNotEqual(p1, p2)
        self.assertTrue(p1.exists())
        self.assertTrue(p2.exists())
        self.assertIn("Contenido primera version", p1.read_text(encoding="utf-8"))
        self.assertIn("Contenido segunda version", p2.read_text(encoding="utf-8"))

        # La papelera debe listar al menos ambos archivos
        papelera_items = storage.listar_papelera()
        self.assertIn(p1, papelera_items)
        self.assertIn(p2, papelera_items)

    def test_obtener_metadatos_preserva_guiones_bajos(self):
        r = storage.crear_nota("mi_variable_privada")
        titulo, fecha = storage.obtener_metadatos(r)
        self.assertEqual(titulo, "mi_variable_privada")

    def test_obtener_metadatos_fallback(self):
        # Archivo sin encabezado '#'
        archivo = config.NOTES_DIR / "2026-10-26_sin_cabecera.txt"
        archivo.write_text("Contenido simple sin encabezado markdown", encoding="utf-8")
        titulo, fecha = storage.obtener_metadatos(archivo)
        self.assertEqual(titulo, "sin cabecera")
        self.assertEqual(fecha, "2026-10-26")

    def test_manejo_errores_archivos_inexistentes(self):
        ruta_falsa = config.NOTES_DIR / "no_existe.txt"
        self.assertEqual(storage.leer_nota(ruta_falsa), "")
        self.assertFalse(storage.eliminar_nota(ruta_falsa))


class TestEditor(unittest.TestCase):
    @patch("subprocess.call")
    def test_fallback_editor(self, mock_subprocess):
        # Primer intento (DEFAULT_EDITOR) lanza FileNotFoundError, nano tiene éxito
        def side_effect(cmd):
            if cmd[0] == config.DEFAULT_EDITOR:
                raise FileNotFoundError("not found")
            return 0
        mock_subprocess.side_effect = side_effect

        p = Path("/tmp/fake.txt")
        res = editor.abrir_editor(p)
        self.assertTrue(res)
        # Verificamos que intentó con DEFAULT_EDITOR y luego con nano
        self.assertEqual(mock_subprocess.call_count, 2)

    @patch("subprocess.call", side_effect=FileNotFoundError("not found"))
    def test_ningun_editor_disponible(self, mock_subprocess):
        p = Path("/tmp/fake.txt")
        res = editor.abrir_editor(p)
        self.assertFalse(res)


class TestCoreYMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        config.NOTES_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        config.NOTES_DIR = self.original_notes_dir
        self.temp_dir.cleanup()

    @patch("builtins.print")
    def test_mostrar_nota(self, mock_print):
        r = storage.crear_nota("Nota Test", "Contenido de prueba")
        core.mostrar_nota(1)
        mock_print.assert_any_call("\n" + "=" * 60)

    @patch("sys.argv", ["main.py", "version"])
    @patch("builtins.print")
    def test_version_texto(self, mock_print):
        main.main()
        mock_print.assert_any_call("Hecho con ❤️ para terminales")


class TestGUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        config.NOTES_DIR = Path(self.temp_dir.name)
        storage.crear_nota("Nota 1", "Contenido 1")
        storage.crear_nota("Nota 2", "Contenido 2")
        self.gui = NerdNotesApp()

    def tearDown(self):
        self.gui.modificado = False
        self.gui.close()
        config.NOTES_DIR = self.original_notes_dir
        self.temp_dir.cleanup()

    def test_ensamblado_unico(self):
        # Solo debe haber una lista y los botones correspondientes
        self.assertEqual(self.gui.lista_notas.count(), 2)

    def test_item_data_user_role(self):
        # Cada item debe guardar un objeto Path en Qt.ItemDataRole.UserRole
        item = self.gui.lista_notas.item(0)
        ruta = item.data(Qt.ItemDataRole.UserRole)
        self.assertIsInstance(ruta, Path)
        self.assertTrue(ruta.exists())

    def test_buscador_filtra_visibles(self):
        self.gui.buscador.setText("Nota 1")
        self.gui.filtrar_notas("Nota 1")
        # Con QSortFilterProxyModel, solo la fila visible queda en el modelo filtrado
        self.assertEqual(self.gui.lista_notas.count(), 1)
        it = self.gui.lista_notas.item(0)
        self.assertIn("Nota 1", it.data(NoteRoles.TitleRole))

    def test_crear_nota_carga_contenido_y_selecciona(self):
        with patch("main_gui.QInputDialog.getText", return_value=("Nueva Nota Test", True)):
            self.gui.crear_nueva_nota()

        self.assertIn("Nueva Nota Test", self.gui.editor_texto.toPlainText())
        self.assertIn("# Nueva Nota Test", self.gui.editor_texto.toPlainText())
        # La nota actual debe estar seleccionada
        self.assertIsNotNone(self.gui.lista_notas.currentItem())
        self.assertEqual(
            self.gui.lista_notas.currentItem().data(Qt.ItemDataRole.UserRole),
            self.gui.ruta_actual
        )
        self.assertFalse(self.gui.modificado)

    def test_dirty_flag_al_editar(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        self.assertFalse(self.gui.modificado)

        self.gui.editor_texto.setPlainText("Texto modificado")
        self.assertTrue(self.gui.modificado)

        self.gui.guardar_nota()
        self.assertFalse(self.gui.modificado)

    def test_cambiar_nota_con_cambios_guarda_en_silencio(self):
        item0 = self.gui.lista_notas.item(0)
        item1 = self.gui.lista_notas.item(1)
        self.gui.lista_notas.setCurrentItem(item0)
        ruta0 = item0.data(Qt.ItemDataRole.UserRole)
        self.gui.editor_texto.setPlainText("Cambio a guardar silenciosamente")
        self.assertTrue(self.gui.modificado)

        # Al cambiar a item1, se guarda en silencio automáticamente sin diálogo de pregunta
        with patch("main_gui.QMessageBox.question") as mock_question:
            self.gui.lista_notas.setCurrentItem(item1)
            mock_question.assert_not_called()

        self.assertEqual(self.gui.lista_notas.currentItem(), item1)
        self.assertFalse(self.gui.modificado)
        self.assertEqual(ruta0.read_text(encoding="utf-8"), "Cambio a guardar silenciosamente")

    def test_cambiar_nota_con_fallo_guardado_avisa(self):
        item0 = self.gui.lista_notas.item(0)
        item1 = self.gui.lista_notas.item(1)
        self.gui.lista_notas.setCurrentItem(item0)
        self.gui.editor_texto.setPlainText("Texto con fallo")
        self.assertTrue(self.gui.modificado)

        with patch.object(self.gui, "guardar_nota", return_value=False), \
             patch("main_gui.QMessageBox.warning") as mock_warn:
            self.gui.lista_notas.setCurrentItem(item1)
            mock_warn.assert_called_once()

    def test_cerrar_ventana_con_cambios_guarda_en_silencio(self):
        from PyQt6.QtGui import QCloseEvent
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        ruta0 = item0.data(Qt.ItemDataRole.UserRole)
        self.gui.editor_texto.setPlainText("Guardar al cerrar")
        self.assertTrue(self.gui.modificado)

        event = QCloseEvent()
        with patch("main_gui.QMessageBox.question") as mock_q:
            self.gui.closeEvent(event)
            mock_q.assert_not_called()

        self.assertTrue(event.isAccepted())
        self.assertEqual(ruta0.read_text(encoding="utf-8"), "Guardar al cerrar")

    def test_cerrar_ventana_con_fallo_guardado_pregunta(self):
        from PyQt6.QtGui import QCloseEvent
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        self.gui.editor_texto.setPlainText("Fallo al cerrar")
        self.assertTrue(self.gui.modificado)

        event = QCloseEvent()
        with patch.object(self.gui, "guardar_nota", return_value=False), \
             patch("main_gui.QMessageBox.warning", return_value=QMessageBox.StandardButton.No):
            self.gui.closeEvent(event)

        self.assertFalse(event.isAccepted())

    def test_cerrar_ventana_sin_cambios(self):
        from PyQt6.QtGui import QCloseEvent
        self.assertFalse(self.gui.modificado)

        event = QCloseEvent()
        with patch("main_gui.QMessageBox.question") as mock_box:
            self.gui.closeEvent(event)
            mock_box.assert_not_called()

        self.assertTrue(event.isAccepted())



if __name__ == "__main__":
    unittest.main()
