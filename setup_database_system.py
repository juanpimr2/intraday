#!/usr/bin/env python3
"""
Script de instalación automática del sistema de persistencia
Crea todos los archivos y directorios necesarios

Uso:
    python setup_database_system.py
"""

import os
from pathlib import Path


def create_directory(path: str):
    """Crea directorio si no existe"""
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"✅ Directorio: {path}")


def create_file(filepath: str, content: str):
    """Crea archivo con contenido"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Archivo: {filepath}")


def main():
    print("="*60)
    print("🗄️  INSTALACIÓN AUTOMÁTICA - SISTEMA DE PERSISTENCIA")
    print("="*60)
    print()
    
    base_dir = Path.cwd()
    
    # ============================================
    # PASO 1: Crear Directorios
    # ============================================
    print("📁 PASO 1: Creando estructura de directorios...")
    print()
    
    directories = [
        "database/migrations/versions",
        "database/queries",
        "dashboard/routes",
        "exports"
    ]
    
    for directory in directories:
        create_directory(directory)
    
    print()
    
    # ============================================
    # PASO 2: Crear __init__.py vacíos
    # ============================================
    print("📝 PASO 2: Creando archivos __init__.py...")
    print()
    
    init_files = [
        "database/migrations/__init__.py",
        "database/queries/__init__.py",
        "dashboard/routes/__init__.py"
    ]
    
    for init_file in init_files:
        create_file(init_file, "")
    
    print()
    
    # ============================================
    # PASO 3: Crear migration_runner.py
    # ============================================
    print("🔧 PASO 3: Creando migration_runner.py...")
    print()
    
    migration_runner_content = '''"""
