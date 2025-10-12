import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

print("="*70)
print("🔍 CHECKPOINT DE SALUD DEL BOT")
print("="*70)

# Conexión
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
    
    print("\n📊 1. ESTADO DE LA BASE DE DATOS")
    print("-"*70)
    
    # Verificar tablas
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print(f"✅ Tablas existentes: {len(tables)}")
    for t in tables:
        print(f"   - {t['table_name']}")
    
    print("\n📈 2. OPERACIONES DE TESLA")
    print("-"*70)
    
    # Buscar operaciones de Tesla
    cursor.execute("""
        SELECT 
            trade_id,
            deal_reference,
            epic,
            direction,
            entry_price,
            position_size,
            stop_loss,
            take_profit,
            entry_time,
            status,
            pnl,
            pnl_percent
        FROM trades 
        WHERE epic LIKE '%TESLA%' OR epic LIKE '%TSLA%'
        ORDER BY entry_time DESC
    """)
    
    tesla_trades = cursor.fetchall()
    
    if tesla_trades:
        print(f"✅ Trades de TESLA encontrados: {len(tesla_trades)}\n")
        for trade in tesla_trades:
            status_emoji = "🟢" if trade['status'] == 'OPEN' else "🔴"
            print(f"{status_emoji} Trade #{trade['trade_id']}")
            print(f"   Deal: {trade['deal_reference']}")
            print(f"   Dirección: {trade['direction']}")
            print(f"   Entrada: ${trade['entry_price']:.2f} x {trade['position_size']}")
            print(f"   SL: ${trade['stop_loss']:.2f} | TP: ${trade['take_profit']:.2f}")
            print(f"   Status: {trade['status']}")
            if trade['pnl']:
                print(f"   P&L: ${trade['pnl']:.2f} ({trade['pnl_percent']:.2f}%)")
            print(f"   Fecha: {trade['entry_time']}")
            print()
    else:
        print("⚠️ No se encontraron trades de TESLA en la BD")
        print("\n🔍 Verificando si hay ALGÚN trade en la BD...")
        
        cursor.execute("SELECT COUNT(*) as total FROM trades")
        total = cursor.fetchone()
        print(f"   Total trades en BD: {total['total']}")
    
    print("\n📊 3. RESUMEN GENERAL")
    print("-"*70)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_trades,
            COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades,
            COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
            COALESCE(SUM(pnl), 0) as total_pnl
        FROM trades
    """)
    
    summary = cursor.fetchone()
    print(f"Total trades: {summary['total_trades']}")
    print(f"Abiertas: {summary['open_trades']}")
    print(f"Cerradas: {summary['closed_trades']}")
    print(f"P&L Total: ${summary['total_pnl']:.2f}")
    
    print("\n📅 4. SESIONES ACTIVAS")
    print("-"*70)
    
    cursor.execute("""
        SELECT 
            session_id,
            start_time,
            initial_balance,
            total_trades,
            total_pnl,
            status
        FROM trading_sessions
        ORDER BY start_time DESC
        LIMIT 5
    """)
    
    sessions = cursor.fetchall()
    if sessions:
        for session in sessions:
            status_emoji = "🟢" if session['status'] == 'RUNNING' else "🔴"
            print(f"{status_emoji} Sesión #{session['session_id']}")
            print(f"   Inicio: {session['start_time']}")
            print(f"   Balance inicial: ${session['initial_balance']:.2f}")
            print(f"   Trades: {session['total_trades']}")
            print(f"   P&L: ${session['total_pnl']:.2f}")
            print(f"   Status: {session['status']}")
            print()
    
    cursor.close()
    conn.close()
    
    print("="*70)
    print("✅ CHECKPOINT COMPLETADO")
    print("="*70)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
