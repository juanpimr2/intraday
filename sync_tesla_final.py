import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=os.getenv('POSTGRES_PORT', 5432),
    database=os.getenv('POSTGRES_DB', 'trading_bot'),
    user=os.getenv('POSTGRES_USER', 'trader'),
    password=os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
)

cursor = conn.cursor(cursor_factory=RealDictCursor)

# Crear sesión
cursor.execute("""
    INSERT INTO trading_sessions (initial_balance)
    VALUES (1014.83)
    RETURNING session_id
""")
session_id = cursor.fetchone()['session_id']
print(f"Sesión creada: #{session_id}")

# Agregar trades de Tesla
trades = [
    ('00513301-0055-311e-0000-0000814224ia', 432.48, 3.9, 462.85, 380.66),
    ('00513301-0055-311e-0000-0000814224ce', 434.42, 2.7, 465.09, 382.50)
]

for deal, price, size, sl, tp in trades:
    cursor.execute("""
        INSERT INTO trades (
            session_id, deal_reference, epic, direction,
            entry_time, entry_price, position_size,
            stop_loss, take_profit, status, margin_used
        ) VALUES (%s, %s, 'TSLA', 'SELL', NOW(), %s, %s, %s, %s, 'OPEN', %s)
    """, (session_id, deal, price, size, sl, tp, size * price * 0.2))
    print(f"✅ Trade agregado: {deal[-8:]}")

conn.commit()
print("\n✅ Operaciones de Tesla sincronizadas")

cursor.close()
conn.close()
