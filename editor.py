import re
import subprocess
from pathlib import Path
from typing import Optional, Callable

import config

# Soporte opcional para PyQt6 para no romper ejecución de CLI en entornos sin interfaz
try:
    from PyQt6.QtWidgets import QTextEdit, QLineEdit, QWidget, QHBoxLayout, QPushButton, QFrame
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QTextBlockFormat, QTextCursor, QFont, QKeySequence
    _PYQT6_DISPONIBLE = True
except (ImportError, TypeError, AttributeError):
    _PYQT6_DISPONIBLE = False
    QTextEdit = object
    QLineEdit = object
    QWidget = object
    QHBoxLayout = object
    QPushButton = object
    QFrame = object
    QObject = object
    QTextBlockFormat = object
    QTextCursor = object
    QFont = object
    QKeySequence = object
    class Qt:
        class Key:
            Key_Return = 0
            Key_Enter = 0
            Key_B = 0
            Key_I = 0
            Key_K = 0
            Key_1 = 0
            Key_2 = 0
            Key_3 = 0
            Key_L = 0
            Key_T = 0
        class KeyboardModifier:
            ControlModifier = 0
            ShiftModifier = 0
        class FocusPolicy:
            NoFocus = 0
        class CursorShape:
            PointingHandCursor = 0

    def pyqtSignal(*args, **kwargs):
        class _DummySignal:
            def connect(self, *a, **k): pass
            def emit(self, *a, **k): pass
        return _DummySignal()

    class QTimer:
        def __init__(self, *args, **kwargs): pass
        def setSingleShot(self, *args): pass
        def setInterval(self, *args): pass
        def start(self, *args): pass
        def stop(self): pass
        def isActive(self): return False
        timeout = pyqtSignal()

def abrir_editor(ruta: Path) -> bool:
    """
    Abre la ruta especificada con el editor configurado,
    con fallback real: DEFAULT_EDITOR/EDITOR -> nano -> vi.
    """
    candidatos = []
    if config.DEFAULT_EDITOR:
        candidatos.append(config.DEFAULT_EDITOR)
    for alt in ['nano', 'vi']:
        if alt not in candidatos:
            candidatos.append(alt)

    for i, editor in enumerate(candidatos):
        if i > 0:
            print(f"Usando {editor} como alternativa")
        try:
            subprocess.call([editor, str(ruta)])
            return True
        except FileNotFoundError:
            print(f"No se encontró el editor '{editor}'")
            continue
        except Exception as e:
            print(f"Error al abrir editor '{editor}': {e}")
            continue

    print("Error: No se encontró ningún editor disponible (probados: EDITOR, nano, vi).")
    return False

def editar_nota(ruta: Path) -> None:
    if not ruta.exists():
        print("NO SE ENCONTRÓ NINGUNA NOTA")
        return 
    abrir_editor(ruta)


class NoteTitleEdit(QLineEdit):
    """
    Campo de título plano y sin bordes, con tipografía 1080p (22px, semi-bold 600).
    Sincroniza su cambio con storage al presionar Enter o perder foco.
    """
    def __init__(self, parent=None):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
            self.setObjectName("editor_titulo")
            self.setPlaceholderText("Título de la nota...")
            font = self.font()
            font.setPixelSize(22)
            font.setWeight(QFont.Weight.DemiBold)
            self.setFont(font)

    def keyPressEvent(self, event):
        if _PYQT6_DISPONIBLE:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.clearFocus()
                event.accept()
                return
            super().keyPressEvent(event)


