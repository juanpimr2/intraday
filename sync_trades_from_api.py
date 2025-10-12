import os
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

from api.capital_client import CapitalClient

def sync_trades_from_api():
    """Sincroniza trades desde la API a la BD"""
    print("="*70)
    print("🔄 SINCRONIZANDO OPERACIONES DESDE CAPITAL.COM")
    print("="*70)
    
    # Conectar a API
    api = CapitalClient()
    
    try:
        print("\n1️⃣ Autenticando con Capital.com...")
        if not api.authenticate():
            print("❌ Error en autenticación")
            return
        print("✅ Autenticado")
        
        print("\n2️⃣ Obteniendo posiciones abiertas...")
        positions = api.get_positions()
        print(f"✅ {len(positions)} posiciones encontradas")
        
        if not positions:
            print("\n⚠️ No hay posiciones abiertas")
            return
        
        # Mostrar todas las posiciones
        print("\n📊 Posiciones disponibles:")
        for pos in positions:
            epic = pos.get('market', {}).get('epic', 'Unknown')
            direction = pos.get('position', {}).get('direction', 'Unknown')
            size = pos.get('position', {}).get('size', 0)
            pnl = pos.get('position', {}).get('profit', 0)
            print(f"   - {epic}: {direction} x{size} | P&L: ${pnl:.2f}")
        
        # Filtrar Tesla
        tesla_positions = [p for p in positions if 'TESLA' in p.get('market', {}).get('epic', '').upper() 
                          or 'TSLA' in p.get('market', {}).get('epic', '').upper()]
        
        if not tesla_positions:
            print("\n⚠️ No hay posiciones de TESLA")
            return
        
        print(f"\n🚗 Sincronizando {len(tesla_positions)} posiciones de TESLA...")
        
        print("\n3️⃣ Conectando a PostgreSQL...")
        db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', 5432),
            'database': os.getenv('POSTGRES_DB', 'trading_bot'),
            'user': os.getenv('POSTGRES_USER', 'trader'),
            'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Conectado a BD")
        
        print("\n4️⃣ Creando/verificando sesión activa...")
        cursor.execute("SELECT session_id FROM trading_sessions WHERE status = 'RUNNING' ORDER BY start_time DESC LIMIT 1")
        session = cursor.fetchone()
        
        if not session:
            # Obtener balance (está anidado)
            account_info = api.get_account_info()
            balance = float(account_info.get('balance', {}).get('balance', 1000))
            
            cursor.execute("""
                INSERT INTO trading_sessions (initial_balance, status)
                VALUES (%s, 'RUNNING')
                RETURNING session_id
            """, (balance,))
            session_id = cursor.fetchone()['session_id']
            conn.commit()
            print(f"✅ Nueva sesión creada: #{session_id} | Balance: €{balance:.2f}")
        else:
            session_id = session['session_id']
            print(f"✅ Usando sesión existente: #{session_id}")
        
        print("\n5️⃣ Guardando operaciones en BD...")
        saved_count = 0
        skipped_count = 0
        
        for pos in tesla_positions:
            position_data = pos.get('position', {})
            market_data = pos.get('market', {})
            
            deal_id = position_data.get('dealId')
            epic = market_data.get('epic')
            
            # Verificar si ya existe
            cursor.execute("SELECT trade_id FROM trades WHERE deal_reference = %s", (deal_id,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"   ⏭️ {epic} ya existe (Trade #{existing['trade_id']})")
                skipped_count += 1
                continue
            
            # Insertar
            entry_price = float(position_data.get('level', 0))
            size = float(position_data.get('size', 0))
            stop_loss = position_data.get('stopLevel')
            take_profit = position_data.get('limitLevel')
            
            cursor.execute("""
                INSERT INTO trades (
                    session_id, deal_reference, epic, direction,
                    entry_time, entry_price, position_size,
                    stop_loss, take_profit, status, margin_used
                ) VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, 'OPEN', %s)
                RETURNING trade_id
            """, (
                session_id,
                deal_id,
                epic,
                position_data.get('direction'),
                entry_price,
                size,
                float(stop_loss) if stop_loss else None,
                float(take_profit) if take_profit else None,
                size * entry_price * 0.2
            ))
            
            trade_id = cursor.fetchone()['trade_id']
            saved_count += 1
            print(f"   ✅ {epic}: Trade #{trade_id} guardado")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n" + "="*70)
        print(f"✅ SINCRONIZACIÓN COMPLETADA")
        print(f"   Nuevos: {saved_count} | Ya existían: {skipped_count}")
        print("="*70)
        
        # Health check final
        if saved_count > 0:
            print("\n📊 Ejecutando health check...")
            import subprocess
            subprocess.run(["python", "health_check.py"])
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    sync_trades_from_api()
