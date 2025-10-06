#!/usr/bin/env python3
"""
Script para ejecutar tests del trading bot con diferentes opciones
"""

import sys
import subprocess
import argparse


def run_command(cmd):
    """Ejecuta un comando y muestra el output"""
    print("\n" + "="*70)
    print(f"Ejecutando: {' '.join(cmd)}")
    print("="*70 + "\n")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Ejecutar tests del trading bot')
    
    parser.add_argument(
        'test_type',
        nargs='?',
        choices=['all', 'unit', 'integration', 'dashboard', 'fast', 'slow'],
        default='all',
        help='Tipo de tests a ejecutar'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Modo verbose (más detalles)'
    )
    
    parser.add_argument(
        '-s', '--show-output',
        action='store_true',
        help='Mostrar prints de los tests'
    )
    
    parser.add_argument(
        '--cov',
        action='store_true',
        help='Ejecutar con coverage'
    )
    
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generar reporte HTML de coverage'
    )
    
    parser.add_argument(
        '-k',
        type=str,
        help='Ejecutar tests que coincidan con la expresión'
    )
    
    parser.add_argument(
        '--failed',
        action='store_true',
        help='Ejecutar solo tests que fallaron la última vez'
    )
    
    args = parser.parse_args()
    
    # Construir comando base
    cmd = ['pytest']
    
    # Agregar flags según argumentos
    if args.verbose:
        cmd.append('-vv')
    
    if args.show_output:
        cmd.append('-s')
    
    if args.failed:
        cmd.append('--lf')  # last-failed
    
    if args.k:
        cmd.extend(['-k', args.k])
    
    # Coverage
    if args.cov:
        cmd.extend(['--cov=.', '--cov-report=term-missing'])
        if args.html:
            cmd.append('--cov-report=html')
    
    # Seleccionar tipo de test
    if args.test_type == 'unit':
        cmd.extend(['-m', 'unit'])
        print("🧪 Ejecutando solo tests unitarios...")
    
    elif args.test_type == 'integration':
        cmd.extend(['-m', 'integration'])
        print("🔗 Ejecutando solo tests de integración...")
    
    elif args.test_type == 'dashboard':
        cmd.extend(['-m', 'dashboard'])
        print("🌐 Ejecutando solo tests del dashboard...")
    
    elif args.test_type == 'fast':
        cmd.extend(['-m', 'not slow'])
        print("⚡ Ejecutando solo tests rápidos...")
    
    elif args.test_type == 'slow':
        cmd.extend(['-m', 'slow'])
        print("🐌 Ejecutando solo tests lentos...")
    
    else:
        print("🚀 Ejecutando todos los tests...")
    
    # Agregar directorio de tests
    cmd.append('tests/')
    
    # Ejecutar
    exit_code = run_command(cmd)
    
    # Mensaje final
    print("\n" + "="*70)
    if exit_code == 0:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("="*70 + "\n")
    
    # Coverage report
    if args.cov and args.html:
        print("\n📊 Reporte de coverage generado en: htmlcov/index.html")
        print("   Ábrelo con: start htmlcov/index.html (Windows) o open htmlcov/index.html (Mac)\n")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    # Verificar que pytest esté instalado
    try:
        import pytest
    except ImportError:
        print("❌ pytest no está instalado")
        print("   Instálalo con: pip install pytest pytest-flask pytest-cov")
        sys.exit(1)
    
    main()