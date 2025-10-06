#!/usr/bin/env python3
"""
Test del SessionLogger
"""

from utils.logger_manager import SessionLogger
import logging

logging.basicConfig(level=logging.INFO)

print("🧪 Testing SessionLogger...")
print()

# Test 1: Logger con sesión
print("1️⃣ Creando logger con session_id=999...")
logger = SessionLogger(session_id=999)
print(f"   ✅ Directorio: {logger.get_log_directory()}")

# Test 2: Log de señal
print("\n2️⃣ Guardando señal...")
logger.log_signal({
    'epic': 'TEST',
    'signal': 'BUY',
    'confidence': 0.85,
    'atr_percent': 2.5,
    'adx': 35.0,
    'reasons': ['Test reason 1', 'Test reason 2']
})
print("   ✅ Señal guardada")

# Test 3: Log de trade abierto
print("\n3️⃣ Guardando trade abierto...")
logger.log_trade_open({
    'deal_reference': 'TEST_123',
    'epic': 'TEST',
    'direction': 'BUY',
    'entry_price': 100.0,
    'size': 1.0,
    'stop_loss': 92.0,
    'take_profit': 114.0,
    'margin_est': 500.0,
    'confidence': 0.85,
    'sl_tp_mode': 'DYNAMIC',
    'atr_percent': 2.5,
    'reasons': ['Reason 1', 'Reason 2']
})
print("   ✅ Trade abierto guardado")

# Test 4: Log de trade cerrado
print("\n4️⃣ Guardando trade cerrado...")
logger.log_trade_close({
    'deal_reference': 'TEST_123',
    'epic': 'TEST',
    'exit_price': 107.0,
    'exit_reason': 'TAKE_PROFIT',
    'pnl': 350.0,
    'pnl_percent': 7.0,
    'duration_minutes': 125
})
print("   ✅ Trade cerrado guardado")

# Test 5: Log de resumen
print("\n5️⃣ Guardando resumen de escaneo...")
logger.log_scan_summary({
    'total_assets': 4,
    'signals_found': 2,
    'trades_executed': 1,
    'margin_used': 500.0
})
print("   ✅ Resumen guardado")

# Test 6: Cerrar logger
print("\n6️⃣ Cerrando logger...")
logger.close()
print("   ✅ Logger cerrado")

print()
print("="*60)
print("✅ TODOS LOS TESTS DEL LOGGER PASARON")
print("="*60)
print()
print(f"📁 Verifica los archivos en: {logger.get_log_directory()}")
print()
print("Archivos creados:")
print("  - trading_bot.log")
print("  - signals.log")
print("  - trades_opened.log")
print("  - trades_closed.log")
print("  - scans_summary.log")
print()