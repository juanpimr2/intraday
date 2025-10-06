#!/usr/bin/env python3
"""
Script de setup para el dashboard
Crea directorios necesarios y verifica dependencias
"""

import os
import sys
import subprocess


def check_python_version():
    """Verifica versión de Python"""
    print("🐍 Verificando versión de Python...")
    version = sys.version_info
    
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python {version.major}.{version.minor} detectado")
        print("   Se requiere Python 3.9 o superior")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    print("\n📦 Verificando dependencias...")
    
    required = [
        'flask',
        'flask_cors',
        'pandas',
        'psycopg2',
        'pytest',
        'openpyxl'
    ]
    
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} no encontrado")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Faltan {len(missing)} dependencias")
        print("   Instálalas con: pip install -r requirements.txt")
        return False
    
    return True


def create_directories():
    """Crea directorios necesarios"""
    print("\n📁 Creando directorios...")
    
    directories = [
        'exports',
        'logs',
        'dashboard/templates',
        'dashboard/static/css',
        'dashboard/static/js',
        'tests'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Creado: {directory}")
        else:
            print(f"✓  Existe: {directory}")


def check_database():
    """Verifica conexión a la base de datos"""
    print("\n🗄️  Verificando base de datos...")
    
    try:
        from database.connection import DatabaseConnection
        db = DatabaseConnection()
        
        with db.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        print("✅ Conexión a PostgreSQL exitosa")
        return True
    
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("\n   Posibles soluciones:")
        print("   1. Inicia PostgreSQL: docker-compose up -d postgres")
        print("   2. Verifica credenciales en .env")
        print("   3. Aplica migraciones: python database/migrations/migration_runner.py migrate")
        return False


def verify_files():
    """Verifica que existan archivos críticos"""
    print("\n📄 Verificando archivos críticos...")
    
    critical_files = [
        'dashboard/app.py',
        'dashboard/templates/index.html',
        'dashboard/static/css/style.css',
        'dashboard/static/js/main.js',
        'database/queries/analytics.py',
        'tests/test_dashboard_integration.py',
        'tests/conftest.py',
        'pytest.ini',
        'requirements.txt'
    ]
    
    missing = []
    
    for file in critical_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} no encontrado")
            missing.append(file)
    
    if missing:
        print(f"\n⚠️  Faltan {len(missing)} archivos críticos")
        print("   Verifica que hayas copiado todos los archivos del proyecto")
        return False
    
    return True


def create_env_example():
    """Crea archivo .env.example si no existe"""
    print("\n🔐 Verificando configuración...")
    
    env_example = """# Trading Bot Configuration
# Renombra este archivo a .env y completa los valores

# API Credentials
CAPITAL_API_KEY=tu_api_key
CAPITAL_EMAIL=tu_email@ejemplo.com
CAPITAL_PASSWORD=tu_password

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=trader
DB_PASSWORD=trader_password

# Dashboard
DASHBOARD_PORT=5000
"""
    
    if not os.path.exists('.env.example'):
        with open('.env.example', 'w') as f:
            f.write(env_example)
        print("✅ Creado .env.example")
        print("   Renómbralo a .env y completa tus credenciales")
    else:
        print("✓  .env.example existe")
    
    if not os.path.exists('.env'):
        print("⚠️  Archivo .env no encontrado")
        print("   Copia .env.example a .env y completa tus credenciales")
        return False
    else:
        print("✅ .env configurado")
    
    return True


def run_quick_test():
    """Ejecuta un test rápido"""
    print("\n🧪 Ejecutando test rápido...")
    
    try:
        result = subprocess.run(
            ['pytest', 'tests/test_dashboard_integration.py::test_api_config', '-v'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Test pasó correctamente")
            return True
        else:
            print("❌ Test falló")
            print(result.stdout)
            print(result.stderr)
            return False
    
    except subprocess.TimeoutExpired:
        print("⏱️  Test timeout (>30s)")
        return False
    except Exception as e:
        print(f"❌ Error ejecutando test: {e}")
        return False


def print_summary(checks):
    """Imprime resumen de checks"""
    print("\n" + "="*70)
    print("📊 RESUMEN DEL SETUP")
    print("="*70)
    
    total = len(checks)
    passed = sum(checks.values())
    
    for check, status in checks.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {check}")
    
    print("="*70)
    print(f"Resultado: {passed}/{total} checks pasaron")
    
    if passed == total:
        print("\n🎉 ¡Todo listo! El dashboard está configurado correctamente")
        print("\n▶️  Siguiente paso:")
        print("   python start_all.py")
        print("   Luego abre: http://localhost:5000")
    else:
        print("\n⚠️  Hay problemas que resolver antes de continuar")
        print("   Revisa los errores arriba y vuelve a ejecutar este script")


def main():
    """Función principal"""
    print("="*70)
    print("🚀 SETUP DEL DASHBOARD - TRADING BOT")
    print("="*70)
    
    checks = {}
    
    # Ejecutar checks
    checks['Python 3.9+'] = check_python_version()
    checks['Dependencias'] = check_dependencies()
    
    create_directories()  # Siempre crear directorios
    
    checks['Archivos críticos'] = verify_files()
    checks['Configuración .env'] = create_env_example()
    checks['Base de datos'] = check_database()
    
    if all(checks.values()):
        checks['Test rápido'] = run_quick_test()
    
    # Resumen
    print_summary(checks)
    
    # Exit code
    if all(checks.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)