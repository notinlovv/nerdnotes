import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import config
import storage
from services.config_service import (
    obtener_notas_fijadas, fijar_nota, desfijar_nota, es_nota_fijada
)
from services.trash_service import (
    mover_a_papelera, listar_papelera, restaurar_nota_papelera, vaciar_papelera
)
from services.tags_service import (
    extraer_etiquetas, listar_todas_etiquetas
)
from services.export_service import (
    exportar_a_pdf, exportar_a_markdown, exportar_a_txt
)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings
from main_gui import NerdNotesApp

app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

class TestFase2Backend(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        self.original_config_file = config.CONFIG_FILE

        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.CONFIG_FILE = config.NOTES_DIR / ".config.json"
        config.asegurar_directorio()

    def tearDown(self):
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        config.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def test_etiquetas_extraccion_y_listado(self):
        r1 = storage.crear_nota("Nota A", "Contenido A", etiquetas=["python", "trabajo"])
        r2 = storage.crear_nota("Nota B", "Contenido B", etiquetas=["trabajo", "urgente"])
        
        tags1 = storage.extraer_etiquetas(r1)
        self.assertIn("python", tags1)
        self.assertIn("trabajo", tags1)

        todas = storage.listar_todas_etiquetas([r1, r2])
        self.assertEqual(todas, ["python", "trabajo", "urgente"])

    def test_busqueda_titulo_contenido_etiquetas(self):
        r1 = storage.crear_nota("Compras", "Comprar leche y pan", etiquetas=["personal"])
        r2 = storage.crear_nota("Trabajo", "Revisar arquitectura del sistema", etiquetas=["proyecto"])

        # Buscar por título
        res_tit = storage.buscar_en_notas("compras", [r1, r2])
        self.assertEqual(res_tit, [r1])

        # Buscar por contenido
        res_cont = storage.buscar_en_notas("arquitectura", [r1, r2])
        self.assertEqual(res_cont, [r2])

        # Buscar por etiqueta
        res_tag = storage.buscar_en_notas("proyecto", [r1, r2])
        self.assertEqual(res_tag, [r2])

        # Filtrar por etiqueta específica
        res_filtro = storage.buscar_en_notas("", [r1, r2], etiqueta_filtro="personal")
        self.assertEqual(res_filtro, [r1])

    def test_renombrar_nota(self):
        r = storage.crear_nota("Titulo Viejo", "Cuerpo de la nota")
        self.assertTrue(r.exists())

        nueva_ruta = storage.renombrar_nota(r, "Titulo Nuevo")
        self.assertIsNotNone(nueva_ruta)
        self.assertTrue(nueva_ruta.exists())
        self.assertFalse(r.exists())

        # Verificar encabezado actualizado
        lineas = nueva_ruta.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lineas[0], "# Titulo Nuevo")

    def test_papelera_mover_restaurar_vaciar(self):
        r = storage.crear_nota("Nota Descartable", "Se ira a papelera")
        self.assertTrue(r.exists())

        # Mover a papelera
        ruta_papelera = storage.mover_a_papelera(r)
        self.assertIsNotNone(ruta_papelera)
        self.assertTrue(ruta_papelera.exists())
        self.assertFalse(r.exists())
        self.assertIn(ruta_papelera, storage.listar_papelera())

        # Listar notas activas NO debe incluir la papelera
        self.assertEqual(len(storage.listar_notas()), 0)

        # Restaurar
        restaurada = storage.restaurar_nota_papelera(ruta_papelera)
        self.assertIsNotNone(restaurada)
        self.assertTrue(restaurada.exists())
        self.assertFalse(ruta_papelera.exists())
        self.assertEqual(len(storage.listar_notas()), 1)

        # Mover de nuevo y vaciar
        p2 = storage.mover_a_papelera(restaurada)
        self.assertEqual(len(storage.listar_papelera()), 1)
        eliminados = storage.vaciar_papelera()
        self.assertEqual(eliminados, 1)
        self.assertEqual(len(storage.listar_papelera()), 0)

    def test_fijar_notas_y_ordenamiento(self):
        r1 = storage.crear_nota("Alpha")
        r2 = storage.crear_nota("Beta")
        r3 = storage.crear_nota("Gamma")

        # Fijar Beta arriba
        storage.fijar_nota(r2.name, fijar=True)
        self.assertTrue(storage.es_nota_fijada(r2.name))
        self.assertFalse(storage.es_nota_fijada(r1.name))

        # Ordenar: Beta debe estar primera siempre
        ordenadas = storage.ordenar_notas([r1, r2, r3], criterio="titulo", descendente=False)
        self.assertEqual(ordenadas[0], r2)

    def test_exportar_formatos(self):
        contenido = "# Titulo\nFecha: 2026-10-26\n\nTexto de exportación"
        
        pdf_out = config.NOTES_DIR / "prueba.pdf"
        md_out = config.NOTES_DIR / "prueba.md"
        txt_out = config.NOTES_DIR / "prueba.txt"

        self.assertTrue(exportar_a_pdf(contenido, pdf_out))
        self.assertTrue(pdf_out.exists())
        self.assertGreater(pdf_out.stat().st_size, 0)

        self.assertTrue(exportar_a_markdown(contenido, md_out))
        self.assertTrue(md_out.exists())

        self.assertTrue(exportar_a_txt(contenido, txt_out))
        self.assertTrue(txt_out.exists())


