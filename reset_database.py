import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 80)
print("🧹 LIMPIEZA Y RESET DE BASE DE DATOS")
print("=" * 80)

config = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'trading_bot'),
    'user': os.getenv('POSTGRES_USER', 'trader'),
    'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
}

try:
    conn = psycopg2.connect(**config)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("\n⚠️  ADVERTENCIA: Esto eliminará TODAS las tablas y datos")
    response = input("¿Estás seguro? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\n🗑️  Eliminando todas las tablas...")
        
        # Eliminar vistas primero
        cursor.execute("""
            DROP VIEW IF EXISTS active_trades CASCADE;
            DROP VIEW IF EXISTS daily_summary CASCADE;
            DROP VIEW IF EXISTS performance_by_asset CASCADE;
            DROP VIEW IF EXISTS latest_account_state CASCADE;
        """)
        
        # Eliminar tablas no necesarias
        cursor.execute("""
            DROP TABLE IF EXISTS system_logs CASCADE;
            DROP TABLE IF EXISTS backtest_results CASCADE;
            DROP TABLE IF EXISTS performance_metrics CASCADE;
            DROP TABLE IF EXISTS market_signals CASCADE;
            DROP TABLE IF EXISTS strategy_versions CASCADE;
        """)
        
        # Eliminar tablas principales
        cursor.execute("""
            DROP TABLE IF EXISTS account_snapshots CASCADE;
            DROP TABLE IF EXISTS trades CASCADE;
            DROP TABLE IF EXISTS trading_sessions CASCADE;
            DROP TABLE IF EXISTS schema_migrations CASCADE;
        """)
        
        print("✅ Tablas eliminadas")
        
        print("\n📝 Recreando estructura simplificada...")
        
        # Leer y ejecutar v001
        with open('database/migrations/versions/v001_initial_schema.sql', 'r') as f:
            cursor.execute(f.read())
        
        # Leer y ejecutar v002
        with open('database/migrations/versions/v002_analytics_views.sql', 'r') as f:
            cursor.execute(f.read())
        
        print("✅ Estructura recreada")
        
        # Verificar
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\n📋 Tablas actuales ({len(tables)}):")
        for table in tables:
            print(f"   - {table[0]}")
            
        print("\n" + "=" * 80)
        print("✅ BASE DE DATOS RESETEADA Y SIMPLIFICADA")
        print("=" * 80)
    else:
        print("\n❌ Operación cancelada")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