class NoteEditor(QTextEdit):
    """
    Componente de edición de notas con soporte para autoguardado inteligente,
    debouncing configurable (500 ms por defecto), indicador de estado sucio,
    formato Markdown inteligente, atajos de teclado y resaltado en tiempo real.
    """
    INTERVALO_AUTOGUARDADO: int = 500

    ha_cambiado = pyqtSignal(bool)
    guardar_solicitado = pyqtSignal(str)
    autoguardado_realizado = pyqtSignal()

    def __init__(self, parent=None, callback_guardar: Optional[Callable[[str], bool]] = None, intervalo_ms: int = 500):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
            self.document().setDocumentMargin(24)
            self._aplicar_formato_interlineado()
            try:
                from ui.markdown_highlighter import MarkdownHighlighter
                self.highlighter = MarkdownHighlighter(self.document())
            except Exception:
                self.highlighter = None
        else:
            self.highlighter = None

        self.callback_guardar = callback_guardar
        self._is_dirty: bool = False
        self._ignorando_cambios: bool = False

        self.autosave_timer = QTimer(self if _PYQT6_DISPONIBLE else None)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(intervalo_ms)
        if _PYQT6_DISPONIBLE:
            self.autosave_timer.timeout.connect(self._al_timeout_autosave)
            self.textChanged.connect(self._al_cambiar_texto)

    def setPlainText(self, text: str):
        if _PYQT6_DISPONIBLE:
            super().setPlainText(text)
            self._aplicar_formato_interlineado()

    def set_tema(self, tema: str):
        """Actualiza el tema del resaltador de sintaxis Markdown."""
        if self.highlighter and hasattr(self.highlighter, "set_theme"):
            self.highlighter.set_theme(tema)

    def _aplicar_formato_interlineado(self):
        if not _PYQT6_DISPONIBLE:
            return
        try:
            cursor = self.textCursor()
            pos = cursor.position()
            cursor.beginEditBlock()
            bf = QTextBlockFormat()
            bf.setLineHeight(160, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.setBlockFormat(bf)
            cursor.endEditBlock()
            cursor.setPosition(min(pos, len(self.toPlainText())))
            self.setTextCursor(cursor)
        except Exception:
            pass

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, valor: bool):
        val_bool = bool(valor)
        if self._is_dirty != val_bool:
            self._is_dirty = val_bool
            self.ha_cambiado.emit(val_bool)

    @property
    def ha_cambiado_estado(self) -> bool:
        """Alias para is_dirty."""
        return self._is_dirty

    @property
    def modificado(self) -> bool:
        return self._is_dirty

    @modificado.setter
    def modificado(self, valor: bool):
        self.is_dirty = valor

    def cargar_texto(self, texto: str):
        """Carga texto sin marcar como sucio ni iniciar el temporizador."""
        self._ignorando_cambios = True
        try:
            if hasattr(self.autosave_timer, "isActive") and self.autosave_timer.isActive():
                self.autosave_timer.stop()
            if _PYQT6_DISPONIBLE:
                self.setPlainText(texto)
            self._is_dirty = False
            self.ha_cambiado.emit(False)
        finally:
            self._ignorando_cambios = False

    def _al_cambiar_texto(self):
        if self._ignorando_cambios:
            return
        if _PYQT6_DISPONIBLE and self.isReadOnly():
            return
        self.is_dirty = True
        self.autosave_timer.start(self.INTERVALO_AUTOGUARDADO)

    def _al_timeout_autosave(self):
        if self._is_dirty:
            if not _PYQT6_DISPONIBLE or not self.isReadOnly():
                exito = self.flush()
                if exito:
                    self.autoguardado_realizado.emit()

    def flush(self) -> bool:
        """Fuerza el guardado inmediato de cambios pendientes deteniendo el temporizador."""
        if hasattr(self.autosave_timer, "isActive") and self.autosave_timer.isActive():
            self.autosave_timer.stop()

        if not self._is_dirty:
            return True

        if _PYQT6_DISPONIBLE and self.isReadOnly():
            return True

        contenido = self.toPlainText() if _PYQT6_DISPONIBLE else ""
        exito = True
        if self.callback_guardar:
            try:
                res = self.callback_guardar(contenido)
                if res is False:
                    exito = False
            except Exception:
                exito = False

        if exito:
            self.is_dirty = False
            self.guardar_solicitado.emit(contenido)
        return exito

    def aplicar_formato(self, tipo: str):
        """
        Aplica formato Markdown contextualmente con manipulación inteligente del cursor.
        Soporta negrita, cursiva, encabezados (h1, h2, h3), listas, checklists,
        bloques de código, citas y enlaces, agrupados en un solo bloque de edición (Undo atómico).
        """
        if not _PYQT6_DISPONIBLE or self.isReadOnly():
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            if tipo in ("negrita", "bold", "cursiva", "italic"):
                simbolo = "**" if tipo in ("negrita", "bold") else "*"
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
                    self.setTextCursor(cursor)
                    return

            elif tipo in ("h1", "h2", "h3", "encabezado"):
                prefijo_map = {"h1": "# ", "h2": "## ", "h3": "### ", "encabezado": "# "}
                prefijo = prefijo_map.get(tipo, "# ")
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

            elif tipo in ("lista", "list", "checklist", "tarea"):
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
                es_lista_simple = tipo in ("lista", "list")
                for lin in lineas:
                    if es_lista_simple:
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

            elif tipo in ("cita", "quote"):
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
                    if lin.startswith("> "):
                        nuevas.append(lin[2:])
                    elif lin.startswith(">"):
                        nuevas.append(lin[1:])
                    else:
                        nuevas.append("> " + lin)
                texto_insertado = "\n".join(nuevas)
                cursor.insertText(texto_insertado)
                cursor.setPosition(start_pos)
                cursor.setPosition(start_pos + len(texto_insertado), QTextCursor.MoveMode.KeepAnchor)

            elif tipo in ("codigo", "code"):
                if cursor.hasSelection():
                    sel_text = cursor.selectedText()
                    start_sel = cursor.selectionStart()
                    if "\u2029" in sel_text or "\n" in sel_text:
                        nuevo_texto = f"```\n{sel_text}\n```"
                        cursor.insertText(nuevo_texto)
                        cursor.setPosition(start_sel)
                        cursor.setPosition(start_sel + len(nuevo_texto), QTextCursor.MoveMode.KeepAnchor)
                    else:
                        if sel_text.startswith("`") and sel_text.endswith("`") and len(sel_text) >= 2:
                            nuevo_texto = sel_text[1:-1]
                        else:
                            nuevo_texto = f"`{sel_text}`"
                        cursor.insertText(nuevo_texto)
                        cursor.setPosition(start_sel)
                        cursor.setPosition(start_sel + len(nuevo_texto), QTextCursor.MoveMode.KeepAnchor)
                else:
                    pos = cursor.position()
                    cursor.insertText("```\n\n```")
                    cursor.setPosition(pos + 4)
                    self.setTextCursor(cursor)
                    return

            elif tipo in ("enlace", "link"):
                if cursor.hasSelection():
                    sel_text = cursor.selectedText()
                    start_sel = cursor.selectionStart()
                    if sel_text.startswith("http://") or sel_text.startswith("https://"):
                        nuevo_texto = f"[enlace]({sel_text})"
                        cursor.insertText(nuevo_texto)
                        cursor.setPosition(start_sel + 1)
                        cursor.setPosition(start_sel + 7, QTextCursor.MoveMode.KeepAnchor)
                    else:
                        nuevo_texto = f"[{sel_text}](url)"
                        cursor.insertText(nuevo_texto)
                        url_start = start_sel + len(sel_text) + 3
                        cursor.setPosition(url_start)
                        cursor.setPosition(url_start + 3, QTextCursor.MoveMode.KeepAnchor)
                else:
                    pos = cursor.position()
                    cursor.insertText("[texto](url)")
                    cursor.setPosition(pos + 1)
                    cursor.setPosition(pos + 6, QTextCursor.MoveMode.KeepAnchor)
        finally:
            cursor.endEditBlock()
            self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        if _PYQT6_DISPONIBLE:
            mods = event.modifiers()
            key = event.key()
            if mods == Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_B:
                    self.aplicar_formato("negrita")
                    event.accept()
                    return
                elif key == Qt.Key.Key_I:
                    self.aplicar_formato("cursiva")
                    event.accept()
                    return
                elif key == Qt.Key.Key_K:
                    self.aplicar_formato("enlace")
                    event.accept()
                    return
                elif key == Qt.Key.Key_1:
                    self.aplicar_formato("h1")
                    event.accept()
                    return
                elif key == Qt.Key.Key_2:
                    self.aplicar_formato("h2")
                    event.accept()
                    return
                elif key == Qt.Key.Key_3:
                    self.aplicar_formato("h3")
                    event.accept()
                    return
            elif mods == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                if key == Qt.Key.Key_L:
                    self.aplicar_formato("lista")
                    event.accept()
                    return
                elif key == Qt.Key.Key_T:
                    self.aplicar_formato("checklist")
                    event.accept()
                    return
            super().keyPressEvent(event)