Sistema de migraciones de base de datos (estilo Flyway)
Gestiona versiones de schema y permite rollbacks
"""

import os
import logging
import psycopg2
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Gestor de migraciones de base de datos"""
    
    def __init__(self, connection_params: dict):
        """
        Inicializa el runner de migraciones
        
        Args:
            connection_params: Dict con host, port, database, user, password
        """
        self.conn_params = connection_params
        self.migrations_dir = Path(__file__).parent / 'versions'
        self.seeds_dir = Path(__file__).parent / 'seeds'
    
    def _get_connection(self):
        """Obtiene conexión a la base de datos"""
        return psycopg2.connect(**self.conn_params)
    
    def _ensure_migrations_table(self):
        """Crea la tabla de control de migraciones si no existe"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(50) PRIMARY KEY,
                    description VARCHAR(500),
                    applied_at TIMESTAMP DEFAULT NOW(),
                    execution_time_ms INTEGER,
                    checksum VARCHAR(64),
                    success BOOLEAN DEFAULT TRUE
                )
            """)
            conn.commit()
            logger.info("✅ Tabla de migraciones verificada")
        except Exception as e:
            logger.error(f"Error creando tabla de migraciones: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_applied_migrations(self) -> List[str]:
        """Obtiene lista de migraciones ya aplicadas"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT version FROM schema_migrations 
                WHERE success = TRUE 
                ORDER BY version
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
    
    def get_pending_migrations(self) -> List[Tuple[str, Path]]:
        """Obtiene migraciones pendientes de aplicar"""
        applied = set(self.get_applied_migrations())
        
        migration_files = sorted(self.migrations_dir.glob('v*.sql'))
        
        pending = []
        for filepath in migration_files:
            version = filepath.stem
            if version not in applied:
                pending.append((version, filepath))
        
        return pending
    
    def apply_migration(self, version: str, filepath: Path) -> bool:
        """Aplica una migración específica"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            import hashlib
            checksum = hashlib.sha256(sql_content.encode()).hexdigest()
            
            description = version.replace('_', ' ').replace('v', 'Version ')
            
            logger.info(f"⏳ Aplicando migración: {version}")
            start_time = datetime.now()
            
            cursor.execute(sql_content)
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            cursor.execute("""
                INSERT INTO schema_migrations 
                (version, description, execution_time_ms, checksum, success)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (version, description, execution_time, checksum))
            
            conn.commit()
            logger.info(f"✅ Migración {version} aplicada ({execution_time}ms)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error aplicando migración {version}: {e}")
            conn.rollback()
            
            try:
                cursor.execute("""
                    INSERT INTO schema_migrations 
                    (version, description, success)
                    VALUES (%s, %s, FALSE)
                """, (version, f"FAILED: {str(e)[:200]}"))
                conn.commit()
            except:
                pass
            
            return False
        finally:
            cursor.close()
            conn.close()
    
    def migrate(self, target_version: str = None):
        """Ejecuta todas las migraciones pendientes"""
        logger.info("="*60)
        logger.info("🗄️  EJECUTANDO MIGRACIONES")
        logger.info("="*60)
        
        self._ensure_migrations_table()
        
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("✅ Base de datos actualizada (no hay migraciones pendientes)")
            return
        
        logger.info(f"📋 {len(pending)} migración(es) pendiente(s)")
        
        for version, filepath in pending:
            if target_version and version > target_version:
                logger.info(f"⏹️  Detenido en versión objetivo: {target_version}")
                break
            
            success = self.apply_migration(version, filepath)
            
            if not success:
                logger.error(f"❌ Migración fallida: {version}. Abortando.")
                break
        
        logger.info("="*60)
        logger.info("✅ Migraciones completadas")
        logger.info("="*60)
    
    def status(self):
        """Muestra estado de las migraciones"""
        logger.info("="*60)
        logger.info("📊 ESTADO DE MIGRACIONES")
        logger.info("="*60)
        
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        
        logger.info(f"✅ Aplicadas: {len(applied)}")
        for version in applied:
            logger.info(f"   - {version}")
        
        if pending:
            logger.info(f"\\n⏳ Pendientes: {len(pending)}")
            for version, _ in pending:
                logger.info(f"   - {version}")
        else:
            logger.info("\\n✅ No hay migraciones pendientes")
        
        logger.info("="*60)


def run_migrations():
    """Función helper para ejecutar migraciones desde línea de comandos"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    connection_params = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trading_bot'),
        'user': os.getenv('POSTGRES_USER', 'trader'),
        'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
    }
    
    runner = MigrationRunner(connection_params)
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'migrate':
            runner.migrate()
        elif command == 'status':
            runner.status()
        else:
            print("Comandos disponibles:")
            print("  python migration_runner.py migrate    - Ejecutar migraciones")
            print("  python migration_runner.py status     - Ver estado")
    else:
        runner.migrate()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    run_migrations()
'''
    
    create_file("database/migrations/migration_runner.py", migration_runner_content)
    
    print()
    
    # ============================================
    # PASO 4: Crear v001_initial_schema.sql
    # ============================================
    print("🗄️  PASO 4: Creando v001_initial_schema.sql...")
    print()
    
    # Contenido SQL demasiado largo, lo pongo en un string separado
    v001_content = """-- v001_initial_schema.sql
-- Schema inicial del bot de trading

CREATE TABLE IF NOT EXISTS strategy_versions (
    version_id SERIAL PRIMARY KEY,
    version_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    config_snapshot JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE,
    changes TEXT[],
    expected_improvements TEXT,
    backtest_win_rate DECIMAL(6, 4),
    backtest_profit_factor DECIMAL(8, 4),
    backtest_total_trades INTEGER,
    demo_win_rate DECIMAL(6, 4),
    demo_days_tested INTEGER
);

CREATE INDEX idx_strategy_versions_active ON strategy_versions(is_active, created_at DESC);

CREATE TABLE IF NOT EXISTS trading_sessions (
    session_id SERIAL PRIMARY KEY,
    strategy_version_id INTEGER REFERENCES strategy_versions(version_id),
    start_time TIMESTAMP NOT NULL DEFAULT NOW(),
    end_time TIMESTAMP,
    initial_balance DECIMAL(12, 2) NOT NULL,
    final_balance DECIMAL(12, 2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(12, 2) DEFAULT 0,
    max_drawdown DECIMAL(8, 4),
    status VARCHAR(20) DEFAULT 'RUNNING',
    config_snapshot JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_start_time ON trading_sessions(start_time DESC);
CREATE INDEX idx_sessions_strategy ON trading_sessions(strategy_version_id, start_time DESC);

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    balance DECIMAL(12, 2) NOT NULL,
    available DECIMAL(12, 2) NOT NULL,
    margin_used DECIMAL(12, 2) NOT NULL,
    margin_percent DECIMAL(8, 4) NOT NULL,
    open_positions_count INTEGER DEFAULT 0,
    equity DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_snapshots_session ON account_snapshots(session_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS market_signals (
    signal_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    epic VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    signal VARCHAR(10) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    current_price DECIMAL(12, 6) NOT NULL,
    rsi DECIMAL(6, 2),
    macd DECIMAL(12, 6),
    macd_signal DECIMAL(12, 6),
    macd_hist DECIMAL(12, 6),
    sma_short DECIMAL(12, 6),
    sma_long DECIMAL(12, 6),
    momentum DECIMAL(8, 4),
    atr_percent DECIMAL(8, 4),
    adx DECIMAL(6, 2),
    plus_di DECIMAL(6, 2),
    minus_di DECIMAL(6, 2),
    slow_trend VARCHAR(20),
    reasons TEXT[],
    indicators_json JSONB,
    executed BOOLEAN DEFAULT FALSE,
    trade_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_signals_session_epic ON market_signals(session_id, epic, timestamp DESC);
CREATE INDEX idx_signals_executed ON market_signals(executed, timestamp DESC);
CREATE INDEX idx_signals_confidence ON market_signals(confidence DESC);

CREATE TABLE IF NOT EXISTS trades (
    trade_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    signal_id INTEGER REFERENCES market_signals(signal_id),
    deal_reference VARCHAR(100),
    epic VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_price DECIMAL(12, 6) NOT NULL,
    position_size DECIMAL(12, 6) NOT NULL,
    stop_loss DECIMAL(12, 6) NOT NULL,
    take_profit DECIMAL(12, 6) NOT NULL,
    margin_used DECIMAL(12, 2) NOT NULL,
    confidence DECIMAL(5, 4),
    sl_tp_mode VARCHAR(20),
    atr_at_entry DECIMAL(8, 4),
    exit_time TIMESTAMP,
    exit_price DECIMAL(12, 6),
    exit_reason VARCHAR(50),
    pnl DECIMAL(12, 2),
    pnl_percent DECIMAL(8, 4),
    duration_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'OPEN',
    entry_reasons TEXT[],
    entry_indicators JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_session ON trades(session_id, entry_time DESC);
CREATE INDEX idx_trades_epic ON trades(epic, entry_time DESC);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_pnl ON trades(pnl DESC NULLS LAST);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason);

CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    period_type VARCHAR(20) NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(6, 4),
    total_pnl DECIMAL(12, 2) DEFAULT 0,
    avg_win DECIMAL(12, 2),
    avg_loss DECIMAL(12, 2),
    largest_win DECIMAL(12, 2),
    largest_loss DECIMAL(12, 2),
    profit_factor DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    avg_trade_duration_minutes INTEGER,
    sharpe_ratio DECIMAL(8, 4),
    metrics_by_epic JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_metrics_session_period ON performance_metrics(session_id, period_type, period_start DESC);

CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id SERIAL PRIMARY KEY,
    strategy_version_id INTEGER REFERENCES strategy_versions(version_id),
    backtest_name VARCHAR(200) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(12, 2) NOT NULL,
    final_capital DECIMAL(12, 2) NOT NULL,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate DECIMAL(6, 4),
    total_return DECIMAL(12, 2),
    total_return_percent DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    profit_factor DECIMAL(8, 4),
    sharpe_ratio DECIMAL(8, 4),
    avg_trade_duration_minutes INTEGER,
    config_used JSONB,
    trades_detail JSONB,
    equity_curve JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_backtest_version ON backtest_results(strategy_version_id, created_at DESC);
CREATE INDEX idx_backtest_date ON backtest_results(start_date DESC, end_date DESC);

CREATE TABLE IF NOT EXISTS system_logs (
    log_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,
    module VARCHAR(100),
    message TEXT NOT NULL,
    exception_trace TEXT,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_session_level ON system_logs(session_id, level, timestamp DESC);
CREATE INDEX idx_logs_timestamp ON system_logs(timestamp DESC);

COMMENT ON TABLE strategy_versions IS 'Versiones de la estrategia para comparar mejoras';
COMMENT ON TABLE trading_sessions IS 'Sesiones de trading del bot';
COMMENT ON TABLE trades IS 'Operaciones ejecutadas con entrada y salida';
"""
    
    create_file("database/migrations/versions/v001_initial_schema.sql", v001_content)
    
    print()
    
    # ============================================
    # PASO 5: Mensaje final
    # ============================================
    print("="*60)
    print("✅ INSTALACIÓN COMPLETADA")
    print("="*60)
    print()
    print("📋 Archivos creados:")
    print("   - database/migrations/migration_runner.py")
    print("   - database/migrations/versions/v001_initial_schema.sql")
    print("   - database/queries/__init__.py")
    print("   - dashboard/routes/__init__.py")
    print()
    print("📁 Directorios creados:")
    print("   - database/migrations/versions/")
    print("   - database/queries/")
    print("   - dashboard/routes/")
    print("   - exports/")
    print()
    print("🎯 PRÓXIMOS PASOS:")
    print()
    print("1. Instalar dependencias:")
    print("   pip install psycopg2-binary python-dotenv openpyxl")
    print()
    print("2. Levantar PostgreSQL:")
    print("   docker-compose up -d postgres")
    print()
    print("3. Ejecutar migraciones:")
    print("   python database/migrations/migration_runner.py migrate")
    print()
    print("4. Verificar estado:")
    print("   python database/migrations/migration_runner.py status")
    print()
    print("="*60)
    print()
    print("💡 NOTA: Faltan por crear manualmente:")
    print("   - database/migrations/versions/v002_analytics_views.sql")
    print("   - database/queries/analytics.py")
    print("   - dashboard/routes/export_routes.py")
    print()
    print("   Te los pasaré en el próximo mensaje si quieres.")
    print()


if __name__ == "__main__":
    main()