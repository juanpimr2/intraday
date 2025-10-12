#!/usr/bin/env python3
"""
Verificacion rapida de exports y diagnostico
"""
import os
from pathlib import Path
from datetime import datetime

print("="*70)
print("VERIFICACION DE EXPORTS")
print("="*70)

# 1. Verificar carpeta exports
exports_path = Path('exports')
print(f"\n1. Carpeta exports existe: {exports_path.exists()}")

if exports_path.exists():
    files = list(exports_path.glob('*'))
    print(f"   Total archivos: {len(files)}")
    
    if files:
        print("\n   Archivos encontrados:")
        for f in sorted(files):
            size = f.stat().st_size
            modified = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   - {f.name} ({size} bytes) - {modified}")
    else:
        print("   VACIA - No hay archivos")

# 2. Verificar último reporte JSON
print("\n2. Verificando ultimo reporte de test...")
json_files = list(exports_path.glob('dashboard_test_report_*.json'))
if json_files:
    latest = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"   Ultimo reporte: {latest.name}")
    
    # Leer contenido
    import json
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n   Estado BD: {data.get('database', {}).get('connection', 'UNKNOWN')}")
    print(f"   Trades Tesla: {data.get('database', {}).get('tesla_trades', 0)}")
    print(f"   Exports realizados: {len([k for k, v in data.get('exports', {}).items() if isinstance(v, dict) and v.get('status') == 'OK'])}")
    
    if data.get('errors'):
        print(f"\n   Errores detectados: {len(data['errors'])}")
        for i, error in enumerate(data['errors'][:3], 1):
            print(f"   {i}. {error[:100]}")
else:
    print("   No se encontro reporte JSON")

# 3. Verificar tabla market_signals
print("\n3. Verificando tabla market_signals en BD...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trading_bot'),
        user=os.getenv('POSTGRES_USER', 'trader'),
        password=os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'market_signals'
        )
    """)
    exists = cursor.fetchone()['exists']
    print(f"   Tabla market_signals existe: {exists}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"   ERROR verificando BD: {e}")

# 4. Intentar generar exports manualmente
print("\n4. Intentando generar exports manualmente...")
try:
    from database.queries.analytics import AnalyticsQueries
    
    analytics = AnalyticsQueries()
    
    # Intentar export CSV
    print("   Generando CSV...")
    csv_path = analytics.export_all_trades(format='csv')
    if csv_path and Path(csv_path).exists():
        print(f"   OK CSV generado: {csv_path}")
    else:
        print(f"   ERROR: CSV no generado (path: {csv_path})")
    
    # Intentar export Excel
    print("   Generando Excel...")
    excel_path = analytics.export_all_trades(format='excel')
    if excel_path and Path(excel_path).exists():
        print(f"   OK Excel generado: {excel_path}")
    else:
        print(f"   ERROR: Excel no generado (path: {excel_path})")
        
except Exception as e:
    print(f"   ERROR generando exports: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("VERIFICACION COMPLETADA")
print("="*70)
