import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import core
import storage
from services import config_service
from PyQt6.QtWidgets import QApplication, QListView, QSplitter
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QAbstractListModel, QSettings
from PyQt6.QtWidgets import QStyledItemDelegate
from main_gui import NerdNotesApp
from ui.notes_model import NotesListModel, NotesFilterProxyModel, NoteRoles, extraer_vista_previa
from ui.note_delegate import NoteCardDelegate
from services.icon_service import get_icon

app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

class TestFase3(unittest.TestCase):
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
            "Mi Nota", 
            "Primera línea de contenido relevante.\nSegunda línea más larga que no entra.", 
            etiquetas=["general"]
        )
        self.gui = NerdNotesApp()

    def tearDown(self):
        self.gui.modificado = False
        self.gui.close()
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        config.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def test_tres_paneles_con_qsplitter(self):
        # Debe haber un QSplitter con 3 widgets principales
        self.assertIsInstance(self.gui.splitter, QSplitter)
        self.assertEqual(self.gui.splitter.count(), 3)
        self.assertEqual(self.gui.splitter.widget(0), self.gui.widget_sidebar)
        self.assertEqual(self.gui.splitter.widget(1), self.gui.widget_lista)
        self.assertEqual(self.gui.splitter.widget(2), self.gui.widget_editor)

    def test_qlistview_con_modelo_y_delegate_propios(self):
        # lista_notas debe ser QListView
        self.assertIsInstance(self.gui.lista_notas, QListView)
        # Su modelo debe ser NotesFilterProxyModel con sourceModel NotesListModel
        self.assertIsInstance(self.gui.notes_model, NotesListModel)
        self.assertIsInstance(self.gui.notes_model, QAbstractListModel)
        self.assertIsInstance(self.gui.lista_notas.model(), NotesFilterProxyModel)
        # Su delegate debe heredar de QStyledItemDelegate
        self.assertIsInstance(self.gui.lista_notas.itemDelegate(), QStyledItemDelegate)
        self.assertIsInstance(self.gui.lista_notas.itemDelegate(), NoteCardDelegate)

    def test_modelo_extrae_vista_previa_unalinea(self):
        idx = self.gui.lista_notas.model().index(0, 0)
        titulo = self.gui.lista_notas.model().data(idx, NoteRoles.TitleRole)
        fecha = self.gui.lista_notas.model().data(idx, NoteRoles.DateRole)
        preview = self.gui.lista_notas.model().data(idx, NoteRoles.PreviewRole)

        self.assertEqual(titulo, "Mi Nota")
        self.assertIsNotNone(fecha)
        self.assertIn("Primera línea de contenido relevante", preview)

    def test_extraer_vista_previa_ignora_encabezados(self):
        contenido = "# Titulo\nFecha: 2026-10-26\nEtiquetas: test\n\nTexto útil aquí"
        preview = extraer_vista_previa(contenido)
        self.assertEqual(preview, "Texto útil aquí")

    def test_alternancia_temas_y_persistencia(self):
        tema_inicial = self.gui.tema_actual
        # Cambiar tema
        self.gui.cambiar_tema()
        nuevo_tema = self.gui.tema_actual
        self.assertNotEqual(tema_inicial, nuevo_tema)

        # Verificar persistencia en QSettings
        settings = QSettings("NerdNotes", "NerdNotesApp")
        self.assertEqual(settings.value("theme"), nuevo_tema)

        # Archivos de estilos deben existir
        dark_qss = Path("resources/dark.qss")
        light_qss = Path("resources/light.qss")
        self.assertTrue(dark_qss.exists())
        self.assertTrue(light_qss.exists())
        self.assertIn("QMainWindow", dark_qss.read_text())
        self.assertIn("QMainWindow", light_qss.read_text())

    def test_iconos_svg_cargan_correctamente(self):
        for nombre in ["new", "trash", "restore", "empty", "preview", "export", "theme", "sidebar"]:
            icon_dark = get_icon(nombre, "dark")
            self.assertFalse(icon_dark.isNull(), f"Icono '{nombre}' dark no debe ser nulo")
            icon_light = get_icon(nombre, "light")
            self.assertFalse(icon_light.isNull(), f"Icono '{nombre}' light no debe ser nulo")

    def test_botones_tienen_tooltip(self):
        self.assertTrue(bool(self.gui.btn_nueva.toolTip()))
        self.assertTrue(bool(self.gui.btn_tema.toolTip()))
        self.assertTrue(bool(self.gui.btn_toggle_sidebar.toolTip()))
        self.assertTrue(bool(self.gui.btn_preview.toolTip()))
        self.assertTrue(bool(self.gui.btn_exportar.toolTip()))
        self.assertTrue(bool(self.gui.btn_eliminar.toolTip()))

    def test_animacion_colapsar_sidebar(self):
        self.assertGreater(self.gui.widget_sidebar.width(), 0)
        self.gui.animar_sidebar()
        self.assertIsNotNone(self.gui.anim_sidebar)
        self.assertTrue(self.gui.anim_sidebar.duration() > 0)

    def test_atajos_sin_colisiones(self):
        # 1. btn_nueva no debe tener atajo asignado directamente (evita que Qt anule Ctrl+N)
        self.assertTrue(self.gui.btn_nueva.shortcut().isEmpty())

        # 2. Debe existir un QShortcut para Ctrl+N en la ventana principal
        shortcuts = self.gui.findChildren(QShortcut)
        ctrl_n_count = sum(1 for s in shortcuts if s.key().toString() == "Ctrl+N")
        self.assertEqual(ctrl_n_count, 1)

        # 3. Ctrl+\ para alternar la barra lateral (liberando Ctrl+B)
        ctrl_slash_count = sum(1 for s in shortcuts if s.key().toString() == "Ctrl+\\")
        self.assertEqual(ctrl_slash_count, 1)

        # 4. Delete debe estar limitado a la lista de notas (WidgetWithChildrenShortcut)
        list_shortcuts = self.gui.lista_notas.findChildren(QShortcut)
        del_shortcuts = [s for s in list_shortcuts if s.key().toString() == "Del"]
        self.assertEqual(len(del_shortcuts), 1)
        self.assertEqual(del_shortcuts[0].context(), Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def test_escritura_atomica_storage_y_config(self):
        # Probar almacenamiento atómico de notas
        nota_path = config.NOTES_DIR / "test_atomica.txt"
        nota_path.write_text("# Test\nContenido inicial", encoding="utf-8")
        
        exito = storage.guardar_nota(nota_path, "# Test\nContenido atómico modificado")
        self.assertTrue(exito)
        self.assertEqual(nota_path.read_text(encoding="utf-8"), "# Test\nContenido atómico modificado")
        
        # Verificar que no quedaron archivos temporales residuales en el directorio
        archivos_residuales = [p.name for p in config.NOTES_DIR.iterdir() if p.name.startswith("tmp") or p.name.endswith(".tmp")]
        self.assertEqual(len(archivos_residuales), 0)

        # Probar guardado atómico de configuración
        config_service.guardar_config({"notas_fijadas": ["nota1.txt", "nota2.txt"]})
        cfg = config_service.cargar_config()
        self.assertEqual(cfg.get("notas_fijadas"), ["nota1.txt", "nota2.txt"])

    def test_cli_delete_papelera_y_permanente(self):
        # 1. Borrado por defecto mueve a papelera
        p1 = storage.crear_nota("Nota Papelera CLI", "Texto 1")
        self.assertTrue(p1.exists())
        
        notas = storage.listar_notas()
        idx_p1 = notas.index(p1) + 1
        with patch("builtins.input", return_value="s"):
            core.eliminar_nota_existente(idx_p1, permanente=False)

        self.assertFalse(p1.exists())
        en_papelera = storage.listar_papelera()
        self.assertEqual(len(en_papelera), 1)
        self.assertIn("Nota_Papelera_CLI", en_papelera[0].name)

        # 2. Borrado con --permanente elimina definitivamente sin ir a papelera
        p2 = storage.crear_nota("Nota Permanente CLI", "Texto 2")
        self.assertTrue(p2.exists())

        notas = storage.listar_notas()
        idx_p2 = notas.index(p2) + 1
        with patch("builtins.input", return_value="s"):
            core.eliminar_nota_existente(idx_p2, permanente=True)

        self.assertFalse(p2.exists())
        # La papelera debe seguir teniendo solo la nota anterior
        self.assertEqual(len(storage.listar_papelera()), 1)

    def test_cli_funciona_sin_pyqt6(self):
        # Ejecutar main.py list en un subproceso donde PyQt6 esté completamente bloqueado
        code_list = (
            "import sys\n"
            "sys.modules['PyQt6'] = None\n"
            "sys.modules['PyQt6.QtCore'] = None\n"
            "sys.modules['PyQt6.QtGui'] = None\n"
            "sys.modules['PyQt6.QtWidgets'] = None\n"
            "import main\n"
            "sys.argv = ['main.py', 'list']\n"
            "main.main()\n"
        )
        res_list = subprocess.run([sys.executable, "-c", code_list], capture_output=True, text=True)
        self.assertEqual(res_list.returncode, 0, f"Error CLI sin PyQt6: {res_list.stderr}")
        self.assertTrue(
            "Notas encontradas" in res_list.stdout or "No hay notas aún" in res_list.stdout,
            f"Salida inesperada: {res_list.stdout}"
        )

        # Probar también version sin PyQt6
        code_ver = (
            "import sys\n"
            "sys.modules['PyQt6'] = None\n"
            "sys.modules['PyQt6.QtCore'] = None\n"
            "sys.modules['PyQt6.QtGui'] = None\n"
            "sys.modules['PyQt6.QtWidgets'] = None\n"
            "import main\n"
            "sys.argv = ['main.py', 'version']\n"
            "main.main()\n"
        )
        res_ver = subprocess.run([sys.executable, "-c", code_ver], capture_output=True, text=True)
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("NerdNotes v", res_ver.stdout)
        self.assertIn("Hecho con ❤️ para terminales", res_ver.stdout)

    def test_orden_fecha_desconocida_al_final(self):
        # Crear notas: una con formato estándar de fecha y otra con nombre no estándar
        p_normal = storage.crear_nota("Nota Normal", "Contenido A")
        p_desconocida = config.NOTES_DIR / "nota_sin_fecha.txt"
        p_desconocida.write_text("# Nota Sin Fecha\nSin fecha en nombre", encoding="utf-8")

        ordenadas_desc = storage.ordenar_notas([p_desconocida, p_normal], criterio="fecha", descendente=True)
        # En orden descendente, la normal (fecha reciente) debe ir primera y la desconocida al final
        self.assertEqual(ordenadas_desc[0], p_normal)
        self.assertEqual(ordenadas_desc[1], p_desconocida)

        ordenadas_asc = storage.ordenar_notas([p_desconocida, p_normal], criterio="fecha", descendente=False)
        # En orden ascendente, la desconocida también debe ir al final
        self.assertEqual(ordenadas_asc[0], p_normal)
        self.assertEqual(ordenadas_asc[1], p_desconocida)


if __name__ == "__main__":
    unittest.main()