class NoteFormatToolbar(QWidget if _PYQT6_DISPONIBLE else object):
    """
    Barra de herramientas sutil de formato Markdown para NoteEditor.
    Botones planos con focus policy NoFocus para preservar la selección activa en el editor.
    """
    def __init__(self, editor: Optional[NoteEditor] = None, parent=None):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
            self.setObjectName("toolbar_formato")
            self.editor = editor
            self._init_ui()

    def set_editor(self, editor: NoteEditor):
        self.editor = editor

    def _init_ui(self):
        if not _PYQT6_DISPONIBLE:
            return

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        # Formato de texto
        self.btn_bold = self._crear_boton("B", "Negrita (Ctrl+B)", "btn_bold", "negrita", bold=True)
        self.btn_italic = self._crear_boton("I", "Cursiva (Ctrl+I)", "btn_italic", "cursiva", italic=True)
        self.btn_h1 = self._crear_boton("H1", "Encabezado 1 (Ctrl+1)", "btn_h1", "h1")
        self.btn_h2 = self._crear_boton("H2", "Encabezado 2 (Ctrl+2)", "btn_h2", "h2")

        layout.addWidget(self.btn_bold)
        layout.addWidget(self.btn_italic)
        layout.addWidget(self.btn_h1)
        layout.addWidget(self.btn_h2)

        layout.addWidget(self._crear_separador())

        # Listas y tareas
        self.btn_bullet = self._crear_boton("• Lista", "Lista con viñetas (Ctrl+Shift+L)", "btn_bullet", "lista")
        self.btn_checklist = self._crear_boton("☑ Tarea", "Lista de tareas (Ctrl+Shift+T)", "btn_checklist", "checklist")

        layout.addWidget(self.btn_bullet)
        layout.addWidget(self.btn_checklist)

        layout.addWidget(self._crear_separador())

        # Estructura y enlaces
        self.btn_quote = self._crear_boton("” Cita", "Cita (>)", "btn_quote", "cita")
        self.btn_code = self._crear_boton("</> Código", "Bloque de código (```)", "btn_code", "codigo")
        self.btn_link = self._crear_boton("🔗 Enlace", "Insertar enlace (Ctrl+K)", "btn_link", "enlace")

        layout.addWidget(self.btn_quote)
        layout.addWidget(self.btn_code)
        layout.addWidget(self.btn_link)

        layout.addStretch(1)

    def _crear_boton(self, texto: str, tooltip: str, obj_name: str, tipo_formato: str, bold=False, italic=False) -> QPushButton:
        btn = QPushButton(texto)
        btn.setObjectName(obj_name)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(28)
        btn.setMinimumWidth(28)

        font = btn.font()
        font.setPointSize(11)
        if bold:
            font.setBold(True)
        if italic:
            font.setItalic(True)
        btn.setFont(font)

        btn.clicked.connect(lambda: self._aplicar(tipo_formato))
        return btn

    def _crear_separador(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("toolbar_separador")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedWidth(1)
        sep.setFixedHeight(14)
        return sep

    def _aplicar(self, tipo: str):
        if self.editor and hasattr(self.editor, "aplicar_formato"):
            self.editor.aplicar_formato(tipo)


class NoteEditorCanvas(QWidget if _PYQT6_DISPONIBLE else object):
    """
    Contenedor centrado de lectura y escritura para NoteEditor.
    Confinado entre 760px y 840px (800px por defecto) para optimizar
    la longitud de línea de lectura (65-80 caracteres) en pantallas 1080p.
    """
    MAX_CANVAS_WIDTH = 800

    def __init__(self, parent=None, max_width: int = 800):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
            self.setObjectName("container_documento")
            self.setMaximumWidth(max_width)


class AutoSaveDebouncer(QObject):
    """
    Manejador desacoplado de temporizador de autoguardado (debouncing)
    con control de estado sucio y flush inmediato.
    """
    ha_cambiado = pyqtSignal(bool)
    guardar_solicitado = pyqtSignal()

    def __init__(self, callback_guardar: Optional[Callable[[], bool]] = None, intervalo_ms: int = 500, parent=None):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent)
        self.callback_guardar = callback_guardar
        self._is_dirty: bool = False
        self.timer = QTimer(self if _PYQT6_DISPONIBLE else None)
        self.timer.setSingleShot(True)
        self.timer.setInterval(intervalo_ms)
        if _PYQT6_DISPONIBLE:
            self.timer.timeout.connect(self._al_timeout)

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, valor: bool):
        val_bool = bool(valor)
        if self._is_dirty != val_bool:
            self._is_dirty = val_bool
            self.ha_cambiado.emit(val_bool)

    def registrar_cambio(self):
        self.is_dirty = True
        self.timer.start()

    def _al_timeout(self):
        if self._is_dirty:
            self.flush()

    def flush(self) -> bool:
        if hasattr(self.timer, "isActive") and self.timer.isActive():
            self.timer.stop()
        if not self._is_dirty:
            return True
        exito = True
        if self.callback_guardar:
            try:
                res = self.callback_guardar()
                if res is False:
                    exito = False
            except Exception:
                exito = False
        if exito:
            self.is_dirty = False
            self.guardar_solicitado.emit()
        return exito


# Aliases
Editor = NoteEditor
AutoSaveEditor = NoteEditor
EditorController = AutoSaveDebouncer
TitleEdit = NoteTitleEdit
FormatToolbar = NoteFormatToolbar
MarkdownToolbar = NoteFormatToolbar
EditorCanvas = NoteEditorCanvas
NoteDocumentContainer = NoteEditorCanvas
