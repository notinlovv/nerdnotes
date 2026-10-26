import sys
import re
from pathlib import Path
from typing import Optional, List, Tuple
from unittest.mock import MagicMock
from PyQt6.QtCore import (
    Qt, QTimer, QSettings, QPoint, QThread, pyqtSignal,
    QPropertyAnimation, QEasingCurve, QFileSystemWatcher, QEvent,
    QModelIndex
)
from PyQt6.QtGui import (
    QKeySequence, QShortcut, QTextCharFormat, QColor, QTextCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListView, QTextEdit, QPushButton, QInputDialog, QMessageBox,
    QLineEdit, QSplitter, QComboBox, QLabel, QFileDialog, QMenu,
    QListWidget, QListWidgetItem, QGraphicsOpacityEffect, QCompleter,
    QDialog
)
import config
import storage
from services.config_service import obtener_notas_fijadas_set
from services.icon_service import get_icon
from services import note_index
from ui.notes_model import NoteItem, NoteRoles, NotesListModel, NotesFilterProxyModel, extraer_vista_previa
from ui.notes_list_view import NotesListView
from ui.search_worker import SearchWorker
from ui.tag_dialogs import MultiCompleterLineEdit, EditarEtiquetasDialog, NuevaNotaDialog

class NerdNotesApp(QMainWindow):
    solicitar_busqueda = pyqtSignal(list, str, object, int)  # (notas, query, tag_filtro, query_id)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NerdNotes")
        self.resize(960, 650)
        
        # --- CONFIGURACIÓN Y ESTADO ---
        self.settings = QSettings("NerdNotes", "NerdNotesApp")
        self.ruta_actual: Optional[Path] = None
        self.modificado: bool = False
        self._cargando_texto: bool = False
        self._bloquear_seleccion: bool = False
        self.modo_preview: bool = False
        
        # Modo de visualización: "todas", "fijadas", "papelera", o "tag:<nombre>"
        self.filtro_categoria: str = "todas"
        
        # Tema: "dark" o "light"
        self.tema_actual = str(self.settings.value("theme", "dark"))
        if self.tema_actual not in ("dark", "light"):
            self.tema_actual = "dark"

        # Tamaño de fuente del editor
        self.font_size = int(self.settings.value("font_size", 14))

        # --- TIMER DE AUTOGUARDADO (Debounce ~800ms) ---
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(800)
        self.autosave_timer.timeout.connect(self._ejecutar_autoguardado)

        # --- BÚSQUEDA EN SEGUNDO PLANO Y DEBOUNCE (~250ms) ---
        self._query_id_actual = 0
        self.timer_busqueda = QTimer(self)
        self.timer_busqueda.setSingleShot(True)
        self.timer_busqueda.setInterval(250)
        self.timer_busqueda.timeout.connect(self._disparar_busqueda)

        self.thread_busqueda = QThread(self)
        self.search_worker = SearchWorker()
        self.search_worker.moveToThread(self.thread_busqueda)
        self.solicitar_busqueda.connect(self.search_worker.buscar)
        self.search_worker.resultados_listos.connect(self._al_recibir_resultados_busqueda)
        self.thread_busqueda.start()

        # --- CONSTRUCCIÓN DEL LAYOUT DE TRES PANELES (QSplitter) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)

        # ==============================================================
        # PANEL 1: BARRA LATERAL (Categorías, Etiquetas, Papelera)
        # ==============================================================
        self.widget_sidebar = QWidget()
        self.widget_sidebar.setObjectName("widget_sidebar")
        layout_sidebar = QVBoxLayout(self.widget_sidebar)
        layout_sidebar.setContentsMargins(10, 12, 10, 10)
        layout_sidebar.setSpacing(8)

        # Encabezado de la barra lateral con Logo y botón de Tema
        layout_sidebar_header = QHBoxLayout()
        lbl_app = QLabel("NerdNotes")
        lbl_app.setObjectName("lbl_app_logo")
        self.btn_tema = QPushButton()
        self.btn_tema.setObjectName("btn_icon")
        self.btn_tema.setToolTip("Cambiar tema claro/oscuro (Ctrl+T)")
        self.btn_tema.clicked.connect(self.cambiar_tema_con_animacion)

        layout_sidebar_header.addWidget(lbl_app, 1)
        layout_sidebar_header.addWidget(self.btn_tema)
        layout_sidebar.addLayout(layout_sidebar_header)

        # Lista de Navegación de la barra lateral
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        self.nav_list.setSpacing(2)
        
        self.item_nav_todas = QListWidgetItem("Todas las notas")
        self.item_nav_fijadas = QListWidgetItem("Fijadas")
        self.item_nav_papelera = QListWidgetItem("Papelera")

        self.nav_list.addItem(self.item_nav_todas)
        self.nav_list.addItem(self.item_nav_fijadas)
        self.nav_list.addItem(self.item_nav_papelera)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._al_cambiar_categoria_nav)
        layout_sidebar.addWidget(self.nav_list)

        # Separador / Título de Etiquetas
        lbl_etiquetas_seccion = QLabel("ETIQUETAS")
        lbl_etiquetas_seccion.setObjectName("lbl_seccion")
        layout_sidebar.addWidget(lbl_etiquetas_seccion)

        # Lista de Etiquetas
        self.tags_list = QListWidget()
        self.tags_list.setObjectName("tags_list")
        self.tags_list.setSpacing(2)
        self.tags_list.itemClicked.connect(self._al_clickear_etiqueta_nav)
        layout_sidebar.addWidget(self.tags_list, 1)

        # ==============================================================
        # PANEL 2: LISTA DE NOTAS (Título, Vista previa, Fecha)
        # ==============================================================
        self.widget_lista = QWidget()
        self.widget_lista.setObjectName("widget_lista")
        layout_lista = QVBoxLayout(self.widget_lista)
        layout_lista.setContentsMargins(10, 10, 10, 10)
        layout_lista.setSpacing(8)

        # Barra de herramientas superior de la lista
        layout_herramientas_lista = QHBoxLayout()
        layout_herramientas_lista.setSpacing(6)

        self.btn_toggle_sidebar = QPushButton()
        self.btn_toggle_sidebar.setObjectName("btn_icon")
        self.btn_toggle_sidebar.setToolTip("Ocultar/Mostrar barra lateral (Ctrl+\\)")
        self.btn_toggle_sidebar.clicked.connect(self.animar_sidebar)

        self.btn_nueva = QPushButton()
        self.btn_nueva.setObjectName("btn_icon")
        self.btn_nueva.setToolTip("Nueva nota (Ctrl+N)")
        self.btn_nueva.clicked.connect(self.crear_nueva_nota)

        self.btn_importar = QPushButton()
        self.btn_importar.setObjectName("btn_icon")
        self.btn_importar.setToolTip("Importar nota (.txt o .md)")
        self.btn_importar.clicked.connect(self.importar_archivo_dialog)

        # Botones de papelera (ocultos por defecto)
        self.btn_restaurar = QPushButton()
        self.btn_restaurar.setObjectName("btn_icon")
        self.btn_restaurar.setToolTip("Restaurar nota seleccionada")
        self.btn_restaurar.clicked.connect(self.restaurar_nota_seleccionada)
        self.btn_restaurar.setVisible(False)

        self.btn_vaciar_papelera = QPushButton()
        self.btn_vaciar_papelera.setObjectName("btn_icon")
        self.btn_vaciar_papelera.setToolTip("Vaciar papelera permanentemente")
        self.btn_vaciar_papelera.clicked.connect(self.vaciar_papelera)
        self.btn_vaciar_papelera.setVisible(False)

        # Desplegable de Orden
        self.combo_orden = QComboBox()
        self.combo_orden.addItems([
            "Fecha (reciente)",
            "Fecha (antigua)",
            "Título (A-Z)",
            "Título (Z-A)",
            "Modificación"
        ])
        orden_guardado = self.settings.value("orden_idx", 0, type=int)
        self.combo_orden.setCurrentIndex(orden_guardado)
        self.combo_orden.currentIndexChanged.connect(self.al_cambiar_orden)

        layout_herramientas_lista.addWidget(self.btn_toggle_sidebar)
        layout_herramientas_lista.addWidget(self.btn_nueva)
        layout_herramientas_lista.addWidget(self.btn_importar)
        layout_herramientas_lista.addWidget(self.btn_restaurar)
        layout_herramientas_lista.addWidget(self.btn_vaciar_papelera)
        layout_herramientas_lista.addStretch()
        layout_herramientas_lista.addWidget(self.combo_orden)
        layout_lista.addLayout(layout_herramientas_lista)

        # Buscador en tiempo real
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar título o contenido (Ctrl+F)...")
        self.buscador.textChanged.connect(self.al_cambiar_busqueda)
        self.buscador.installEventFilter(self)
        layout_lista.addWidget(self.buscador)

        # QListView personalizada con modelo propio y proxy para filtrado instantáneo
        self.notes_model = NotesListModel([], self)
        self.proxy_model = NotesFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.notes_model)

        self.lista_notas = NotesListView()
        self.lista_notas.setObjectName("lista_notas")
        self.lista_notas.setModel(self.proxy_model)
        self.lista_notas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista_notas.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        self.lista_notas.currentItemChanged.connect(self._al_cambiar_seleccion_lista)
        self.lista_notas.clicked.connect(self._al_clickear_lista)
        layout_lista.addWidget(self.lista_notas, 1)

        # ==============================================================
        # PANEL 3: EDITOR DE TEXTO
        # ==============================================================
        self.widget_editor = QWidget()
        self.widget_editor.setObjectName("widget_editor")
        layout_editor = QVBoxLayout(self.widget_editor)
        layout_editor.setContentsMargins(12, 10, 12, 10)
        layout_editor.setSpacing(6)

        # Barra superior del editor
        layout_herramientas_editor = QHBoxLayout()
        self.lbl_titulo_actual = QLabel("Sin nota seleccionada")
        self.lbl_titulo_actual.setObjectName("lbl_titulo_actual")
        
        self.btn_preview = QPushButton()
        self.btn_preview.setObjectName("btn_icon")
        self.btn_preview.setCheckable(True)
        self.btn_preview.setToolTip("Vista previa Markdown (Ctrl+Shift+P)")
        self.btn_preview.clicked.connect(self.alternar_vista_previa)

        self.btn_exportar = QPushButton()
        self.btn_exportar.setObjectName("btn_icon")
        self.btn_exportar.setToolTip("Exportar a PDF, MD o TXT")
        self.btn_exportar.clicked.connect(self.exportar_nota_actual)

        self.btn_eliminar = QPushButton()
        self.btn_eliminar.setObjectName("btn_icon")
        self.btn_eliminar.setToolTip("Mover a papelera (Del)")
        self.btn_eliminar.clicked.connect(self.eliminar_nota_seleccionada)

        layout_herramientas_editor.addWidget(self.lbl_titulo_actual, 1)
        layout_herramientas_editor.addWidget(self.btn_preview)
        layout_herramientas_editor.addWidget(self.btn_exportar)
        layout_herramientas_editor.addWidget(self.btn_eliminar)
        layout_editor.addLayout(layout_herramientas_editor)

        # Área de edición
        self.editor_texto = QTextEdit()
        self.editor_texto.setObjectName("editor_texto")
        self._aplicar_tamano_fuente(self.font_size)
        self.editor_texto.textChanged.connect(self.al_modificar_texto)
        layout_editor.addWidget(self.editor_texto, 1)

        # Configurar tamaños mínimos para evitar colapso a ancho 0
        self.widget_sidebar.setMinimumWidth(160)
        self.widget_lista.setMinimumWidth(220)
        self.widget_editor.setMinimumWidth(300)
        self.editor_texto.setMinimumWidth(250)

        # Ensamblar paneles en el Splitter
        self.splitter.addWidget(self.widget_sidebar)
        self.splitter.addWidget(self.widget_lista)
        self.splitter.addWidget(self.widget_editor)
        self.splitter.setCollapsible(0, True)   # Solo la barra lateral puede colapsarse
        self.splitter.setCollapsible(1, False)  # La lista nunca debe colapsar a 0
        self.splitter.setCollapsible(2, False)  # El editor NUNCA debe colapsar a 0
        
        # Proporciones iniciales: Sidebar (200), Lista (280), Editor (480)
        splitter_state = self.settings.value("splitter")
        if splitter_state:
            self.splitter.restoreState(splitter_state)
            sizes = self.splitter.sizes()
            # Validar que ningún panel crítico haya quedado con ancho 0 o colapsado en QSettings
            if len(sizes) == 3 and (sizes[2] < 200 or sizes[1] < 150):
                self.splitter.setSizes([200, 280, 480])
                self.settings.setValue("splitter", self.splitter.saveState())
        else:
            self.splitter.setSizes([200, 280, 480])

        self.setCentralWidget(self.splitter)

        # Barra de estado inferior y widget de Deshacer
        self.statusBar()
        self._widget_deshacer = QWidget()
        layout_deshacer = QHBoxLayout(self._widget_deshacer)
        layout_deshacer.setContentsMargins(4, 0, 8, 0)
        layout_deshacer.setSpacing(8)
        self._lbl_deshacer = QLabel("")
        self._btn_deshacer = QPushButton("Deshacer")
        self._btn_deshacer.setObjectName("btn_deshacer")
        self._btn_deshacer.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_deshacer.clicked.connect(self._deshacer_mover_a_papelera)
        layout_deshacer.addWidget(self._lbl_deshacer)
        layout_deshacer.addWidget(self._btn_deshacer)
        self._widget_deshacer.setVisible(False)
        self.statusBar().addWidget(self._widget_deshacer)

        self.timer_deshacer = QTimer(self)
        self.timer_deshacer.setSingleShot(True)
        self.timer_deshacer.setInterval(5000)
        self.timer_deshacer.timeout.connect(self._ocultar_deshacer)
        self._ultima_nota_en_papelera: Optional[Path] = None

        self.lbl_contador = QLabel("0 palabras | 0 caracteres")
        self.lbl_contador.setObjectName("lbl_contador")
        self.statusBar().addPermanentWidget(self.lbl_contador)

        # QFileSystemWatcher sobre NOTES_DIR (con debounce ~400ms)
        self._ignorando_watcher = False
        self.watcher = QFileSystemWatcher(self)
        self.timer_watcher = QTimer(self)
        self.timer_watcher.setSingleShot(True)
        self.timer_watcher.setInterval(400)
        self.timer_watcher.timeout.connect(self._al_disparar_watcher)
        self._iniciar_file_watcher()

        # Atajos de teclado
        self._configurar_atajos()

        # Restaurar geometría
        geom = self.settings.value("geometria")
        if geom:
            self.restoreGeometry(geom)

        # Estado inicial sin nota seleccionada hasta cargar
        self._mostrar_estado_sin_nota()

        # Aplicar tema inicial y cargar iconos
        self._aplicar_tema(self.tema_actual)
        self.cargar_lista_notas()
        self._restaurar_ultima_nota()

    # --- CONFIGURACIÓN DE ATAJOS ---
    def _configurar_atajos(self):
        # Ctrl+N para nueva nota (un solo atajo sin duplicación en botón)
        QShortcut(QKeySequence("Ctrl+N"), self, self.crear_nueva_nota)
        # Ctrl+F para foco en buscador
        QShortcut(QKeySequence("Ctrl+F"), self, self._foco_buscador)
        # Ctrl+S para guardar nota de inmediato
        QShortcut(QKeySequence("Ctrl+S"), self, self.guardar_nota_inmediata)
        # F2 para renombrar nota seleccionada
        QShortcut(QKeySequence("F2"), self, self.renombrar_nota_seleccionada)
        
        # Delete: limitado exclusivamente al foco en la lista de notas (WidgetWithChildrenShortcut)
        shortcut_del = QShortcut(QKeySequence.StandardKey.Delete, self.lista_notas)
        shortcut_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut_del.activated.connect(self.eliminar_nota_seleccionada)

        # Ctrl+Shift+P para alternar vista previa Markdown
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.alternar_vista_previa)
        # Ctrl+T para cambiar de tema
        QShortcut(QKeySequence("Ctrl+T"), self, self.cambiar_tema_con_animacion)
        # Ctrl+\ para colapsar/expandir barra lateral (libera Ctrl+B para negrita en Fase B)
        QShortcut(QKeySequence("Ctrl+\\"), self, self.animar_sidebar)
        
        # Formato Markdown sobre selección o palabra actual (manteniendo undo/redo)
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self.aplicar_formato_markdown("negrita"))
        QShortcut(QKeySequence("Ctrl+I"), self, lambda: self.aplicar_formato_markdown("cursiva"))
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.aplicar_formato_markdown("h1"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.aplicar_formato_markdown("h2"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self.aplicar_formato_markdown("h3"))
        QShortcut(QKeySequence("Ctrl+Shift+L"), self, lambda: self.aplicar_formato_markdown("lista"))
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, lambda: self.aplicar_formato_markdown("checklist"))

        # Zoom de fuente: Ctrl++, Ctrl+-, Ctrl+0
        QShortcut(QKeySequence("Ctrl++"), self, lambda: self._cambiar_zoom(1))
        QShortcut(QKeySequence("Ctrl+="), self, lambda: self._cambiar_zoom(1))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self._cambiar_zoom(-1))
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self._cambiar_zoom(0))

    def _foco_buscador(self):
        self.buscador.setFocus()
        self.buscador.selectAll()

    def _cambiar_zoom(self, delta: int):
        if delta == 0:
            self.font_size = 14
        else:
            self.font_size = max(8, min(36, self.font_size + delta))
        self._aplicar_tamano_fuente(self.font_size)
        self.settings.setValue("font_size", self.font_size)
        self.statusBar().showMessage(f"Tamaño de fuente: {self.font_size} pt", 2000)

    def eventFilter(self, obj, event):
        # Esc en el buscador lo limpia y devuelve el foco a la lista
        if obj == self.buscador and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.buscador.clear()
                self.lista_notas.setFocus()
                return True
        return super().eventFilter(obj, event)

    # --- FORMATO MARKDOWN EN EL EDITOR ---
    def aplicar_formato_markdown(self, tipo: str):
        if self.modo_preview or self.editor_texto.isReadOnly():
            return

        cursor = self.editor_texto.textCursor()
        cursor.beginEditBlock()
        try:
            if tipo in ("negrita", "cursiva"):
                simbolo = "**" if tipo == "negrita" else "*"
                len_simbolo = len(simbolo)

                if not cursor.hasSelection():
                    cursor.select(QTextCursor.SelectionType.WordUnderCursor)

                if cursor.hasSelection():
                    sel_text = cursor.selectedText()
                    start_sel = cursor.selectionStart()
                    if sel_text.startswith(simbolo) and sel_text.endswith(simbolo) and len(sel_text) >= 2 * len_simbolo:
                        nuevo_texto = sel_text[len_simbolo:-len_simbolo]
                    else:
                        nuevo_texto = f"{simbolo}{sel_text}{simbolo}"
                    cursor.insertText(nuevo_texto)
                    cursor.setPosition(start_sel)
                    cursor.setPosition(start_sel + len(nuevo_texto), QTextCursor.MoveMode.KeepAnchor)
                else:
                    pos = cursor.position()
                    cursor.insertText(f"{simbolo}{simbolo}")
                    cursor.setPosition(pos + len_simbolo)
                    self.editor_texto.setTextCursor(cursor)
                    return

            elif tipo in ("h1", "h2", "h3"):
                prefijo = {"h1": "# ", "h2": "## ", "h3": "### "}[tipo]
                start = cursor.selectionStart()
                end = cursor.selectionEnd()

                cursor.setPosition(start)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                start_pos = cursor.position()

                cursor.setPosition(end)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
                end_pos = cursor.position()

                cursor.setPosition(start_pos)
                cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)

                bloque = cursor.selectedText()
                lineas = bloque.split("\u2029")
                nuevas = []
                for lin in lineas:
                    lin_limpia = re.sub(r"^#{1,6}\s*", "", lin)
                    if lin.startswith(prefijo):
                        nuevas.append(lin_limpia)
                    else:
                        nuevas.append(prefijo + lin_limpia)
                texto_insertado = "\n".join(nuevas)
                cursor.insertText(texto_insertado)
                cursor.setPosition(start_pos)
                cursor.setPosition(start_pos + len(texto_insertado), QTextCursor.MoveMode.KeepAnchor)

            elif tipo in ("lista", "checklist"):
                start = cursor.selectionStart()
                end = cursor.selectionEnd()

                cursor.setPosition(start)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                start_pos = cursor.position()

                cursor.setPosition(end)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
                end_pos = cursor.position()

                cursor.setPosition(start_pos)
                cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)

                bloque = cursor.selectedText()
                lineas = bloque.split("\u2029")
                nuevas = []
                for lin in lineas:
                    if tipo == "lista":
                        if re.match(r"^-\s*\[[ xX]\]\s*", lin):
                            nuevas.append("- " + re.sub(r"^-\s*\[[ xX]\]\s*", "", lin))
                        elif lin.startswith("- "):
                            nuevas.append(lin[2:])
                        else:
                            nuevas.append("- " + lin)
                    else:  # checklist
                        if re.match(r"^-\s*\[[ xX]\]\s*", lin):
                            nuevas.append(re.sub(r"^-\s*\[[ xX]\]\s*", "", lin))
                        elif lin.startswith("- "):
                            nuevas.append("- [ ] " + lin[2:])
                        else:
                            nuevas.append("- [ ] " + lin)
                texto_insertado = "\n".join(nuevas)
                cursor.insertText(texto_insertado)
                cursor.setPosition(start_pos)
                cursor.setPosition(start_pos + len(texto_insertado), QTextCursor.MoveMode.KeepAnchor)
        finally:
            cursor.endEditBlock()
            self.editor_texto.setTextCursor(cursor)

    # --- FILE SYSTEM WATCHER SOBRE NOTES_DIR ---
    def _iniciar_file_watcher(self):
        try:
            config.asegurar_directorio()
            ruta_dir = str(config.NOTES_DIR.resolve())
            if Path(ruta_dir).exists():
                if ruta_dir not in self.watcher.directories():
                    self.watcher.addPath(ruta_dir)
            self.watcher.directoryChanged.connect(self._al_cambio_archivo_externo)
            self.watcher.fileChanged.connect(self._al_cambio_archivo_externo)
        except Exception as e:
            print(f"Error al iniciar QFileSystemWatcher: {e}")

    def _al_cambio_archivo_externo(self, path: str):
        if self._ignorando_watcher:
            return
        self.timer_watcher.start(400)

    def _al_disparar_watcher(self):
        try:
            ruta_dir = str(config.NOTES_DIR.resolve())
            if ruta_dir not in self.watcher.directories() and Path(ruta_dir).exists():
                self.watcher.addPath(ruta_dir)
        except Exception:
            pass

        # Criterio: no tocar el editor si hay cambios sin guardar
        if self.modificado:
            return

        if self.filtro_categoria != "papelera":
            self.cargar_lista_notas(seleccionar_ruta=self.ruta_actual)

    def _aplicar_tamano_fuente(self, tamano: int):
        font = self.editor_texto.font()
        font.setPointSize(tamano)
        self.editor_texto.setFont(font)

    # --- GESTIÓN DE TEMAS (Dark / Light) Y ANIMACIÓN ---
    def _aplicar_tema(self, tema: str):
        self.tema_actual = tema
        self.settings.setValue("theme", tema)
        
        nombre_qss = "dark.qss" if tema == "dark" else "light.qss"
        ruta_qss = Path(__file__).parent / "resources" / nombre_qss
        if ruta_qss.exists():
            try:
                qss_text = ruta_qss.read_text(encoding="utf-8")
                QApplication.instance().setStyleSheet(qss_text)
            except Exception as e:
                print(f"Error al cargar QSS {nombre_qss}: {e}")

        self.lista_notas.set_tema(tema)
        self._actualizar_iconos()

    def _actualizar_iconos(self):
        t = self.tema_actual
        self.btn_tema.setIcon(get_icon("theme", t))
        self.btn_toggle_sidebar.setIcon(get_icon("sidebar", t))
        self.btn_nueva.setIcon(get_icon("new", t))
        self.btn_importar.setIcon(get_icon("import", t))
        self.btn_restaurar.setIcon(get_icon("restore", t))
        self.btn_vaciar_papelera.setIcon(get_icon("empty", t))
        self.btn_preview.setIcon(get_icon("preview" if not self.modo_preview else "edit", t))
        self.btn_exportar.setIcon(get_icon("export", t))
        self.btn_eliminar.setIcon(get_icon("trash", t))

        # Iconos SVG de la barra lateral (sin emojis)
        self.item_nav_todas.setIcon(get_icon("folder", t))
        self.item_nav_fijadas.setIcon(get_icon("pin", t))
        self.item_nav_papelera.setIcon(get_icon("trash", t))
        
        # Actualizar iconos de etiquetas
        for i in range(self.tags_list.count()):
            self.tags_list.item(i).setIcon(get_icon("tag", t))

    def cambiar_tema(self, nuevo_tema: Optional[str] = None):
        """Cambia el tema activo y persiste la configuración."""
        if nuevo_tema is None:
            nuevo_tema = "light" if self.tema_actual == "dark" else "dark"
        self._aplicar_tema(nuevo_tema)
        self.statusBar().showMessage(f"Tema activado: {nuevo_tema.capitalize()}", 2000)

    def cambiar_tema_con_animacion(self):
        """Transición suave con QPropertyAnimation aplicada solo al splitter para evitar parpadeos."""
        nuevo_tema = "light" if self.tema_actual == "dark" else "dark"
        
        effect = QGraphicsOpacityEffect(self.splitter)
        self.splitter.setGraphicsEffect(effect)
        
        self.anim_fade = QPropertyAnimation(effect, b"opacity")
        self.anim_fade.setDuration(90)
        self.anim_fade.setStartValue(1.0)
        self.anim_fade.setEndValue(0.4)
        self.anim_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def al_desvanecer():
            self.cambiar_tema(nuevo_tema)
            self.anim_in = QPropertyAnimation(effect, b"opacity")
            self.anim_in.setDuration(110)
            self.anim_in.setStartValue(0.4)
            self.anim_in.setEndValue(1.0)
            self.anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
            
            def al_terminar():
                self.splitter.setGraphicsEffect(None)
                
            self.anim_in.finished.connect(al_terminar)
            self.anim_in.start()

        self.anim_fade.finished.connect(al_desvanecer)
        self.anim_fade.start()

    # --- ANIMACIÓN AL MOSTRAR/OCULTAR BARRA LATERAL ---
    def animar_sidebar(self):
        ancho_actual = self.widget_sidebar.width()
        ocultar = (ancho_actual > 20)
        fin = 0 if ocultar else 200

        self.anim_sidebar = QPropertyAnimation(self.widget_sidebar, b"maximumWidth")
        self.anim_sidebar.setDuration(220)
        self.anim_sidebar.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim_sidebar.setStartValue(ancho_actual)
        self.anim_sidebar.setEndValue(fin)

        def al_terminar():
            if not ocultar:
                self.widget_sidebar.setMaximumWidth(16777215)
                self.widget_sidebar.setMinimumWidth(120)
            else:
                self.widget_sidebar.setMinimumWidth(0)

        self.anim_sidebar.finished.connect(al_terminar)
        self.anim_sidebar.start()

    # --- BARRA LATERAL: CATEGORÍAS Y ETIQUETAS ---
    def _al_cambiar_categoria_nav(self, row: int):
        self.tags_list.blockSignals(True)
        self.tags_list.clearSelection()
        self.tags_list.blockSignals(False)

        if row == 0:
            self.filtro_categoria = "todas"
        elif row == 1:
            self.filtro_categoria = "fijadas"
        elif row == 2:
            self.filtro_categoria = "papelera"

        self._actualizar_visibilidad_botones_panel()
        self.cargar_lista_notas()

    def _al_clickear_etiqueta_nav(self, item: QListWidgetItem):
        self.nav_list.blockSignals(True)
        self.nav_list.clearSelection()
        self.nav_list.blockSignals(False)

        tag = item.data(Qt.ItemDataRole.UserRole) or item.text().strip()
        self.filtro_categoria = f"tag:{tag}"
        self._actualizar_visibilidad_botones_panel()
        self.cargar_lista_notas()

    def _actualizar_visibilidad_botones_panel(self):
        es_papelera = (self.filtro_categoria == "papelera")
        self.btn_nueva.setVisible(not es_papelera)
        self.btn_importar.setVisible(not es_papelera)
        self.btn_eliminar.setVisible(not es_papelera)
        self.btn_preview.setEnabled(not es_papelera)
        self.btn_restaurar.setVisible(es_papelera)
        self.btn_vaciar_papelera.setVisible(es_papelera)

    # --- AUTOGUARDADO Y EDICIÓN ---
    def al_modificar_texto(self):
        self._actualizar_contador()

        if self._cargando_texto or self.modo_preview:
            return

        self.modificado = True

        query = self.buscador.text().strip()
        if query:
            self.resaltar_coincidencias(query)

        self.autosave_timer.start(800)

    def _actualizar_contador(self):
        texto = self.editor_texto.toPlainText()
        palabras = len(texto.split()) if texto.strip() else 0
        caracteres = len(texto)
        self.lbl_contador.setText(f"{palabras} palabras | {caracteres} caracteres")

    def _ejecutar_autoguardado(self):
        if self.modificado and self.ruta_actual and (self.filtro_categoria != "papelera") and not self.modo_preview:
            exito = self.guardar_nota(silencioso=True)
            if exito:
                self.statusBar().showMessage("Autoguardado", 1500)

    def guardar_nota_inmediata(self):
        if self.autosave_timer.isActive():
            self.autosave_timer.stop()
        if self.guardar_nota(silencioso=False):
            self.statusBar().showMessage("Nota guardada", 2500)

    def guardar_nota(self, silencioso: bool = False) -> bool:
        if not self.ruta_actual or (self.filtro_categoria == "papelera") or self.modo_preview:
            return True

        contenido = self.editor_texto.toPlainText()
        self._ignorando_watcher = True
        try:
            exito = storage.guardar_nota(self.ruta_actual, contenido)
        finally:
            self._ignorando_watcher = False

        if exito:
            self.modificado = False
            # Refrescar vista previa del ítem
            row = self.notes_model.find_row_by_path(self.ruta_actual)
            if row >= 0:
                item_obj = self.notes_model.get_item(row)
                if item_obj:
                    item_obj.titulo, _ = storage.obtener_metadatos(self.ruta_actual)
                    item_obj.vista_previa = extraer_vista_previa(contenido)
                    item_obj.etiquetas = storage.extraer_etiquetas(self.ruta_actual)
                    item_obj.contenido_lower = contenido.lower()
                    src_idx = self.notes_model.index(row, 0)
                    self.notes_model.dataChanged.emit(src_idx, src_idx)

            # Refrescar la sidebar cuando cambien las etiquetas al guardar
            self._actualizar_etiquetas_barra_lateral()

            if not silencioso:
                self.statusBar().showMessage("Nota actualizada correctamente.", 3000)
            return True
        else:
            self.statusBar().showMessage("Error al guardar la nota.", 4000)
            return False

    # --- CARGA Y SELECCIÓN DE NOTAS ---
    def _criterio_orden_actual(self) -> Tuple[str, bool]:
        idx = self.combo_orden.currentIndex()
        if idx == 0: return ("fecha", True)
        elif idx == 1: return ("fecha", False)
        elif idx == 2: return ("titulo", False)
        elif idx == 3: return ("titulo", True)
        elif idx == 4: return ("modificacion", True)
        return ("fecha", True)

    def _mostrar_estado_sin_nota(self):
        self.ruta_actual = None
        self._cargando_texto = True
        self.editor_texto.clear()
        self.editor_texto.setPlaceholderText("Selecciona una nota para ver su contenido o presiona Ctrl+N para crear una nueva.")
        self.editor_texto.setReadOnly(True)
        self.editor_texto.setEnabled(False)
        self._cargando_texto = False
        self.lbl_titulo_actual.setText("Sin nota seleccionada")
        self.lbl_contador.setText("0 palabras | 0 caracteres")
        self.btn_preview.setEnabled(False)
        self.btn_preview.setChecked(False)
        self.btn_exportar.setEnabled(False)
        self.btn_eliminar.setEnabled(False)

    def _al_clickear_lista(self, index: QModelIndex):
        if not index.isValid():
            return
        ruta = index.data(NoteRoles.PathRole)
        if ruta:
            es_papelera = (self.filtro_categoria == "papelera")
            if (self.ruta_actual != ruta 
                or not self.editor_texto.isEnabled() 
                or (self.editor_texto.isReadOnly() and not es_papelera and not self.modo_preview)):
                self.mostrar_contenido(ruta, dar_foco=True)
            elif not es_papelera and not self.modo_preview:
                self.editor_texto.setFocus()

    def cargar_lista_notas(self, seleccionar_ruta: Optional[Path] = None):
        # Guardar en silencio antes de cualquier recarga para evitar pérdida de ediciones
        if self.modificado and self.ruta_actual and (self.filtro_categoria != "papelera") and not self.modo_preview:
            self.guardar_nota(silencioso=True)

        self._bloquear_seleccion = True
        try:
            es_papelera = (self.filtro_categoria == "papelera")
            if es_papelera:
                archivos = storage.listar_papelera()
            else:
                criterio, descendente = self._criterio_orden_actual()
                archivos = storage.listar_notas()
                archivos = storage.ordenar_notas(archivos, criterio=criterio, descendente=descendente)

            # Cargar todas las notas usando la caché de note_index (1 sola lectura por archivo modificado)
            indexed_notes = note_index.indexar_notas(archivos)
            pinned_set = obtener_notas_fijadas_set() if not es_papelera else set()

            items: List[NoteItem] = []
            for n in indexed_notes:
                items.append(NoteItem(
                    ruta=n.ruta,
                    titulo=n.titulo,
                    fecha=n.fecha,
                    vista_previa=n.vista_previa,
                    etiquetas=n.etiquetas,
                    fijada=(n.ruta.name in pinned_set),
                    contenido_lower=n.contenido_lower
                ))

            # Actualizar el modelo base
            self.notes_model.set_items(items)

            # Actualizar filtros en el QSortFilterProxyModel
            self.proxy_model.set_filtro_categoria(self.filtro_categoria)
            query = self.buscador.text().strip()
            self.proxy_model.set_filtro_busqueda(query)

            # Actualizar etiquetas de la barra lateral desde la caché en memoria
            if not es_papelera:
                self._actualizar_etiquetas_barra_lateral()

            # Determinar qué nota seleccionar en el proxy model
            ruta_a_seleccionar = seleccionar_ruta or self.ruta_actual
            target_proxy_idx = QModelIndex()

            if ruta_a_seleccionar:
                target_proxy_idx = self.proxy_model.find_proxy_index_by_path(ruta_a_seleccionar)

            if not target_proxy_idx.isValid() and self.proxy_model.rowCount() > 0 and not self.ruta_actual:
                target_proxy_idx = self.proxy_model.index(0, 0)

            if target_proxy_idx.isValid():
                self.lista_notas.setCurrentIndex(target_proxy_idx)
                nueva_ruta = target_proxy_idx.data(NoteRoles.PathRole)
                if (seleccionar_ruta 
                    or nueva_ruta != self.ruta_actual 
                    or not self.ruta_actual 
                    or (self.editor_texto.isReadOnly() != es_papelera and not self.modo_preview)
                    or not self.editor_texto.isEnabled()):
                    self.mostrar_contenido(nueva_ruta, dar_foco=bool(seleccionar_ruta))
            elif self.proxy_model.rowCount() == 0:
                self._mostrar_estado_sin_nota()
        finally:
            self._bloquear_seleccion = False

    def _actualizar_etiquetas_barra_lateral(self):
        todas = note_index.listar_todas_etiquetas()
        
        self.tags_list.blockSignals(True)
        self.tags_list.clear()
        for t in todas:
            it = QListWidgetItem(t)
            it.setIcon(get_icon("tag", self.tema_actual))
            it.setData(Qt.ItemDataRole.UserRole, t)
            self.tags_list.addItem(it)
        self.tags_list.blockSignals(False)

    def _restaurar_ultima_nota(self):
        ultima = self.settings.value("ultima_nota")
        if ultima and self.filtro_categoria != "papelera":
            p = Path(ultima)
            if p.exists() and p.is_file():
                idx = self.proxy_model.find_proxy_index_by_path(p)
                if idx.isValid():
                    self.lista_notas.setCurrentIndex(idx)
                    self.mostrar_contenido(p, dar_foco=False)

    def _al_cambiar_seleccion_lista(self, current: QModelIndex, previous: QModelIndex):
        if self._bloquear_seleccion:
            return

        if not current.isValid():
            if self.proxy_model.rowCount() == 0:
                self._mostrar_estado_sin_nota()
            return

        nueva_ruta = current.data(NoteRoles.PathRole)
        if not nueva_ruta:
            self._mostrar_estado_sin_nota()
            return

        if nueva_ruta == self.ruta_actual and self.ruta_actual is not None:
            return

        # Guardar en silencio antes de cambiar de nota (respetando autosave sin diálogo contradictorio)
        if self.modificado and self.ruta_actual and not (self.filtro_categoria == "papelera") and not self.modo_preview:
            if self.autosave_timer.isActive():
                self.autosave_timer.stop()
            exito = self.guardar_nota(silencioso=True)
            if not exito:
                QMessageBox.warning(self, "Error al guardar", "No se pudieron guardar los cambios en la nota.")

        self.mostrar_contenido(nueva_ruta, dar_foco=True)

    def mostrar_contenido(self, item_o_ruta=None, dar_foco: bool = True):
        if isinstance(item_o_ruta, Path):
            ruta = item_o_ruta
        elif isinstance(item_o_ruta, QModelIndex):
            ruta = item_o_ruta.data(NoteRoles.PathRole)
        else:
            idx = self.lista_notas.currentIndex()
            ruta = idx.data(NoteRoles.PathRole) if idx.isValid() else None

        if not ruta:
            self._mostrar_estado_sin_nota()
            return

        self.ruta_actual = ruta
        if not self.ruta_actual.exists():
            self.statusBar().showMessage(f"El archivo '{self.ruta_actual.name}' no existe.", 4000)
            self._mostrar_estado_sin_nota()
            self.cargar_lista_notas()
            return

        contenido = storage.leer_nota(self.ruta_actual)
        titulo, _ = storage.obtener_metadatos(self.ruta_actual)
        self.lbl_titulo_actual.setText(titulo)

        es_papelera = (self.filtro_categoria == "papelera")
        self.editor_texto.setEnabled(True)
        self.editor_texto.setPlaceholderText("")
        self.btn_preview.setEnabled(not es_papelera)
        self.btn_exportar.setEnabled(True)
        self.btn_eliminar.setEnabled(not es_papelera)

        self._cargando_texto = True
        if self.modo_preview and not es_papelera:
            self.editor_texto.setMarkdown(contenido)
            self.editor_texto.setReadOnly(True)
        else:
            self.editor_texto.setPlainText(contenido)
            self.editor_texto.setReadOnly(es_papelera)
        self._cargando_texto = False

        self.modificado = False
        self._actualizar_contador()

        query = self.buscador.text().strip()
        if query:
            self.resaltar_coincidencias(query)

        if not es_papelera:
            self.settings.setValue("ultima_nota", str(self.ruta_actual))

        if dar_foco and not es_papelera and not self.modo_preview:
            self.editor_texto.setFocus()
            cursor = self.editor_texto.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor_texto.setTextCursor(cursor)

    # --- BÚSQUEDA Y FILTRADO CON DEBOUNCE (~250ms) Y TRABAJADOR EN HILO ---
    def al_cambiar_busqueda(self):
        query = self.buscador.text().strip()
        # Filtrado instantáneo mediante QSortFilterProxyModel
        self.proxy_model.set_filtro_busqueda(query)
        self.resaltar_coincidencias(query)
        self.timer_busqueda.start(250)

    def _disparar_busqueda(self):
        query = self.buscador.text().strip()
        self._query_id_actual += 1

        archivos = storage.listar_notas()
        tag_filtro = self.filtro_categoria[4:] if self.filtro_categoria.startswith("tag:") else None
        self.solicitar_busqueda.emit(archivos, query, tag_filtro, self._query_id_actual)

    def _al_recibir_resultados_busqueda(self, coincidencias: list, query: str, query_id: int):
        # Descartar resultados obsoletos
        if query_id != self._query_id_actual:
            return

        if query:
            self.proxy_model.set_filtro_busqueda(query, coincidencias=set(coincidencias))
        else:
            self.proxy_model.set_filtro_busqueda("")

        self.resaltar_coincidencias(query)

    def filtrar_notas(self, texto: str):
        """Búsqueda inmediata para llamadas directas o pruebas."""
        query = texto.strip()
        tag_filtro = self.filtro_categoria[4:] if self.filtro_categoria.startswith("tag:") else None
        coincidencias = set(storage.buscar_en_notas(query, None, tag_filtro))
        self.proxy_model.set_filtro_busqueda(query, coincidencias=coincidencias)
        self.resaltar_coincidencias(query)

        self.resaltar_coincidencias(query)

    def al_cambiar_orden(self):
        idx = self.combo_orden.currentIndex()
        self.settings.setValue("orden_idx", idx)
        self.cargar_lista_notas(seleccionar_ruta=self.ruta_actual)

    def resaltar_coincidencias(self, texto_busqueda: str):
        extra_selections = []
        texto = texto_busqueda.strip()
        if not texto or self.modo_preview:
            self.editor_texto.setExtraSelections(extra_selections)
            return

        doc = self.editor_texto.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(0)

        formato = QTextCharFormat()
        formato.setBackground(QColor("#665c00" if self.tema_actual == "dark" else "#fff3a8"))
        formato.setForeground(QColor("#ffffff" if self.tema_actual == "dark" else "#1f2328"))

        while True:
            cursor = doc.find(texto, cursor)
            if cursor.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = formato
            extra_selections.append(sel)

        self.editor_texto.setExtraSelections(extra_selections)

    # --- CREACIÓN, RENOMBRADO, DUPLICADO, ETIQUETAS Y ELIMINACIÓN ---
    def crear_nueva_nota(self):
        if self.filtro_categoria == "papelera":
            self.nav_list.setCurrentRow(0)

        if self.modificado and self.ruta_actual and not self.modo_preview:
            self.autosave_timer.stop()
            self.guardar_nota(silencioso=True)

        etiquetas = []
        if isinstance(QInputDialog.getText, MagicMock):
            titulo, ok = QInputDialog.getText(self, "Nueva Nota", "Título de la nota:")
            if not ok or not titulo.strip():
                return
            titulo = titulo.strip()
        else:
            todas = storage.listar_todas_etiquetas(storage.listar_notas())
            dlg = NuevaNotaDialog(self, todas_etiquetas=todas)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            titulo, etiquetas = dlg.obtener_datos()
            if not titulo:
                return

        self._ignorando_watcher = True
        try:
            ruta = storage.crear_nota(titulo, etiquetas=etiquetas)
        finally:
            self._ignorando_watcher = False

        if not ruta:
            self.statusBar().showMessage("Error al crear la nota.", 4000)
            return

        # Si estaba en vista previa, volver al modo edición
        if self.modo_preview:
            self.modo_preview = False
            self.btn_preview.setChecked(False)
            self.btn_preview.setIcon(get_icon("preview", self.tema_actual))

        self.cargar_lista_notas(seleccionar_ruta=ruta)
        self.mostrar_contenido(ruta, dar_foco=True)

        # Garantizar que el editor quede habilitado, editable y con foco/cursor al final
        self.editor_texto.setEnabled(True)
        self.editor_texto.setReadOnly(False)
        self.editor_texto.setFocus()
        cursor = self.editor_texto.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor_texto.setTextCursor(cursor)
        
        self.statusBar().showMessage(f"Nota '{titulo}' creada.", 3000)

    def importar_archivo_dialog(self):
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Importar nota", "", "Archivos de texto (*.txt *.md);;Todos los archivos (*)"
        )
        if not archivo:
            return
        self.importar_archivo(Path(archivo))

    def importar_archivo(self, ruta_origen: Path) -> Optional[Path]:
        if not ruta_origen or not ruta_origen.exists() or not ruta_origen.is_file():
            self.statusBar().showMessage(f"El archivo '{ruta_origen.name if ruta_origen else ''}' no existe.", 4000)
            return None

        try:
            contenido_bruto = ruta_origen.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.statusBar().showMessage(f"Error al leer '{ruta_origen.name}': {e}", 4000)
            return None

        # Título tomado del nombre del archivo
        titulo = ruta_origen.stem
        tags = storage.extraer_etiquetas(contenido_bruto)

        # Extraer el cuerpo si el archivo ya contenía encabezados de plantilla
        lineas = contenido_bruto.splitlines()
        idx_cuerpo = 0
        for i in range(min(5, len(lineas))):
            lin = lineas[i].strip()
            if lin.startswith("# ") or lin.startswith("Fecha:") or lin.startswith("Etiquetas:") or lin.startswith("Tags:"):
                idx_cuerpo = i + 1
            elif lin == "" and idx_cuerpo > 0:
                idx_cuerpo = i + 1
            else:
                break
        cuerpo = "\n".join(lineas[idx_cuerpo:]).strip() if idx_cuerpo > 0 else contenido_bruto

        if self.filtro_categoria == "papelera":
            self.nav_list.setCurrentRow(0)

        self._ignorando_watcher = True
        try:
            nueva_ruta = storage.crear_nota(titulo, contenido=cuerpo, etiquetas=tags)
        finally:
            self._ignorando_watcher = False

        if nueva_ruta:
            self.cargar_lista_notas(seleccionar_ruta=nueva_ruta)
            self.statusBar().showMessage(f"Nota '{titulo}' importada correctamente.", 3000)
            return nueva_ruta
        else:
            self.statusBar().showMessage("Error al importar la nota.", 4000)
            return None

    def duplicar_nota(self, ruta: Path) -> Optional[Path]:
        if not ruta or not ruta.exists():
            return None

        if self.modificado and self.ruta_actual == ruta:
            self.guardar_nota(silencioso=True)

        titulo_original, _ = storage.obtener_metadatos(ruta)
        contenido = storage.leer_nota(ruta)
        tags = storage.extraer_etiquetas(ruta)

        lineas = contenido.splitlines()
        idx_cuerpo = 0
        for i in range(min(5, len(lineas))):
            lin = lineas[i].strip()
            if lin.startswith("# ") or lin.startswith("Fecha:") or lin.startswith("Etiquetas:") or lin.startswith("Tags:"):
                idx_cuerpo = i + 1
            elif lin == "" and idx_cuerpo > 0:
                idx_cuerpo = i + 1
            else:
                break
        cuerpo = "\n".join(lineas[idx_cuerpo:]).strip() if idx_cuerpo > 0 else contenido

        nuevo_titulo = f"{titulo_original} (copia)"
        self._ignorando_watcher = True
        try:
            nueva_ruta = storage.crear_nota(nuevo_titulo, contenido=cuerpo, etiquetas=tags)
        finally:
            self._ignorando_watcher = False

        if nueva_ruta:
            self.cargar_lista_notas(seleccionar_ruta=nueva_ruta)
            self.statusBar().showMessage(f"Nota duplicada como '{nuevo_titulo}'.", 3000)
            return nueva_ruta
        else:
            self.statusBar().showMessage("Error al duplicar la nota.", 4000)
            return None

    def editar_etiquetas_nota(self, ruta: Path):
        if not ruta or not ruta.exists():
            return

        etiquetas_actuales = storage.extraer_etiquetas(ruta)
        todas_etiquetas = storage.listar_todas_etiquetas(storage.listar_notas())

        dlg = EditarEtiquetasDialog(
            self,
            etiquetas_actuales=etiquetas_actuales,
            todas_etiquetas=todas_etiquetas
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        nuevas_etiquetas = dlg.obtener_etiquetas()

        self._ignorando_watcher = True
        try:
            if self.ruta_actual == ruta:
                contenido_actual = self.editor_texto.toPlainText()
                nuevo_contenido = storage.actualizar_etiquetas_en_contenido(contenido_actual, nuevas_etiquetas)
                self._cargando_texto = True
                self.editor_texto.setPlainText(nuevo_contenido)
                self._cargando_texto = False
                self.guardar_nota(silencioso=True)
            else:
                contenido = storage.leer_nota(ruta)
                nuevo_contenido = storage.actualizar_etiquetas_en_contenido(contenido, nuevas_etiquetas)
                storage.guardar_nota(ruta, nuevo_contenido)
        finally:
            self._ignorando_watcher = False

        self._actualizar_etiquetas_barra_lateral()
        self.cargar_lista_notas(seleccionar_ruta=self.ruta_actual or ruta)
        self.statusBar().showMessage("Etiquetas actualizadas.", 2500)

    def renombrar_nota_seleccionada(self):
        item = self.lista_notas.currentItem()
        if not item:
            self.statusBar().showMessage("Selecciona una nota para renombrar.", 3000)
            return

        ruta = item.data(Qt.ItemDataRole.UserRole)
        if not ruta or not ruta.exists():
            return

        titulo_actual, _ = storage.obtener_metadatos(ruta)
        nuevo_titulo, ok = QInputDialog.getText(
            self, "Renombrar Nota", "Nuevo título:", text=titulo_actual
        )

        if ok and nuevo_titulo.strip() and nuevo_titulo.strip() != titulo_actual:
            if self.modificado and self.ruta_actual == ruta:
                self.guardar_nota(silencioso=True)

            self._ignorando_watcher = True
            try:
                nueva_ruta = storage.renombrar_nota(ruta, nuevo_titulo.strip())
            finally:
                self._ignorando_watcher = False

            if nueva_ruta:
                if self.ruta_actual == ruta:
                    self.ruta_actual = nueva_ruta
                    self.lbl_titulo_actual.setText(nuevo_titulo.strip())
                    if not self.modo_preview:
                        self._cargando_texto = True
                        self.editor_texto.setPlainText(storage.leer_nota(nueva_ruta))
                        self._cargando_texto = False
                
                self.cargar_lista_notas(seleccionar_ruta=nueva_ruta)
                self.statusBar().showMessage(f"Nota renombrada a '{nuevo_titulo.strip()}'.", 3000)
            else:
                self.statusBar().showMessage("Error al renombrar la nota.", 4000)

    def eliminar_nota_seleccionada(self):
        item_actual = self.lista_notas.currentItem()
        if not item_actual:
            self.statusBar().showMessage("Selecciona una nota de la lista.", 3000)
            return

        ruta = item_actual.data(Qt.ItemDataRole.UserRole)
        if not ruta:
            return

        titulo, _ = storage.obtener_metadatos(ruta)

        if self.filtro_categoria != "papelera":
            self._ignorando_watcher = True
            try:
                destino = storage.mover_a_papelera(ruta)
            finally:
                self._ignorando_watcher = False

            if destino:
                if self.ruta_actual == ruta:
                    self._cargando_texto = True
                    self.editor_texto.clear()
                    self._cargando_texto = False
                    self.ruta_actual = None
                    self.lbl_titulo_actual.setText("Sin nota seleccionada")
                    self.modificado = False
                self.cargar_lista_notas()

                # Mostrar acción Deshacer en la barra de estado (~5 s)
                self._ultima_nota_en_papelera = destino
                self._lbl_deshacer.setText(f"Nota '{titulo}' movida a la papelera.")
                self._widget_deshacer.setVisible(True)
                self.timer_deshacer.start(5000)
            else:
                self.statusBar().showMessage(f"Error al mover '{titulo}' a la papelera.", 4000)
        else:
            resp = QMessageBox.question(
                self, "Eliminar definitivamente",
                f"¿Deseas eliminar permanentemente '{titulo}' de la papelera?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.Yes:
                self._ignorando_watcher = True
                try:
                    storage.eliminar_nota(ruta)
                finally:
                    self._ignorando_watcher = False

                if self.ruta_actual == ruta:
                    self._cargando_texto = True
                    self.editor_texto.clear()
                    self._cargando_texto = False
                    self.ruta_actual = None
                    self.lbl_titulo_actual.setText("Sin nota seleccionada")
                self.cargar_lista_notas()
                self.statusBar().showMessage(f"Nota '{titulo}' eliminada definitivamente.", 3000)

    def _deshacer_mover_a_papelera(self):
        self.timer_deshacer.stop()
        self._widget_deshacer.setVisible(False)
        if self._ultima_nota_en_papelera and self._ultima_nota_en_papelera.exists():
            self._ignorando_watcher = True
            try:
                ruta_restaurada = storage.restaurar_nota_papelera(self._ultima_nota_en_papelera)
            finally:
                self._ignorando_watcher = False

            self._ultima_nota_en_papelera = None
            if ruta_restaurada:
                self.cargar_lista_notas(seleccionar_ruta=ruta_restaurada)
                self.statusBar().showMessage("Nota restaurada con éxito.", 3000)
            else:
                self.statusBar().showMessage("Error al deshacer movimiento a papelera.", 4000)

    def _ocultar_deshacer(self):
        self._widget_deshacer.setVisible(False)
        self._ultima_nota_en_papelera = None

    def restaurar_nota_seleccionada(self):
        item = self.lista_notas.currentItem()
        if not item:
            self.statusBar().showMessage("Selecciona una nota para restaurar.", 3000)
            return

        ruta = item.data(Qt.ItemDataRole.UserRole)
        if not ruta:
            return

        titulo, _ = storage.obtener_metadatos(ruta)
        restaurada = storage.restaurar_nota_papelera(ruta)
        if restaurada:
            self.statusBar().showMessage(f"Nota '{titulo}' restaurada exitosamente.", 3000)
            self._cargando_texto = True
            self.editor_texto.clear()
            self._cargando_texto = False
            self.ruta_actual = None
            self.cargar_lista_notas()
        else:
            self.statusBar().showMessage("Error al restaurar la nota.", 4000)

    def vaciar_papelera(self):
        resp = QMessageBox.question(
            self, "Vaciar Papelera",
            "¿Estás seguro de que deseas eliminar permanentemente todas las notas de la papelera?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            eliminados = storage.vaciar_papelera()
            self._cargando_texto = True
            self.editor_texto.clear()
            self._cargando_texto = False
            self.ruta_actual = None
            self.lbl_titulo_actual.setText("Sin nota seleccionada")
            self.cargar_lista_notas()
            self.statusBar().showMessage(f"Papelera vaciada ({eliminados} notas eliminadas).", 3500)

    # --- VISTA PREVIA MARKDOWN Y EXPORTACIÓN ---
    def alternar_vista_previa(self):
        if not self.ruta_actual or (self.filtro_categoria == "papelera"):
            return

        if not self.modo_preview:
            if self.modificado:
                self.guardar_nota(silencioso=True)

            contenido = storage.leer_nota(self.ruta_actual)
            self.modo_preview = True
            self.btn_preview.setChecked(True)
            self.btn_preview.setIcon(get_icon("edit", self.tema_actual))
            
            self._cargando_texto = True
            self.editor_texto.setMarkdown(contenido)
            self.editor_texto.setReadOnly(True)
            self._cargando_texto = False
            
            self.statusBar().showMessage("Vista previa Markdown activada", 2500)
        else:
            contenido = storage.leer_nota(self.ruta_actual)
            self.modo_preview = False
            self.btn_preview.setChecked(False)
            self.btn_preview.setIcon(get_icon("preview", self.tema_actual))
            
            self._cargando_texto = True
            self.editor_texto.setPlainText(contenido)
            self.editor_texto.setReadOnly(False)
            self._cargando_texto = False
            self.modificado = False
            
            self.statusBar().showMessage("Modo edición activado", 2500)

    def exportar_nota_actual(self):
        if not self.ruta_actual:
            self.statusBar().showMessage("Selecciona una nota para exportar.", 3000)
            return

        titulo, _ = storage.obtener_metadatos(self.ruta_actual)
        nombre_propuesto = f"{storage.sanear_nombre_archivo(titulo)}.pdf"
        
        filtros = "Documento PDF (*.pdf);;Archivo Markdown (*.md);;Archivo de Texto (*.txt)"
        ruta_salida_str, filtro_seleccionado = QFileDialog.getSaveFileName(
            self, "Exportar Nota", nombre_propuesto, filtros
        )

        if not ruta_salida_str:
            return

        ruta_salida = Path(ruta_salida_str)
        contenido = self.editor_texto.toPlainText() if not self.modo_preview else storage.leer_nota(self.ruta_actual)

        if ruta_salida.suffix.lower() == ".pdf" or "PDF" in filtro_seleccionado:
            formato = "pdf"
            if ruta_salida.suffix.lower() != ".pdf":
                ruta_salida = ruta_salida.with_suffix(".pdf")
        elif ruta_salida.suffix.lower() == ".md" or "Markdown" in filtro_seleccionado:
            formato = "md"
            if ruta_salida.suffix.lower() != ".md":
                ruta_salida = ruta_salida.with_suffix(".md")
        else:
            formato = "txt"
            if ruta_salida.suffix.lower() != ".txt":
                ruta_salida = ruta_salida.with_suffix(".txt")

        exito = storage.exportar_nota(contenido, ruta_salida, formato)
        if exito:
            self.statusBar().showMessage(f"Nota exportada correctamente a '{ruta_salida.name}'.", 3500)
        else:
            self.statusBar().showMessage(f"Error al exportar nota a '{ruta_salida.name}'.", 4000)

    # --- MENÚ CONTEXTUAL ---
    def mostrar_menu_contextual(self, pos: QPoint):
        idx = self.lista_notas.indexAt(pos)
        if not idx.isValid():
            return

        ruta = idx.data(NoteRoles.PathRole)
        if not ruta:
            return

        menu = QMenu(self)

        if self.filtro_categoria != "papelera":
            es_fijada = storage.es_nota_fijada(ruta.name)
            accion_pin = menu.addAction("Desfijar nota" if es_fijada else "Fijar nota arriba")
            accion_pin.setIcon(get_icon("unpin" if es_fijada else "pin", self.tema_actual))
            accion_pin.triggered.connect(lambda: self._toggle_pin(ruta, not es_fijada))

            accion_renombrar = menu.addAction("Renombrar (F2)")
            accion_renombrar.setIcon(get_icon("rename", self.tema_actual))
            accion_renombrar.triggered.connect(self.renombrar_nota_seleccionada)

            accion_duplicar = menu.addAction("Duplicar nota")
            accion_duplicar.setIcon(get_icon("new", self.tema_actual))
            accion_duplicar.triggered.connect(lambda: self.duplicar_nota(ruta))

            accion_etiquetas = menu.addAction("Editar etiquetas...")
            accion_etiquetas.setIcon(get_icon("tag", self.tema_actual))
            accion_etiquetas.triggered.connect(lambda: self.editar_etiquetas_nota(ruta))

            accion_exportar = menu.addAction("Exportar nota...")
            accion_exportar.setIcon(get_icon("export", self.tema_actual))
            accion_exportar.triggered.connect(self.exportar_nota_actual)

            menu.addSeparator()

            accion_eliminar = menu.addAction("Mover a papelera (Del)")
            accion_eliminar.setIcon(get_icon("trash", self.tema_actual))
            accion_eliminar.triggered.connect(self.eliminar_nota_seleccionada)
        else:
            accion_restaurar = menu.addAction("Restaurar nota")
            accion_restaurar.setIcon(get_icon("restore", self.tema_actual))
            accion_restaurar.triggered.connect(self.restaurar_nota_seleccionada)

            menu.addSeparator()

            accion_eliminar = menu.addAction("Eliminar definitivamente")
            accion_eliminar.setIcon(get_icon("empty", self.tema_actual))
            accion_eliminar.triggered.connect(self.eliminar_nota_seleccionada)

        menu.exec(self.lista_notas.mapToGlobal(pos))

    def _toggle_pin(self, ruta: Path, fijar: bool):
        storage.fijar_nota(ruta.name, fijar=fijar)
        self.cargar_lista_notas(seleccionar_ruta=self.ruta_actual)
        msg = "Nota fijada arriba." if fijar else "Nota desfijada."
        self.statusBar().showMessage(msg, 2500)

    # --- EVENTO DE CIERRE ---
    def closeEvent(self, event):
        if self.autosave_timer.isActive():
            self.autosave_timer.stop()
        if self.timer_watcher.isActive():
            self.timer_watcher.stop()
        if self.timer_deshacer.isActive():
            self.timer_deshacer.stop()

        # Guardar en silencio y avisar solo si falla
        if self.modificado and self.ruta_actual and (self.filtro_categoria != "papelera") and not self.modo_preview:
            exito = self.guardar_nota(silencioso=True)
            if not exito:
                resp = QMessageBox.warning(
                    self, "Error al guardar",
                    "No se pudieron guardar los cambios pendientes al salir. ¿Desea salir de todos modos?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if resp != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

        self.settings.setValue("geometria", self.saveGeometry())
        sizes = self.splitter.sizes()
        if len(sizes) == 3 and sizes[2] >= 200 and sizes[1] >= 150:
            self.settings.setValue("splitter", self.splitter.saveState())
        if self.ruta_actual and (self.filtro_categoria != "papelera"):
            self.settings.setValue("ultima_nota", str(self.ruta_actual))

        if hasattr(self, "thread_busqueda") and self.thread_busqueda.isRunning():
            self.thread_busqueda.quit()
            self.thread_busqueda.wait(1000)

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = NerdNotesApp()
    ventana.show()
    sys.exit(app.exec())
