"""
Configuración compartida de pytest y fixtures globales
"""

import pytest
import os
import sys
from datetime import datetime

# Agregar path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.app import app
from database.database_manager import DatabaseManager
from database.connection import DatabaseConnection
from config import Config


# ============================================
# FIXTURES DE CONFIGURACIÓN
# ============================================

@pytest.fixture(scope='session')
def test_config():
    """Configuración para tests"""
    return {
        'testing': True,
        'database': 'testing',
        'api_timeout': 10
    }


# ============================================
# FIXTURES DE FLASK
# ============================================

@pytest.fixture(scope='module')
def flask_app():
    """App de Flask configurada para testing"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture(scope='module')
def client(flask_app):
    """Cliente de test de Flask"""
    with flask_app.test_client() as client:
        yield client


@pytest.fixture(scope='module')
def runner(flask_app):
    """CLI runner para testing"""
    return flask_app.test_cli_runner()


# ============================================
# FIXTURES DE BASE DE DATOS
# ============================================

@pytest.fixture(scope='session')
def db_connection():
    """Conexión a la base de datos para tests"""
    try:
        db = DatabaseConnection()
        yield db
    except Exception as e:
        pytest.skip(f"Base de datos no disponible: {e}")


@pytest.fixture(scope='module')
def db_manager(db_connection):
    """Database manager para tests"""
    return DatabaseManager()


@pytest.fixture(scope='function')
def clean_database(db_connection):
    """Limpia la base de datos antes de cada test (opcional)"""
    # Solo usar si quieres empezar con BD limpia
    # CUIDADO: Esto borra TODOS los datos
    pass


# ============================================
# FIXTURES DE DATOS DE PRUEBA
# ============================================

@pytest.fixture(scope='function')
def test_session(db_manager):
    """Crea una sesión de prueba"""
    session_id = db_manager.start_session(
        initial_balance=10000.0,
        config_snapshot={
            'assets': ['GOLD', 'TSLA'],
            'max_positions': 3,
            'test_mode': True
        }
    )
    
    yield session_id
    
    # Cleanup opcional
    # db_manager.delete_session(session_id)


@pytest.fixture(scope='function')
def test_trades(db_manager, test_session):
    """Crea trades de prueba"""
    trades = []
    
    # Trade ganador
    trade_id = db_manager.save_trade({
        'epic': 'GOLD',
        'direction': 'BUY',
        'entry_price': 1800.0,
        'exit_price': 1850.0,
        'size': 1.0,
        'entry_date': datetime.now(),
        'exit_date': datetime.now(),
        'pnl': 50.0,
        'pnl_percent': 2.78,
        'reason': 'TAKE_PROFIT',
        'confidence': 0.75,
        'indicators': {'rsi': 45.0, 'macd': 0.5}
    })
    trades.append(trade_id)
    
    # Trade perdedor
    trade_id = db_manager.save_trade({
        'epic': 'TSLA',
        'direction': 'SELL',
        'entry_price': 250.0,
        'exit_price': 255.0,
        'size': 2.0,
        'entry_date': datetime.now(),
        'exit_date': datetime.now(),
        'pnl': -10.0,
        'pnl_percent': -2.0,
        'reason': 'STOP_LOSS',
        'confidence': 0.65,
        'indicators': {'rsi': 70.0, 'macd': -0.3}
    })
    trades.append(trade_id)
    
    return trades


@pytest.fixture(scope='function')
def test_signals(db_manager, test_session):
    """Crea señales de prueba"""
    signals = []
    
    # Señal BUY ejecutada
    signal_id = db_manager.save_signal({
        'epic': 'GOLD',
        'signal_type': 'BUY',
        'confidence': 0.75,
        'current_price': 1800.0,
        'indicators': {'rsi': 45.0, 'macd': 0.5, 'adx': 25.0},
        'reasons': ['RSI oversold', 'MACD bullish'],
        'executed': True
    })
    signals.append(signal_id)
    
    # Señal SELL no ejecutada
    signal_id = db_manager.save_signal({
        'epic': 'TSLA',
        'signal_type': 'SELL',
        'confidence': 0.55,
        'current_price': 250.0,
        'indicators': {'rsi': 70.0, 'macd': -0.3, 'adx': 18.0},
        'reasons': ['RSI overbought'],
        'executed': False
    })
    signals.append(signal_id)
    
    return signals


# ============================================
# FIXTURES DE MOCKING (para tests sin API real)
# ============================================

@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock del API client para tests sin conexión real"""
    class MockCapitalClient:
        def authenticate(self):
            return True
        
        def get_account_info(self):
            return {
                'balance': {'balance': 10000.0, 'available': 8000.0}
            }
        
        def get_positions(self):
            return []
        
        def get_market_data(self, epic, resolution, max_values=200):
            return {
                'prices': [
                    {'closePrice': 1800.0, 'openPrice': 1795.0, 'highPrice': 1805.0, 'lowPrice': 1790.0}
                    for _ in range(100)
                ]
            }
        
        def place_order(self, order_data):
            return {'dealReference': 'MOCK-12345'}
    
    return MockCapitalClient()


# ============================================
# HOOKS DE PYTEST
# ============================================

def pytest_configure(config):
    """Configuración al inicio de pytest"""
    print("\n" + "="*70)
    print("🧪 INICIANDO TESTS DEL TRADING BOT")
    print("="*70)


def pytest_sessionfinish(session, exitstatus):
    """Al finalizar todos los tests"""
    print("\n" + "="*70)
    print("✅ TESTS COMPLETADOS")
    print("="*70)


def pytest_runtest_makereport(item, call):
    """Hook para capturar resultados de tests"""
    if call.when == "call":
        if call.excinfo is not None:
            # Test falló
            print(f"\n❌ FAILED: {item.nodeid}")
        else:
            # Test pasó
            print(f"✅ PASSED: {item.nodeid}")


# ============================================
# MARKERS PERSONALIZADOS
# ============================================

def pytest_collection_modifyitems(config, items):
    """Modifica la colección de tests para agregar markers automáticamente"""
    for item in items:
        # Auto-marcar tests de integración
        if "integration" in item.nodeid or "test_dashboard" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Auto-marcar tests lentos
        if "backtest" in item.nodeid or "export" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # Auto-marcar tests que requieren API
        if "api" in item.nodeid:
            item.add_marker(pytest.mark.api)


# ============================================
# FIXTURES DE CLEANUP
# ============================================

@pytest.fixture(scope='function', autouse=True)
def cleanup_exports():
    """Limpia archivos de export después de cada test"""
    yield
    
    # Limpiar exports generados en tests
    import glob
    export_files = glob.glob('exports/test_*')
    for file in export_files:
        try:
            os.remove(file)
        except:
            pass