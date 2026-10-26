import argparse
import sys
from pathlib import Path

import config
import core

def configurar_parser() -> argparse.ArgumentParser:
    """Configura el parser de argumentos"""
    parser = argparse.ArgumentParser(
        description="📝 NerdNotes - Bloc de notas para terminal",
        epilog="Ejemplo: notas new 'Mi idea' | notas list | notas show 1"
    )
    
    # Subcomandos
    subparsers = parser.add_subparsers(dest='comando', required=True, help='Comando a ejecutar')
    
    # new - Crear nota
    parser_new = subparsers.add_parser('new', help='Crear nueva nota')
    parser_new.add_argument('titulo', nargs='?', help='Título de la nota')
    
    # list - Listar notas
    parser_list = subparsers.add_parser('list', aliases=['ls'], help='Listar todas las notas')
    
    # show - Mostrar nota
    parser_show = subparsers.add_parser('show', help='Mostrar contenido de una nota')
    parser_show.add_argument('indice', type=int, help='Índice de la nota (ver list)')
    
    # edit - Editar nota
    parser_edit = subparsers.add_parser('edit', help='Editar una nota existente')
    parser_edit.add_argument('indice', type=int, help='Índice de la nota (ver list)')
    
    # delete - Eliminar nota
    parser_delete = subparsers.add_parser('delete', aliases=['del', 'rm'], help='Eliminar una nota (mueve a la papelera por defecto)')
    parser_delete.add_argument('indice', type=int, help='Índice de la nota (ver list)')
    parser_delete.add_argument('--permanente', '-p', action='store_true', help='Eliminar permanentemente en vez de mover a la papelera')
    
    # version - Mostrar versión
    parser_version = subparsers.add_parser('version', help='Mostrar versión')
    
    return parser

def main():
    """Punto de entrada principal"""
    # Asegurar que existe el directorio de notas
    config.asegurar_directorio()
    
    parser = configurar_parser()
    args = parser.parse_args()
    
    # Ejecutar comando
    if args.comando == 'new':
        core.crear_nueva_nota(args.titulo)
    
    elif args.comando in ('list', 'ls'):
        core.listar_todas_notas()
    
    elif args.comando == 'show':
        core.mostrar_nota(args.indice)
    
    elif args.comando == 'edit':
        core.editar_nota_existente(args.indice)
    
    elif args.comando in ('delete', 'del', 'rm'):
        core.eliminar_nota_existente(args.indice, permanente=args.permanente)
    
    elif args.comando == 'version':
        print("NerdNotes v0.1.0")
        print("Hecho con ❤️ para terminales")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
