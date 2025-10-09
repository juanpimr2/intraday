import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.migrations.migration_runner import MigrationRunner

connection_params = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'trading_bot'),
    'user': os.getenv('POSTGRES_USER', 'trader'),
    'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
}

runner = MigrationRunner(connection_params)

print("🔍 Verificando migraciones...")
print("-" * 60)

# Migraciones aplicadas
applied = runner.get_applied_migrations()
print(f"✅ Migraciones aplicadas: {len(applied)}")
for migration in applied:
    print(f"   - {migration}")

# Migraciones pendientes
pending = runner.get_pending_migrations()
print(f"\n⏳ Migraciones pendientes: {len(pending)}")
for version, filepath in pending:
    print(f"   - {version} ({filepath.name})")

if pending:
    print("\nPara aplicar migraciones pendientes, ejecuta:")
    print("   python database/migrations/migration_runner.py migrate")
