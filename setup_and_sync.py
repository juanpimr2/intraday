import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
import requests
import json

# Cargar variables de entorno
load_dotenv()

print("=" * 80)
print("🚀 CONFIGURACIÓN COMPLETA - TRADING BOT POSTGRESQL")
print("=" * 80)

# ============================================
# PARTE 1: Configurar PostgreSQL
# ============================================
def setup_database():
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', 5432),
        'database': os.getenv('POSTGRES_DB', 'trading_bot'),
        'user': os.getenv('POSTGRES_USER', 'trader'),
        'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
    }
    
    print("\n📊 Configuración PostgreSQL:")
    for k, v in config.items():
        if k != 'password':
            print(f"   {k}: {v}")
    
    try:
        print("\n🔌 Conectando a PostgreSQL...")
        conn = psycopg2.connect(**config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verificar conexión
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"✅ Conectado exitosamente")
        
        # Crear estructura completa
        print("\n📋 Creando/Verificando estructura de tablas...")
        
        # Tabla de sesiones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_sessions (
                session_id SERIAL PRIMARY KEY,
                start_time TIMESTAMP NOT NULL DEFAULT NOW(),
                end_time TIMESTAMP,
                initial_balance DECIMAL(12, 2) NOT NULL,
                final_balance DECIMAL(12, 2),
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl DECIMAL(12, 2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'RUNNING',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Tabla de trades (corregida)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES trading_sessions(session_id),
                deal_reference VARCHAR(100) UNIQUE,
                epic VARCHAR(50) NOT NULL,
                direction VARCHAR(10) NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                entry_price DECIMAL(12, 6) NOT NULL,
                position_size DECIMAL(12, 6) NOT NULL,
                stop_loss DECIMAL(12, 6),
                take_profit DECIMAL(12, 6),
                margin_used DECIMAL(12, 2),
                confidence DECIMAL(5, 4),
                exit_time TIMESTAMP,
                exit_price DECIMAL(12, 6),
                exit_reason VARCHAR(50),
                pnl DECIMAL(12, 2),
                pnl_percent DECIMAL(8, 4),
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_epic ON trades(epic)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_deal ON trades(deal_reference)")
        
        conn.commit()
        print("✅ Estructura de BD creada/verificada")
        
        return conn
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Error conectando a PostgreSQL: {e}")
        print("\n⚠️  Soluciones posibles:")
        print("1. Si usas Docker:")
        print("   docker run --name trading_postgres -e POSTGRES_USER=trader \\")
        print("   -e POSTGRES_PASSWORD=secure_password_123 -e POSTGRES_DB=trading_bot \\")
        print("   -p 5432:5432 -d postgres:15-alpine")
        print("\n2. Si usas PostgreSQL local, verifica que esté activo")
        return None
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None

# ============================================
# PARTE 2: Verificar posiciones en API
# ============================================
def check_api_positions():
    print("\n" + "="*80)
    print("📡 VERIFICANDO POSICIONES EN CAPITAL.COM API")
    print("="*80)
    
    api_key = os.getenv('CAPITAL_API_KEY')
    password = os.getenv('CAPITAL_PASSWORD')
    
    if not api_key or api_key == 'tu_api_key_real':
        print("⚠️  Por favor, actualiza el archivo .env con tus credenciales reales de Capital.com")
        return None
    
    # Login
    base_url = "https://demo-api-capital.backend-capital.com"
    
    try:
        print("\n🔐 Haciendo login en Capital.com...")
        login_response = requests.post(
            f"{base_url}/api/v1/session",
            json={"identifier": api_key, "password": password},
            headers={"X-CAPITAL-API-KEY": api_key}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Error de login: {login_response.status_code}")
            return None
        
        tokens = login_response.headers
        cst = tokens.get('X-SECURITY-TOKEN')
        cst_header = tokens.get('CST')
        
        print("✅ Login exitoso")
        
        # Obtener posiciones abiertas
        headers = {
            "X-CAPITAL-API-KEY": api_key,
            "X-SECURITY-TOKEN": cst,
            "CST": cst_header
        }
        
        positions_response = requests.get(
            f"{base_url}/api/v1/positions",
            headers=headers
        )
        
        if positions_response.status_code == 200:
            positions = positions_response.json()
            
            print(f"\n📊 Total posiciones abiertas: {len(positions.get('positions', []))}")
            
            tesla_positions = []
            for pos in positions.get('positions', []):
                if 'TESLA' in pos.get('epic', '').upper() or 'TSLA' in pos.get('epic', '').upper():
                    tesla_positions.append(pos)
            
            if tesla_positions:
                print(f"\n🚗 POSICIONES DE TESLA ENCONTRADAS: {len(tesla_positions)}")
                for pos in tesla_positions:
                    print(f"\n   Deal ID: {pos.get('dealId')}")
                    print(f"   Epic: {pos.get('epic')}")
                    print(f"   Direction: {pos.get('direction')}")
                    print(f"   Size: {pos.get('size')}")
                    print(f"   Entry: ${pos.get('openLevel')}")
                    print(f"   Current: ${pos.get('closeLevel')}")
                    print(f"   P&L: ${pos.get('profit', 0):.2f}")
                    print(f"   Stop Loss: ${pos.get('stopLevel', 'N/A')}")
                    print(f"   Take Profit: ${pos.get('limitLevel', 'N/A')}")
                
                return tesla_positions
            else:
                print("\n⚠️  No hay posiciones de Tesla abiertas en la API")
                return []
        else:
            print(f"❌ Error obteniendo posiciones: {positions_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error conectando con API: {e}")
        return None

# ============================================
# PARTE 3: Sincronizar con BD
# ============================================
def sync_positions_to_db(conn, api_positions):
    if not conn or not api_positions:
        return
    
    print("\n" + "="*80)
    print("🔄 SINCRONIZANDO POSICIONES API -> BD")
    print("="*80)
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Crear sesión si no existe una activa
    cursor.execute("SELECT session_id FROM trading_sessions WHERE status = 'RUNNING' LIMIT 1")
    session = cursor.fetchone()
    
    if not session:
        print("\n📝 Creando nueva sesión de trading...")
        cursor.execute("""
            INSERT INTO trading_sessions (initial_balance, status)
            VALUES (10000, 'RUNNING')
            RETURNING session_id
        """)
        session = cursor.fetchone()
        conn.commit()
        print(f"✅ Sesión creada: #{session['session_id']}")
    
    session_id = session['session_id']
    
    # Sincronizar cada posición
    for pos in api_positions:
        deal_ref = pos.get('dealId')
        
        # Verificar si ya existe
        cursor.execute("SELECT trade_id FROM trades WHERE deal_reference = %s", (deal_ref,))
        existing = cursor.fetchone()
        
        if not existing:
            print(f"\n💾 Guardando nueva posición: {deal_ref}")
            cursor.execute("""
                INSERT INTO trades (
                    session_id, deal_reference, epic, direction,
                    entry_time, entry_price, position_size,
                    stop_loss, take_profit, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN')
                RETURNING trade_id
            """, (
                session_id,
                deal_ref,
                pos.get('epic'),
                pos.get('direction'),
                datetime.now(),
                float(pos.get('openLevel', 0)),
                float(pos.get('size', 0)),
                float(pos.get('stopLevel', 0)) if pos.get('stopLevel') else None,
                float(pos.get('limitLevel', 0)) if pos.get('limitLevel') else None
            ))
            
            trade_id = cursor.fetchone()['trade_id']
            print(f"✅ Guardada en BD con ID: {trade_id}")
        else:
            print(f"✅ Posición {deal_ref} ya existe en BD")
    
    conn.commit()
    
    # Verificar estado final
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open
        FROM trades
        WHERE epic LIKE '%TESLA%' OR epic LIKE '%TSLA%'
    """)
    
    stats = cursor.fetchone()
    print(f"\n📊 Estado final en BD:")
    print(f"   Total trades Tesla: {stats['total']}")
    print(f"   Trades abiertos: {stats['open']}")

# ============================================
# MAIN
# ============================================
def main():
    # Configurar BD
    conn = setup_database()
    if not conn:
        sys.exit(1)
    
    # Verificar posiciones en API
    api_positions = check_api_positions()
    
    # Sincronizar
    if api_positions:
        sync_positions_to_db(conn, api_positions)
    
    # Cerrar conexión
    if conn:
        conn.close()
    
    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80)

if __name__ == "__main__":
    main()
