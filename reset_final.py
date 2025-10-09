import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 80)
print("LIMPIEZA Y RESET DE BASE DE DATOS")
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
    
    print("\nEliminando estructura antigua...")
    
    # Eliminar TODO
    cursor.execute("""
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO trader;
        GRANT ALL ON SCHEMA public TO public;
    """)
    
    print("✅ Schema limpio")
    
    print("\nCreando estructura nueva...")
    
    # Leer archivos SQL
    with open('database/migrations/versions/v001_initial_schema.sql', 'r') as f:
        v001 = f.read()
    
    with open('database/migrations/versions/v002_analytics_views.sql', 'r') as f:
        v002 = f.read()
    
    # Ejecutar
    cursor.execute(v001)
    print("✅ Tablas creadas")
    
    cursor.execute(v002)
    print("✅ Vistas creadas")
    
    # Verificar
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    tables = cursor.fetchall()
    
    cursor.execute("""
        SELECT table_name FROM information_schema.views 
        WHERE table_schema = 'public'
    """)
    views = cursor.fetchall()
    
    print(f"\n📋 Estructura final:")
    print(f"   Tablas ({len(tables)}): {', '.join([t[0] for t in tables])}")
    print(f"   Vistas ({len(views)}): {', '.join([v[0] for v in views])}")
    
    print("\n" + "="*80)
    print("✅ BASE DE DATOS LISTA")
    print("="*80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
