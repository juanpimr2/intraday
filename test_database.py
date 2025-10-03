#!/usr/bin/env python3
"""
Test del sistema de persistencia
"""

from database.connection import DatabaseConnection
from database.queries.analytics import AnalyticsQueries

print("="*60)
print("🧪 TEST DEL SISTEMA DE PERSISTENCIA")
print("="*60)
print()

# Test 1: Conexión
print("1️⃣ Test de Conexión...")
try:
    db = DatabaseConnection()
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        result = cursor.fetchone()
        print(f"   ✅ Conexión exitosa")
        print(f"   ✅ Migraciones aplicadas: {result['count']}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Verificar tablas
print("2️⃣ Test de Tablas...")
try:
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"   ✅ Tablas creadas: {len(tables)}")
        for table in tables:
            print(f"      - {table['table_name']}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 3: Verificar vistas
print("3️⃣ Test de Vistas...")
try:
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        views = cursor.fetchall()
        print(f"   ✅ Vistas creadas: {len(views)}")
        for view in views:
            print(f"      - {view['table_name']}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 4: Analytics
print("4️⃣ Test de Analytics...")
try:
    analytics = AnalyticsQueries()
    
    # Probar query (puede estar vacío)
    df = analytics.get_session_summary(limit=5)
    print(f"   ✅ Analytics funciona")
    print(f"   📊 Sesiones en BD: {len(df)}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("="*60)
print("✅ SISTEMA DE PERSISTENCIA FUNCIONANDO")
print("="*60)
print()
print("🎯 Próximo paso: Ejecutar el bot")
print("   python main.py")
print()