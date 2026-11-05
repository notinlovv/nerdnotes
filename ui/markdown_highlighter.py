import re
from typing import Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import (
        QSyntaxHighlighter,
        QTextCharFormat,
        QFont,
        QColor,
        QTextDocument
    )
    _PYQT6_DISPONIBLE = True
except (ImportError, TypeError, AttributeError):
    _PYQT6_DISPONIBLE = False
    QSyntaxHighlighter = object
    QTextCharFormat = object
    QFont = object
    QColor = object
    QTextDocument = object


class MarkdownHighlighter(QSyntaxHighlighter if _PYQT6_DISPONIBLE else object):
    """
    Resaltador de sintaxis Markdown ligero y eficiente para NoteEditor.
    Aplica estilos en tiempo real para encabezados, negrita/cursiva,
    bloques e inline de código, tareas y citas sin saturar el hilo principal.
    """
    STATE_NORMAL = 0
    STATE_CODE_BLOCK = 1

    # Expresiones regulares precompiladas para máxima velocidad
    RE_HEADING = re.compile(r"^(#{1,6}\s+.*)$")
    RE_QUOTE = re.compile(r"^(>\s*.*)$")
    RE_CHECK_DONE = re.compile(r"^(\s*-\s*\[[xX]\]\s*)(.*)$")
    RE_CHECK_PENDING = re.compile(r"^(\s*-\s*\[\s*\]\s*)(.*)$")
    RE_LIST = re.compile(r"^(\s*[-*+]\s+|\s*\d+\.\s+)")
    RE_INLINE_CODE = re.compile(r"(`+)([^`]+?)\1")
    RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    RE_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*")
    RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
    RE_ITALIC = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")
    RE_TAG = re.compile(r"(?<!\S)#[a-zA-Z0-9_\u00c0-\u017f-]+")

    def __init__(self, parent_or_document=None, theme: str = "dark"):
        if _PYQT6_DISPONIBLE:
            super().__init__(parent_or_document)
        self.theme = theme
        self._init_formats()

    def set_theme(self, theme: str):
        """Actualiza la paleta cromática según el tema activo y re-resalta."""
        if self.theme != theme:
            self.theme = theme
            self._init_formats()
            if _PYQT6_DISPONIBLE and hasattr(self, "rehighlight"):
                self.rehighlight()

    def _init_formats(self):
        if not _PYQT6_DISPONIBLE:
            return

        is_dark = (self.theme == "dark")

        # 1. Encabezados
        self.fmt_heading = QTextCharFormat()
        self.fmt_heading.setFontWeight(QFont.Weight.Bold)
        self.fmt_heading.setForeground(QColor("#60a5fa" if is_dark else "#1d4ed8"))

        # 2. Negrita y Cursiva
        self.fmt_bold = QTextCharFormat()
        self.fmt_bold.setFontWeight(QFont.Weight.Bold)
        self.fmt_bold.setForeground(QColor("#f4f4f5" if is_dark else "#09090b"))

        self.fmt_italic = QTextCharFormat()
        self.fmt_italic.setFontItalic(True)
        self.fmt_italic.setForeground(QColor("#e4e4e7" if is_dark else "#18181b"))

        self.fmt_bold_italic = QTextCharFormat()
        self.fmt_bold_italic.setFontWeight(QFont.Weight.Bold)
        self.fmt_bold_italic.setFontItalic(True)
        self.fmt_bold_italic.setForeground(QColor("#f4f4f5" if is_dark else "#09090b"))

        # 3. Código inline
        self.fmt_inline_code = QTextCharFormat()
        self.fmt_inline_code.setFontFamily("monospace")
        self.fmt_inline_code.setBackground(QColor("#27272a" if is_dark else "#f4f4f5"))
        self.fmt_inline_code.setForeground(QColor("#f472b6" if is_dark else "#db2777"))

        # 4. Bloque de código multilínea
        self.fmt_code_block = QTextCharFormat()
        self.fmt_code_block.setFontFamily("monospace")
        self.fmt_code_block.setBackground(QColor("#202023" if is_dark else "#f4f5f7"))
        self.fmt_code_block.setForeground(QColor("#e4e4e7" if is_dark else "#18181b"))

        # 5. Checklists
        self.fmt_check_done_box = QTextCharFormat()
        self.fmt_check_done_box.setFontWeight(QFont.Weight.Bold)
        self.fmt_check_done_box.setForeground(QColor("#10b981" if is_dark else "#059669"))

        self.fmt_check_done_text = QTextCharFormat()
        self.fmt_check_done_text.setFontStrikeOut(True)
        self.fmt_check_done_text.setForeground(QColor("#71717a"))

        self.fmt_check_pending_box = QTextCharFormat()
        self.fmt_check_pending_box.setFontWeight(QFont.Weight.Bold)
        self.fmt_check_pending_box.setForeground(QColor("#a1a1aa" if is_dark else "#52525b"))

        # 6. Listas
        self.fmt_list_bullet = QTextCharFormat()
        self.fmt_list_bullet.setFontWeight(QFont.Weight.Bold)
        self.fmt_list_bullet.setForeground(QColor("#60a5fa" if is_dark else "#2563eb"))

        # 7. Citas
        self.fmt_quote = QTextCharFormat()
        self.fmt_quote.setFontItalic(True)
        self.fmt_quote.setForeground(QColor("#a1a1aa" if is_dark else "#52525b"))

        # 8. Enlaces
        self.fmt_link_text = QTextCharFormat()
        self.fmt_link_text.setFontUnderline(True)
        self.fmt_link_text.setForeground(QColor("#38bdf8" if is_dark else "#0284c7"))

        self.fmt_link_url = QTextCharFormat()
        self.fmt_link_url.setForeground(QColor("#71717a"))

        # 9. Etiquetas
        self.fmt_tag = QTextCharFormat()
        self.fmt_tag.setFontWeight(QFont.Weight.DemiBold)
        self.fmt_tag.setForeground(QColor("#a78bfa" if is_dark else "#7c3aed"))

    def highlightBlock(self, text: str):
        if not _PYQT6_DISPONIBLE:
            return

        # 1. Bloques de código multilínea
        prev_state = self.previousBlockState()
        in_code_block = (prev_state == self.STATE_CODE_BLOCK)
        stripped = text.strip()
        is_fence = stripped.startswith("```")

        if in_code_block:
            self.setFormat(0, len(text), self.fmt_code_block)
            if is_fence:
                self.setCurrentBlockState(self.STATE_NORMAL)
            else:
                self.setCurrentBlockState(self.STATE_CODE_BLOCK)
            return
        else:
            if is_fence:
                self.setFormat(0, len(text), self.fmt_code_block)
                self.setCurrentBlockState(self.STATE_CODE_BLOCK)
                return
            else:
                self.setCurrentBlockState(self.STATE_NORMAL)

        # 2. Encabezados (# a ######)
        m_head = self.RE_HEADING.match(text)
        if m_head:
            self.setFormat(0, len(text), self.fmt_heading)
            return

        # 3. Citas (> ...)
        m_quote = self.RE_QUOTE.match(text)
        if m_quote:
            self.setFormat(0, len(text), self.fmt_quote)
            return

        # 4. Checklists (- [x] o - [ ])
        m_check_done = self.RE_CHECK_DONE.match(text)
        if m_check_done:
            prefix_len = len(m_check_done.group(1))
            self.setFormat(0, prefix_len, self.fmt_check_done_box)
            if len(text) > prefix_len:
                self.setFormat(prefix_len, len(text) - prefix_len, self.fmt_check_done_text)
            return

        m_check_pending = self.RE_CHECK_PENDING.match(text)
        if m_check_pending:
            prefix_len = len(m_check_pending.group(1))
            self.setFormat(0, prefix_len, self.fmt_check_pending_box)

        # 5. Listas viñetas / numéricas
        m_list = self.RE_LIST.match(text)
        if m_list and not m_check_pending:
            self.setFormat(0, len(m_list.group(1)), self.fmt_list_bullet)

        # 6. Código inline (`...`)
        for m in self.RE_INLINE_CODE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_inline_code)

        # 7. Enlaces ([texto](url))
        for m in self.RE_LINK.finditer(text):
            t_start = m.start()
            t_end = m.start(2) + len(m.group(2)) + 1
            self.setFormat(t_start, t_end - t_start, self.fmt_link_text)
            url_start = t_end
            self.setFormat(url_start, m.end() - url_start, self.fmt_link_url)

        # 8. Negrita y Cursiva
        for m in self.RE_BOLD_ITALIC.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_bold_italic)

        for m in self.RE_BOLD.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_bold)

        for m in self.RE_ITALIC.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_italic)

        # 9. Etiquetas (#tag)
        for m in self.RE_TAG.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_tag)

