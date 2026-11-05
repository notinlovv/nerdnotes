from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import QModelIndex, Qt, QRect, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath
from ui.notes_model import NoteRoles
from services.icon_service import get_icon

class NoteCardDelegate(QStyledItemDelegate):
    """
    Delegate personalizado para QListView que dibuja cada nota como una tarjeta
    con título, fecha, vista previa de una línea y etiquetas como pills/chips con QPainterPath,
    adaptada al tema claro u oscuro con jerarquía visual refinada.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tema = "dark"

    def set_tema(self, tema: str):
        self.tema = tema

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        tags = index.data(NoteRoles.TagsRole) or []
        if tags:
            return QSize(option.rect.width(), 74)
        return QSize(option.rect.width(), 64)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Margen de 4px con los bordes de la lista
        rect = option.rect.adjusted(4, 2, -4, -2)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # Paleta de colores según el tema
        if self.tema == "dark":
            bg_hover = QColor("#222226")
            bg_selected = QColor("#223045")
            text_title = QColor("#f4f4f5")
            text_date = QColor("#71717a")
            text_preview = QColor("#a1a1aa")
            accent_bar = QColor("#007acc")
            pill_bg = QColor("#2e2e35")
            pill_text = QColor("#a1a1aa")
        else:
            bg_hover = QColor("#f4f4f5")
            bg_selected = QColor("#e0edff")
            text_title = QColor("#18181b")
            text_date = QColor("#71717a")
            text_preview = QColor("#52525b")
            accent_bar = QColor("#2563eb")
            pill_bg = QColor("#e4e4e7")
            pill_text = QColor("#52525b")

        # Dibujar fondo de tarjeta con bordes redondeados (6px)
        if is_selected:
            painter.setBrush(bg_selected)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

            # Barra vertical de acento (3px de ancho) en el extremo izquierdo
            bar_rect = QRect(rect.left() + 2, rect.top() + 6, 3, rect.height() - 12)
            painter.setBrush(accent_bar)
            painter.drawRoundedRect(bar_rect, 1.5, 1.5)
        elif is_hover:
            painter.setBrush(bg_hover)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

        # Datos del modelo
        titulo = index.data(NoteRoles.TitleRole) or ""
        fecha = index.data(NoteRoles.DateRole) or ""
        preview = index.data(NoteRoles.PreviewRole) or ""
        fijada = bool(index.data(NoteRoles.PinnedRole))
        tags = index.data(NoteRoles.TagsRole) or []

        # Área interior con márgenes cómodos
        content_rect = rect.adjusted(12, 6, -10, -6)

        # 1. Fecha (alineada a la derecha en tono atenuado)
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
            pin_icon = get_icon("pin", self.tema)
            pin_rect = QRect(title_left, content_rect.top() + 2, 14, 14)
            pin_icon.paint(painter, pin_rect)
            title_left += 18

        title_width = (content_rect.right() - 90) - title_left
        title_rect = QRect(title_left, content_rect.top(), max(10, title_width), 18)
        metrics = painter.fontMetrics()
        elided_title = metrics.elidedText(titulo, Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        # 3. Extracto/snippet en tono secundario legible
        font_preview = QFont(option.font)
        font_preview.setPointSize(max(9, font_preview.pointSize() - 1))
        font_preview.setBold(False)
        painter.setFont(font_preview)
        painter.setPen(text_preview)

        preview_rect = QRect(content_rect.left(), content_rect.top() + 21, content_rect.width(), 17)
        metrics_p = painter.fontMetrics()
        elided_preview = metrics_p.elidedText(preview, Qt.TextElideMode.ElideRight, content_rect.width())
        painter.drawText(preview_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_preview)

        # 4. Renderizado de etiquetas como Chips/Pills con QPainterPath
        if tags:
            font_tag = QFont(option.font)
            font_tag.setPointSize(max(8, font_tag.pointSize() - 3))
            font_tag.setBold(False)
            painter.setFont(font_tag)
            metrics_tag = painter.fontMetrics()

            pill_h = 16
            pill_y = content_rect.top() + 41
            tag_x = content_rect.left()

            for t in tags:
                tag_str = str(t).strip()
                if not tag_str:
                    continue
                w_text = metrics_tag.horizontalAdvance(tag_str)
                pill_w = w_text + 12
                if tag_x + pill_w > content_rect.right():
                    break
                pill_rect = QRectF(tag_x, pill_y, pill_w, pill_h)
                pill_path = QPainterPath()
                pill_path.addRoundedRect(pill_rect, pill_h / 2, pill_h / 2)
                painter.fillPath(pill_path, pill_bg)
                painter.setPen(pill_text)
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, tag_str)
                tag_x += pill_w + 5

        painter.restore()
