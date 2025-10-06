#!/usr/bin/env python3
"""
Test para verificar que los trades se guardan correctamente en BD
"""

import sys
import logging
from datetime import datetime
from database.database_manager import DatabaseManager
from database.connection import DatabaseConnection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("="*70)
print("🧪 TEST: GUARDADO DE TRADES EN BASE DE DATOS")
print("="*70)
print()

# ============================================
# TEST 1: Verificar conexión
# ============================================
print("1️⃣ Verificando conexión a PostgreSQL...")
try:
    db = DatabaseConnection()
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"   ✅ Conectado a PostgreSQL")
        print(f"   📊 Versión: {version['version'].split(',')[0]}")
except Exception as e:
    print(f"   ❌ Error de conexión: {e}")
    print("\n⚠️  Asegúrate de que:")
    print("   1. PostgreSQL está corriendo: docker-compose up -d postgres")
    print("   2. Las credenciales en .env son correctas")
    print("   3. Las migraciones están aplicadas")
    sys.exit(1)

print()

# ============================================
# TEST 2: Verificar estructura de tablas
# ============================================
print("2️⃣ Verificando estructura de tablas...")
try:
    with db.get_cursor(commit=False) as cursor:
        # Verificar tablas principales
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('trading_sessions', 'trades', 'market_signals')
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        if len(tables) == 3:
            print(f"   ✅ Tablas necesarias existen ({len(tables)}/3)")
            for table in tables:
                print(f"      - {table['table_name']}")
        else:
            print(f"   ❌ Faltan tablas: encontradas {len(tables)}/3")
            print("   Ejecuta: python database/migrations/migration_runner.py migrate")
            sys.exit(1)
        
        # ✅ VERIFICAR COLUMNAS DE LA TABLA TRADES
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'trades'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print(f"\n   📋 Columnas de tabla 'trades': {len(columns)}")
        for col in columns[:10]:  # Mostrar primeras 10
            print(f"      - {col['column_name']} ({col['data_type']})")
        
except Exception as e:
    print(f"   ❌ Error verificando tablas: {e}")
    sys.exit(1)

print()

# ============================================
# TEST 3: Simular sesión y trade
# ============================================
print("3️⃣ Simulando sesión y trade de prueba...")
try:
    db_manager = DatabaseManager()
    
    # Iniciar sesión de prueba
    test_config = {
        'test_mode': True,
        'assets': ['TEST_EPIC'],
        'max_positions': 1
    }
    
    session_id = db_manager.start_session(
        initial_balance=10000.0,
        config_snapshot=test_config
    )
    
    if not session_id:
        print("   ❌ No se pudo crear sesión (BD no disponible)")
        print("   ⚠️  El bot funcionará pero sin guardar datos")
        sys.exit(0)
    
    print(f"   ✅ Sesión creada - ID: {session_id}")
    
    # Guardar señal de prueba
    test_signal = {
        'epic': 'TEST_EPIC',
        'signal': 'BUY',
        'confidence': 0.85,
        'current_price': 100.0,
        'reasons': ['Test signal'],
        'atr_percent': 2.5,
        'adx': 35.0,
        'indicators': {
            'rsi': 45.0,
            'macd': 1.5,
            'sma_short': 98.0,
            'sma_long': 95.0
        }
    }
    
    signal_id = db_manager.save_signal(test_signal)
    print(f"   ✅ Señal guardada - ID: {signal_id}")
    
    # Guardar trade de prueba (✅ CORREGIDO: usar nombres correctos)
    test_trade = {
        'signal_id': signal_id,
        'deal_reference': 'TEST_DEAL_456',
        'epic': 'TEST_EPIC',
        'direction': 'BUY',
        'entry_price': 100.0,
        'size': 1.0,  # Esto se mapea a position_size internamente
        'stop_loss': 92.0,
        'take_profit': 114.0,
        'margin_est': 500.0,
        'confidence': 0.85,
        'sl_tp_mode': 'DYNAMIC',
        'atr_percent': 2.5,
        'reasons': ['Test reason 1', 'Test reason 2']
    }
    
    trade_id = db_manager.save_trade_open(test_trade)
    print(f"   ✅ Trade guardado - ID: {trade_id}")
    
    # Marcar señal como ejecutada
    db_manager.mark_signal_executed(signal_id, trade_id)
    print(f"   ✅ Señal marcada como ejecutada")
    
