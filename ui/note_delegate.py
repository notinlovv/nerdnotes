from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import QModelIndex, Qt, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QFont
from ui.notes_model import NoteRoles
from services.icon_service import get_icon

class NoteCardDelegate(QStyledItemDelegate):
    """
    Delegate personalizado para QListView que dibuja cada nota como una tarjeta
    con título, fecha y vista previa de una línea, adaptada al tema claro u oscuro.
    Usa iconos vectoriales SVG para fijadas y etiquetas en lugar de caracteres emoji.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tema = "dark"

    def set_tema(self, tema: str):
        self.tema = tema

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), 66)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect.adjusted(6, 3, -6, -3)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # Paleta de colores según el tema
        if self.tema == "dark":
            bg_hover = QColor("#262626")
            bg_selected = QColor("#094771")
            text_title = QColor("#ffffff") if is_selected else QColor("#e0e0e0")
            text_date = QColor("#7d8590") if not is_selected else QColor("#a6ccf5")
            text_preview = QColor("#9e9e9e") if not is_selected else QColor("#d0e2ff")
            text_tags = QColor("#569cd6") if not is_selected else QColor("#8ec07c")
            accent_bar = QColor("#007acc")
        else:
            bg_hover = QColor("#eaeef2")
            bg_selected = QColor("#d0e2ff")
            text_title = QColor("#0043ce") if is_selected else QColor("#1f2328")
            text_date = QColor("#656d76")
            text_preview = QColor("#57606a") if not is_selected else QColor("#1f2328")
            text_tags = QColor("#0969da")
            accent_bar = QColor("#0066cc")

        # Dibujar fondo de tarjeta
        if is_selected:
            painter.setBrush(bg_selected)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

            # Barra vertical de acento a la izquierda
            bar_rect = QRect(rect.left() + 2, rect.top() + 8, 3, rect.height() - 16)
            painter.setBrush(accent_bar)
            painter.drawRoundedRect(bar_rect, 1.5, 1.5)
        elif is_hover:
            painter.setBrush(bg_hover)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

        # Datos del modelo
        titulo = index.data(NoteRoles.TitleRole) or ""
        fecha = index.data(NoteRoles.DateRole) or ""
        preview = index.data(NoteRoles.PreviewRole) or ""
        fijada = bool(index.data(NoteRoles.PinnedRole))
        tags = index.data(NoteRoles.TagsRole) or []

        # Área interior con márgenes cómodos
        content_rect = rect.adjusted(12, 7, -12, -7)

        # 1. Fecha (alineada a la derecha)
        font_date = QFont(option.font)
        font_date.setPointSize(max(8, font_date.pointSize() - 2))
        painter.setFont(font_date)
        painter.setPen(text_date)

        date_rect = QRect(content_rect.right() - 85, content_rect.top(), 85, 18)
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, fecha)

        # 2. Título (en negrita a la izquierda, con icono de pin SVG si está fijada)
        font_title = QFont(option.font)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.setPen(text_title)

        title_left = content_rect.left()
        if fijada:
            # Dibujar icono SVG de pin
            pin_icon = get_icon("pin", self.tema)
            pin_rect = QRect(title_left, content_rect.top() + 2, 14, 14)
            pin_icon.paint(painter, pin_rect)
            title_left += 18

        title_width = (content_rect.right() - 90) - title_left
        title_rect = QRect(title_left, content_rect.top(), max(10, title_width), 18)
        metrics = painter.fontMetrics()
        elided_title = metrics.elidedText(titulo, Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        # 3. Vista previa de una línea y etiquetas
        font_preview = QFont(option.font)
        font_preview.setPointSize(max(9, font_preview.pointSize() - 1))
        font_preview.setBold(False)
        painter.setFont(font_preview)
        painter.setPen(text_preview)

        preview_full = preview
        if tags:
            preview_full = f"{preview}   [{', '.join(tags)}]"

        preview_rect = QRect(content_rect.left(), content_rect.top() + 22, content_rect.width(), 18)
        metrics_p = painter.fontMetrics()
        elided_preview = metrics_p.elidedText(preview_full, Qt.TextElideMode.ElideRight, content_rect.width())
        painter.drawText(preview_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_preview)

        painter.restore()
