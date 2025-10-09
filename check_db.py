import sqlite3
import pandas as pd
from datetime import datetime
import json

# Conectar a la base de datos
db_path = "trading_bot.db"
conn = sqlite3.connect(db_path)

print("=" * 60)
print(" ESTADO ACTUAL DE LA BASE DE DATOS")
print("=" * 60)

# 1. Operaciones activas/abiertas
query_open = """
SELECT * FROM positions 
WHERE status = 'open' OR status = 'OPEN'
ORDER BY entry_time DESC
"""
df_open = pd.read_sql_query(query_open, conn)
print(f"\n✅ Operaciones ABIERTAS: {len(df_open)}")
if not df_open.empty:
    print(df_open[['id', 'symbol', 'side', 'size', 'entry_price', 'current_price', 'pnl', 'entry_time']].to_string())

# 2. Operaciones de TESLA específicamente
query_tesla = """
SELECT * FROM positions 
WHERE symbol LIKE '%TESLA%' OR symbol LIKE '%TSLA%'
ORDER BY entry_time DESC
LIMIT 10
"""
df_tesla = pd.read_sql_query(query_tesla, conn)
print(f"\n Operaciones de TESLA (últimas 10):")
if not df_tesla.empty:
    print(df_tesla[['id', 'symbol', 'side', 'status', 'size', 'entry_price', 'exit_price', 'pnl', 'entry_time']].to_string())

# 3. Resumen de operaciones por estado
query_summary = """
SELECT status, COUNT(*) as count, SUM(pnl) as total_pnl
FROM positions
GROUP BY status
"""
df_summary = pd.read_sql_query(query_summary, conn)
print("\n Resumen por estado:")
print(df_summary.to_string())

# 4. Últimas 5 operaciones (cualquier estado)
query_recent = """
SELECT * FROM positions
ORDER BY entry_time DESC
LIMIT 5
"""
df_recent = pd.read_sql_query(query_recent, conn)
print("\n Últimas 5 operaciones:")
print(df_recent[['id', 'symbol', 'side', 'status', 'pnl', 'entry_time']].to_string())

conn.close()
print("\n" + "=" * 60)
