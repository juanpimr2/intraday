"""
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
            logger.info(f"\n⏳ Pendientes: {len(pending)}")
            for version, _ in pending:
                logger.info(f"   - {version}")
        else:
            logger.info("\n✅ No hay migraciones pendientes")
        
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