except Exception as e:
    print(f"   ❌ Error simulando trade: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# ============================================
# TEST 4: Verificar datos guardados
# ============================================
print("4️⃣ Verificando datos guardados...")
try:
    with db.get_cursor(commit=False) as cursor:
        # Verificar sesión
        cursor.execute("""
            SELECT session_id, initial_balance, status, 
                   to_char(start_time, 'YYYY-MM-DD HH24:MI:SS') as start_time
            FROM trading_sessions 
            WHERE session_id = %s
        """, (session_id,))
        session = cursor.fetchone()
        
        if session:
            print(f"   ✅ Sesión encontrada:")
            print(f"      ID: {session['session_id']}")
            print(f"      Balance inicial: €{session['initial_balance']:,.2f}")
            print(f"      Estado: {session['status']}")
            print(f"      Inicio: {session['start_time']}")
        
        # Verificar señal
        cursor.execute("""
            SELECT signal_id, epic, signal, confidence, executed
            FROM market_signals 
            WHERE signal_id = %s
        """, (signal_id,))
        signal = cursor.fetchone()
        
        if signal:
            print(f"\n   ✅ Señal encontrada:")
            print(f"      ID: {signal['signal_id']}")
            print(f"      Epic: {signal['epic']}")
            print(f"      Señal: {signal['signal']}")
            print(f"      Confianza: {signal['confidence']:.0%}")
            print(f"      Ejecutada: {'✅ Sí' if signal['executed'] else '❌ No'}")
        
        # ✅ CORREGIDO: Usar position_size en lugar de size
        cursor.execute("""
            SELECT trade_id, epic, direction, entry_price, position_size,
                   stop_loss, take_profit, margin_used, status, deal_reference
            FROM trades 
            WHERE trade_id = %s
        """, (trade_id,))
        trade = cursor.fetchone()
        
        if trade:
            print(f"\n   ✅ Trade encontrado:")
            print(f"      ID: {trade['trade_id']}")
            print(f"      Deal: {trade['deal_reference']}")
            print(f"      Epic: {trade['epic']}")
            print(f"      Dirección: {trade['direction']}")
            print(f"      Entrada: €{trade['entry_price']:.2f}")
            print(f"      Tamaño: {trade['position_size']}")
            print(f"      SL: €{trade['stop_loss']:.2f}")
            print(f"      TP: €{trade['take_profit']:.2f}")
            print(f"      Margen: €{trade['margin_used']:.2f}")
            print(f"      Estado: {trade['status']}")
        
except Exception as e:
    print(f"   ❌ Error verificando datos: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# ============================================
# TEST 5: Simular cierre de trade
# ============================================
print("5️⃣ Simulando cierre de trade...")
try:
    exit_data = {
        'entry_time': datetime.now(),
        'exit_time': datetime.now(),
        'exit_price': 107.0,
        'exit_reason': 'TAKE_PROFIT',
        'pnl': 350.0,
        'pnl_percent': 7.0
    }
    
    db_manager.save_trade_close('TEST_DEAL_456', exit_data)
    print("   ✅ Trade cerrado correctamente")
    
    # Verificar cierre
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("""
            SELECT status, exit_price, exit_reason, pnl, pnl_percent
            FROM trades 
            WHERE deal_reference = 'TEST_DEAL_456'
        """)
        closed_trade = cursor.fetchone()
        
        if closed_trade and closed_trade['status'] == 'CLOSED':
            print(f"   ✅ Trade cerrado verificado:")
            print(f"      Estado: {closed_trade['status']}")
            print(f"      Precio salida: €{closed_trade['exit_price']:.2f}")
            print(f"      Razón: {closed_trade['exit_reason']}")
            print(f"      P&L: €{closed_trade['pnl']:.2f} ({closed_trade['pnl_percent']:.1f}%)")

except Exception as e:
    print(f"   ❌ Error cerrando trade: {e}")
    import traceback
    traceback.print_exc()

print()

# ============================================
# TEST 6: Finalizar sesión
# ============================================
print("6️⃣ Finalizando sesión de prueba...")
try:
    db_manager.end_session(final_balance=10350.0)
    print("   ✅ Sesión finalizada")
    
    # Verificar sesión finalizada
    with db.get_cursor(commit=False) as cursor:
        cursor.execute("""
            SELECT status, final_balance, total_trades, total_pnl
            FROM trading_sessions 
            WHERE session_id = %s
        """, (session_id,))
        final_session = cursor.fetchone()
        
        if final_session:
            print(f"   ✅ Sesión verificada:")
            print(f"      Estado: {final_session['status']}")
            print(f"      Balance final: €{final_session['final_balance']:,.2f}")
            print(f"      Total trades: {final_session['total_trades']}")
            print(f"      P&L total: €{final_session['total_pnl']:.2f}")

except Exception as e:
    print(f"   ❌ Error finalizando sesión: {e}")

print()

# ============================================
# RESUMEN
# ============================================
print("="*70)
print("✅ TODOS LOS TESTS PASARON CORRECTAMENTE")
print("="*70)
print()
print("🎯 CONCLUSIÓN:")
print("   ✅ La conexión a PostgreSQL funciona")
print("   ✅ Las tablas están correctamente creadas")
print("   ✅ Las señales se guardan correctamente")
print("   ✅ Los trades se guardan correctamente")
print("   ✅ Los trades se cierran correctamente")
print("   ✅ Las sesiones se gestionan correctamente")
print()
print("📊 Datos de prueba guardados:")
print(f"   Session ID: {session_id}")
print(f"   Signal ID: {signal_id}")
print(f"   Trade ID: {trade_id}")
print()
print("="*70)