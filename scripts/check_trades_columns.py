# -*- coding: utf-8 -*-
"""
Verifica las columnas reales de la tabla trades
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

config = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'trading_bot'),
    'user': os.getenv('POSTGRES_USER', 'trader'),
    'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
}

print("="*70)
print("COLUMNAS DE LA TABLA TRADES")
print("="*70)

try:
    conn = psycopg2.connect(**config)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'trades'
        ORDER BY ordinal_position
    """)
    
    columns = cursor.fetchall()
    
    print(f"\nTotal columnas: {len(columns)}\n")
    
    for col in columns:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        print(f"  {col['column_name']:25s} {col['data_type']:20s} {nullable}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    
except Exception as e:
    print(f"ERROR: {e}")
