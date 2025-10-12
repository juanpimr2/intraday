#!/usr/bin/env python3
"""
Script de setup simplificado para verificar el dashboard del trading bot
"""

import sys
import os
import subprocess
from pathlib import Path


def print_header(text):
    """Imprime un header formateado"""
    print("=" * 70)
    print(f"{text}")
    print("=" * 70)


def print_section(text):
    """Imprime una sección"""
    print(f"\n{text}")


def check_python_version():
    """Verifica la versión de Python"""
    print_section("Verificando version de Python...")
    version = sys.version_info
    
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"X Python {version.major}.{version.minor}.{version.micro}")
        print("   Se requiere Python 3.9 o superior")
        return False
    
    print(f"OK Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    print_section("Verificando dependencias...")
    
    required = [
        'flask',
        'pandas',
        'pytest'
    ]
    
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"OK {package}")
        except ImportError:
            print(f"X {package} (falta)")
            missing.append(package)
    
    if missing:
        print(f"\nInstala las dependencias faltantes:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def create_directories():
    """Crea los directorios necesarios"""
    print_section("Creando directorios...")
    
    directories = [
        'exports',
        'logs',
        'dashboard/templates',
        'dashboard/static/css',
        'dashboard/static/js',
        'tests'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"OK Creado: {directory}")
        else:
            print(f"OK Existe: {directory}")
    
    return True


def check_critical_files():
    """Verifica que los archivos críticos existan"""
    print_section("Verificando archivos criticos...")
    
    critical_files = [
        'dashboard/app.py',
        'config.py',
        'tests/test_dashboard_integration.py',
        'tests/conftest.py',
        'pytest.ini'
    ]
    
    missing = []
    
    for filepath in critical_files:
        path = Path(filepath)
        if path.exists():
            print(f"OK {filepath}")
        else:
            print(f"X {filepath} (falta)")
            missing.append(filepath)
    
    if missing:
        print(f"\nArchivos criticos faltantes:")
        for f in missing:
            print(f"   - {f}")
        return False
    
    return True


def run_quick_test():
    """Ejecuta un test rápido"""
    print_section("Ejecutando test rapido...")
    
    try:
        # Configurar environment para UTF-8 en Windows
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Usar python -m pytest para compatibilidad con Windows
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 
             'tests/test_dashboard_integration.py::test_api_config', 
             '-v', '--tb=line', '--no-header'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            print("OK Test basico paso correctamente")
            return True
        else:
            print("X Test basico fallo")
            # Solo mostrar la última parte del output (más relevante)
            output_lines = result.stdout.split('\n')
            relevant_lines = [l for l in output_lines if 'PASSED' in l or 'FAILED' in l or 'ERROR' in l]
            if relevant_lines:
                print("   ", "\n    ".join(relevant_lines[:5]))
            return False
            
    except subprocess.TimeoutExpired:
        print("X Test tomo demasiado tiempo (timeout 30s)")
        return False
    except FileNotFoundError:
        print("X pytest no esta instalado correctamente")
        print("   Ejecuta: pip install pytest")
        return False
    except Exception as e:
        print(f"X Error ejecutando test: {e}")
        return False


def print_summary(results):
    """Imprime un resumen de los checks"""
    print_header("RESUMEN DEL SETUP")
    
    checks = {
        'Python 3.9+': results['python'],
        'Dependencias': results['dependencies'],
        'Directorios': results['directories'],
        'Archivos criticos': results['files'],
        'Test rapido': results['test']
    }
    
    for check, passed in checks.items():
        status = "OK" if passed else "X"
        print(f"{status} {check}")
    
    print("=" * 70)
    
    passed_count = sum(1 for v in checks.values() if v)
    total_count = len(checks)
    
    print(f"Resultado: {passed_count}/{total_count} checks pasaron")
    
    if passed_count == total_count:
        print("\nTodo listo! Puedes ejecutar el dashboard:")
        print("   python start_all.py")
    else:
        print("\nHay problemas que resolver antes de continuar")
        print("   Revisa los errores arriba y vuelve a ejecutar este script")


def main():
    """Función principal"""
    print_header("SETUP DEL DASHBOARD - TRADING BOT")
    
    # Ejecutar todos los checks
    results = {
        'python': check_python_version(),
        'dependencies': check_dependencies(),
        'directories': create_directories(),
        'files': check_critical_files(),
        'test': run_quick_test()
    }
    
    # Imprimir resumen
    print_summary(results)
    
    # Exit code basado en resultados
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()