class TestFase2GUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        self.original_config_file = config.CONFIG_FILE

        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.CONFIG_FILE = config.NOTES_DIR / ".config.json"
        config.asegurar_directorio()

        self.r1 = storage.crear_nota("Nota Uno", "Contenido con palabra clave", etiquetas=["general"])
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

    def test_contador_palabras_y_caracteres(self):
        self.gui.editor_texto.setPlainText("Una dos tres cuatro")
        self.assertIn("4 palabras", self.gui.lbl_contador.text())
        self.assertIn("19 caracteres", self.gui.lbl_contador.text())

    def test_autosave_timer(self):
        # Seleccionar nota
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)
        
        # Modificar texto: debe iniciar timer de autosave
        self.gui.editor_texto.setPlainText("# Nota Uno\nFecha: 2026-10-26\n\nTexto guardado automaticamente")
        self.assertTrue(self.gui.autosave_timer.isActive())
        self.assertTrue(self.gui.modificado)

        # Forzar timeout del timer
        self.gui._ejecutar_autoguardado()
        self.assertFalse(self.gui.modificado)
        
        # Verificar contenido persistido en disco
        contenido = storage.leer_nota(self.gui.ruta_actual)
        self.assertIn("Texto guardado automaticamente", contenido)

    def test_guardar_inmediato_ctrl_s(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        self.gui.editor_texto.setPlainText("# Nota Uno\nTexto Ctrl+S")
        self.gui.guardar_nota_inmediata()
        self.assertFalse(self.gui.autosave_timer.isActive())
        self.assertFalse(self.gui.modificado)

    def test_vista_previa_markdown(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        # Activar vista previa
        self.gui.alternar_vista_previa()
        self.assertTrue(self.gui.modo_preview)
        self.assertTrue(self.gui.editor_texto.isReadOnly())

        # Desactivar vista previa
        self.gui.alternar_vista_previa()
        self.assertFalse(self.gui.modo_preview)
        self.assertFalse(self.gui.editor_texto.isReadOnly())

    def test_resaltado_de_coincidencias(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        self.gui.resaltar_coincidencias("clave")
        extra_sels = self.gui.editor_texto.extraSelections()
        self.assertGreater(len(extra_sels), 0)

        # Limpiar
        self.gui.resaltar_coincidencias("")
        self.assertEqual(len(self.gui.editor_texto.extraSelections()), 0)

    def test_renombrar_desde_gui(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("Nuevo Nombre GUI", True)):
            self.gui.renombrar_nota_seleccionada()

        self.assertEqual(self.gui.lbl_titulo_actual.text(), "Nuevo Nombre GUI")
        self.assertIn("Nuevo Nombre GUI", storage.leer_nota(self.gui.ruta_actual))

    def test_mover_a_papelera_y_restaurar_gui(self):
        item0 = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item0)

        # Mover a papelera
        self.gui.eliminar_nota_seleccionada()
        self.assertEqual(self.gui.lista_notas.count(), 0)

        # Cambiar a vista Papelera (fila 2 de la lista de navegación)
        self.gui.nav_list.setCurrentRow(2)
        self.assertEqual(self.gui.lista_notas.count(), 1)

        # Restaurar
        item_papelera = self.gui.lista_notas.item(0)
        self.gui.lista_notas.setCurrentItem(item_papelera)
        self.gui.restaurar_nota_seleccionada()
        self.assertEqual(self.gui.lista_notas.count(), 0)

        # Volver a notas activas (fila 0 de la lista de navegación)
        self.gui.nav_list.setCurrentRow(0)
        self.assertEqual(self.gui.lista_notas.count(), 1)


class TestNoteIndexYSeguridadConcurrente(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_notes_dir = config.NOTES_DIR
        self.original_trash_dir = config.TRASH_DIR
        config.NOTES_DIR = Path(self.temp_dir.name)
        config.TRASH_DIR = config.NOTES_DIR / ".papelera"
        config.asegurar_directorio()
        from services import note_index
        note_index.limpiar()

    def tearDown(self):
        from services import note_index
        note_index.limpiar()
        config.NOTES_DIR = self.original_notes_dir
        config.TRASH_DIR = self.original_trash_dir
        self.temp_dir.cleanup()

    def test_modificar_contenido_cambiando_mtime_recarga_cache(self):
        from services import note_index
        r = storage.crear_nota("Nota Inicial", "Cuerpo inicial de la nota")
        self.assertIsNotNone(r)

        # Indexación 1
        nota1 = note_index.indexar_nota(r)
        self.assertIsNotNone(nota1)
        self.assertEqual(nota1.titulo, "Nota Inicial")
        self.assertIn("Cuerpo inicial", nota1.contenido)

        # Modificar archivo en disco forzando nuevo mtime
        nuevo_contenido = "# Titulo Modificado\nFecha: 2026-11-05\n\nCuerpo modificado completamente"
        r.write_text(nuevo_contenido, encoding="utf-8")
        nuevo_mtime = nota1.mtime + 10.0
        os.utime(r, (nuevo_mtime, nuevo_mtime))

        # Indexación 2: Debe detectar el cambio de mtime y recargar
        nota2 = note_index.indexar_nota(r)
        self.assertIsNotNone(nota2)
        self.assertEqual(nota2.titulo, "Titulo Modificado")
        self.assertIn("Cuerpo modificado", nota2.contenido)
        self.assertGreater(nota2.mtime, nota1.mtime)

    def test_llamada_sucesiva_sin_cambios_no_lee_disco(self):
        from services import note_index
        r1 = storage.crear_nota("Nota Fria 1", "Contenido 1")
        r2 = storage.crear_nota("Nota Fria 2", "Contenido 2")

        # Carga fría (primera lectura)
        notas_frias = note_index.sincronizar_indice(config.NOTES_DIR)
        self.assertEqual(len(notas_frias), 2)

        # Carga caliente (llamada sucesiva sin cambios):
        # Ni open() ni read_text() deben invocarse para archivos ya cacheados
        with patch.object(Path, "read_text", side_effect=AssertionError("read_text() no debe invocarse sin cambios")):
            with patch("builtins.open", side_effect=AssertionError("open() no debe invocarse sin cambios")):
                notas_calientes = note_index.sincronizar_indice(config.NOTES_DIR)
                self.assertEqual(len(notas_calientes), 2)
                self.assertEqual(notas_calientes[0].titulo, notas_frias[0].titulo)

    def test_eliminar_archivo_fuera_elimina_entrada_en_siguiente_refresco(self):
        from services import note_index
        r1 = storage.crear_nota("Nota Permanente", "Texto permanente")
        r2 = storage.crear_nota("Nota Para Borrar Fuera", "Texto a borrar")

        note_index.sincronizar_indice(config.NOTES_DIR)
        self.assertIsNotNone(note_index.obtener_nota(r1))
        self.assertIsNotNone(note_index.obtener_nota(r2))

        # Eliminar r2 directamente desde el sistema de archivos (fuera de la app)
        r2.unlink()
        self.assertFalse(r2.exists())

        # En el siguiente refresco debe purgarse del índice
        notas_refrescadas = note_index.sincronizar_indice(config.NOTES_DIR)
        self.assertEqual(len(notas_refrescadas), 1)
        self.assertIsNone(note_index.obtener_nota(r2))
        self.assertIsNotNone(note_index.obtener_nota(r1))

    def test_cancelacion_reactiva_search_worker(self):
        from ui.search_worker import SearchWorker
        from services import note_index
        worker = SearchWorker()

        # Probar banderas de interrupción
        self.assertFalse(bool(worker.is_interrupted))
        self.assertFalse(worker.is_interrupted())
        worker.abortar()
        self.assertTrue(bool(worker.is_interrupted))
        self.assertTrue(worker.is_interrupted())

        # Probar que si se cancela, no emite señal resultados_listos
        worker_recibio_senal = []
        worker.resultados_listos.connect(lambda matches, q, qid: worker_recibio_senal.append((matches, q, qid)))

        r = storage.crear_nota("Nota Buscar", "Texto de prueba para worker")

        # Búsqueda abortada a priori
        worker.abortar()
        worker.buscar([r], "Buscar", None, query_id=1)
        self.assertEqual(len(worker_recibio_senal), 0)

        # Búsqueda abortada dinámicamente en medio de la iteración
        r2 = storage.crear_nota("Nota Buscar 2", "Segundo texto")
        r3 = storage.crear_nota("Nota Buscar 3", "Tercer texto")
        worker._abort = False

        original_indexar = note_index.indexar_nota
        def interrumpir_al_segundo(ruta):
            if "Buscar_2" in ruta.name:
                worker.abortar()
            return original_indexar(ruta)

        with patch("services.note_index.indexar_nota", side_effect=interrumpir_al_segundo):
            worker.buscar([r, r2, r3], "Buscar", None, query_id=2)

        # Como se abortó a la mitad, no debe emitir resultados
        self.assertEqual(len(worker_recibio_senal), 0)

        # Búsqueda limpia no abortada
        worker._abort = False
        worker.buscar([r], "Buscar", None, query_id=3)
        self.assertEqual(len(worker_recibio_senal), 1)
        self.assertEqual(worker_recibio_senal[0][2], 3)

    def test_thread_safety_note_index(self):
        import threading
        from services import note_index

        r = storage.crear_nota("Nota Concurrente", "Contenido inicial")
        errores = []

        def lector():
            try:
                for _ in range(50):
                    note_index.indexar_nota(r)
                    note_index.buscar("concurrente", [r])
            except Exception as e:
                errores.append(e)

        def escritor():
            try:
                for i in range(50):
                    note_index.actualizar(r, f"# Titulo {i}\nContenido {i}")
            except Exception as e:
                errores.append(e)

        hilos = [threading.Thread(target=lector) for _ in range(3)] + \
                [threading.Thread(target=escritor) for _ in range(2)]

        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        self.assertEqual(len(errores), 0)


if __name__ == "__main__":
    unittest.main()

