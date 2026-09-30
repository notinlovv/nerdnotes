import sys
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QHBoxLayout, QVBoxLayout, QListWidget, 
                             QTextEdit, QPushButton, QInputDialog, QMessageBox, QLineEdit)
import storage 

class NerdNotesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NerdNotes - GUI")
        self.resize(800, 600)
        
        # Widget principal y Layout base
        widget_central = QWidget()
        layout_principal = QHBoxLayout(widget_central)
        
        # --- PANEL IZQUIERDO (Lista) ---
        panel_izquierdo = QVBoxLayout()
        
        # Sub-layout horizontal para agrupar los botones
        layout_botones_izq = QHBoxLayout()
        self.btn_nueva = QPushButton("Nueva Nota")
        self.btn_nueva.setShortcut("Ctrl+N")
        self.btn_eliminar = QPushButton("Eliminar Nota")
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar nota...")
        
        self.lista_notas = QListWidget()
        
        panel_izquierdo.addLayout(layout_botones_izq)
        panel_izquierdo.addWidget(self.buscador)  # <-- Añadimos el buscador al layout
        panel_izquierdo.addWidget(self.lista_notas)
        
        layout_botones_izq.addWidget(self.btn_nueva)
        layout_botones_izq.addWidget(self.btn_eliminar)
        
        self.lista_notas = QListWidget()
        
        panel_izquierdo.addLayout(layout_botones_izq)
        panel_izquierdo.addWidget(self.lista_notas)
        
        # --- PANEL DERECHO (Editor) ---
        panel_derecho = QVBoxLayout()
        self.editor_texto = QTextEdit()
        self.btn_guardar = QPushButton("Guardar Cambios")
        self.btn_guardar.setShortcut("Ctrl+S")
        
        panel_derecho.addWidget(self.editor_texto)
        panel_derecho.addWidget(self.btn_guardar)
        
        # Ensamblar los paneles
        layout_principal.addLayout(panel_izquierdo, 1) # Proporción 1/4
        layout_principal.addLayout(panel_derecho, 3)   # Proporción 3/4
        self.setCentralWidget(widget_central)
        
        # --- ESTADO Y CONEXIONES ---
        self.ruta_actual = None  # Para saber qué archivo estamos editando
        
        self.btn_nueva.clicked.connect(self.crear_nueva_nota)
        self.btn_eliminar.clicked.connect(self.eliminar_nota_seleccionada)
        self.lista_notas.itemClicked.connect(self.mostrar_contenido)
        self.btn_guardar.clicked.connect(self.guardar_nota)
        self.buscador.textChanged.connect(self.filtrar_notas)
        
        # Cargar las notas al iniciar
        self.cargar_lista_notas()

    def cargar_lista_notas(self):
        self.lista_notas.clear()
        notas = storage.listar_notas()
        for nota in notas:
            titulo, fecha = storage.obtener_metadatos(nota)
            self.lista_notas.addItem(f"[{fecha}] {titulo}")

    def crear_nueva_nota(self):
        # Muestra una ventana emergente para pedir el título
        titulo, ok = QInputDialog.getText(self, "Nueva Nota", "Título de la nota:")
        if ok and titulo:
            self.ruta_actual = storage.crear_nota(titulo)
            self.cargar_lista_notas()
            self.editor_texto.clear()
            QMessageBox.information(self, "Éxito", f"Nota '{titulo}' creada.")

    def mostrar_contenido(self):
        # Calcula el índice basado en la selección (sumando 1 porque tu lógica empieza en 1)
        indice = self.lista_notas.currentRow() + 1
        self.ruta_actual = storage.obtener_ruta_por_indice(indice)
        
        if self.ruta_actual:
            contenido = storage.leer_nota(self.ruta_actual)
            self.editor_texto.setPlainText(contenido)

    def guardar_nota(self):
        if self.ruta_actual:
            # Capturamos todo el texto del panel derecho
            contenido = self.editor_texto.toPlainText()
            # Escribimos directamente usando el objeto Path que nos dio storage.py
            self.ruta_actual.write_text(contenido, encoding='utf-8')
            QMessageBox.information(self, "Guardado", "Nota actualizada correctamente.")

    def filtrar_notas(self, texto):
        # Recorremos todas las notas de la lista visual
        for i in range(self.lista_notas.count()):
            item = self.lista_notas.item(i)
            # Pasamos todo a minúsculas para que la búsqueda no sea estricta
            if texto.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def eliminar_nota_seleccionada(self):
        # Verificar qué fila está seleccionada
        fila_actual = self.lista_notas.currentRow()
        
        if fila_actual < 0:
            QMessageBox.warning(self, "Atención", "Selecciona una nota de la lista para eliminar.")
            return
            
        # Calcular el índice (sumamos 1 porque tu lógica de storage empieza en 1)
        indice = fila_actual + 1
        ruta_a_eliminar = storage.obtener_ruta_por_indice(indice)
        
        if ruta_a_eliminar:
            titulo, _ = storage.obtener_metadatos(ruta_a_eliminar)
            respuesta = QMessageBox.question(
                self, 
                "Confirmar Eliminación", 
                f"¿Estás seguro de que deseas eliminar permanentemente '{titulo}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if respuesta == QMessageBox.StandardButton.Yes:
                storage.eliminar_nota(ruta_a_eliminar)
                self.cargar_lista_notas()
                
                if self.ruta_actual == ruta_a_eliminar:
                    self.editor_texto.clear()
                    self.ruta_actual = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # --- TEMA OSCURO (QSS) ---
    estilo_oscuro = """
    QMainWindow, QWidget {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    QListWidget, QTextEdit {
        background-color: #252526;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 5px;
        font-size: 14px;
        selection-background-color: #007acc;
    }
    QListWidget::item:hover {
        background-color: #2a2d2e;
    }
    QPushButton {
        background-color: #333333;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #444444;
        border: 1px solid #555555;
    }
    QPushButton:pressed {
        background-color: #222222;
    }
    QMessageBox {
        background-color: #1e1e1e;
    }
    """
    app.setStyleSheet(estilo_oscuro)
    
    ventana = NerdNotesApp()
    ventana.show()
    sys.exit(app.exec())