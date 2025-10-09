import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

print("=" * 80)
print("🔍 VERIFICACIÓN COMPLETA: OPERACIONES TESLA")
print("=" * 80)

# Conexión a PostgreSQL
config = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'trading_bot'),
    'user': os.getenv('POSTGRES_USER', 'trader'),
    'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
}

try:
    conn = psycopg2.connect(**config)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n📊 ESTADO DE LA BASE DE DATOS")
    print("-" * 60)
    
    # 1. Verificar tablas existentes
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print(f"\n📋 Tablas encontradas: {len(tables)}")
    for table in tables:
        print(f"   - {table['table_name']}")
    
    # 2. Verificar sesiones activas
    cursor.execute("""
        SELECT session_id, start_time, status, initial_balance
        FROM trading_sessions 
        WHERE status = 'RUNNING'
        ORDER BY start_time DESC
    """)
    sessions = cursor.fetchall()
    
    if sessions:
        print(f"\n📍 Sesiones activas: {len(sessions)}")
        for session in sessions:
            print(f"   Session #{session['session_id']}: {session['status']} desde {session['start_time']}")
        current_session = sessions[0]['session_id']
    else:
        print("\n⚠️ No hay sesiones activas. Creando una nueva...")
        cursor.execute("""
            INSERT INTO trading_sessions (initial_balance, status)
            VALUES (1014.83, 'RUNNING')
            RETURNING session_id
        """)
        current_session = cursor.fetchone()['session_id']
        conn.commit()
        print(f"✅ Sesión creada: #{current_session}")
    
    # 3. Verificar trades de TESLA
    cursor.execute("""
        SELECT trade_id, deal_reference, epic, direction, 
               entry_price, position_size, stop_loss, take_profit,
               status, pnl, entry_time
        FROM trades 
        WHERE epic LIKE '%TESLA%' OR epic LIKE '%TSLA%'
        ORDER BY entry_time DESC
    """)
    trades = cursor.fetchall()
    
    print(f"\n🚗 TRADES DE TESLA EN BD: {len(trades)}")
    if trades:
        for trade in trades:
            status_emoji = "🟢" if trade['status'] == 'OPEN' else "🔴"
            print(f"\n   {status_emoji} Trade #{trade['trade_id']}")
            print(f"      Deal: {trade['deal_reference']}")
            print(f"      Direction: {trade['direction']}")
            print(f"      Entry: ${trade['entry_price']}")
            print(f"      Size: {trade['position_size']}")
            print(f"      SL: ${trade['stop_loss']}")
            print(f"      TP: ${trade['take_profit']}")
            print(f"      Status: {trade['status']}")
    
    # 4. Insertar los trades de TESLA que vemos en tu dashboard
    print("\n" + "="*60)
    print("📝 SINCRONIZANDO OPERACIONES DEL DASHBOARD")
    print("-"*60)
    
    # Datos de las 2 operaciones SELL de TESLA que viste
    tesla_operations = [
        {
            'deal_reference': '00513301-0055-311e-0000-0000814224ia',
            'epic': 'TSLA',
            'direction': 'SELL',
            'entry_price': 432.48,
            'position_size': 3.9,
            'stop_loss': 462.85,
            'take_profit': 380.66
        },
        {
            'deal_reference': '00513301-0055-311e-0000-0000814224ce',
            'epic': 'TSLA',
            'direction': 'SELL', 
            'entry_price': 434.42,
            'position_size': 2.7,
            'stop_loss': 465.09,
            'take_profit': 382.50
        }
    ]
    
    for op in tesla_operations:
        # Verificar si ya existe
        cursor.execute(
            "SELECT trade_id FROM trades WHERE deal_reference = %s",
            (op['deal_reference'],)
        )
        existing = cursor.fetchone()
        
        if not existing:
            print(f"\n💾 Insertando: {op['deal_reference'][-8:]}")
            cursor.execute("""
                INSERT INTO trades (
                    session_id, deal_reference, epic, direction,
                    entry_time, entry_price, position_size,
                    stop_loss, take_profit, status, margin_used
                ) VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, 'OPEN', %s)
                RETURNING trade_id
            """, (
                current_session,
                op['deal_reference'],
                op['epic'],
                op['direction'],
                op['entry_price'],
                op['position_size'],
                op['stop_loss'],
                op['take_profit'],
                op['position_size'] * op['entry_price'] * 0.2  # Margen aprox 20%
            ))
            
            trade_id = cursor.fetchone()['trade_id']
            print(f"   ✅ Guardado como trade #{trade_id}")
        else:
            print(f"   ✅ {op['deal_reference'][-8:]} ya existe (#{existing['trade_id']})")
    
    conn.commit()
    
    # 5. Verificación final
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open,
               COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed
        FROM trades
        WHERE epic LIKE '%TESLA%' OR epic LIKE '%TSLA%'
    """)
    
    final_stats = cursor.fetchone()
    
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL")
    print("-"*60)
    print(f"✅ Total trades TESLA: {final_stats['total']}")
    print(f"   🟢 Abiertos: {final_stats['open']}")
    print(f"   🔴 Cerrados: {final_stats['closed']}")
    print(f"\n✅ Las 2 operaciones de TESLA están sincronizadas en BD")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
