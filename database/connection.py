"""
Gestor de conexión a PostgreSQL con pool de conexiones
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import logging
import os
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Gestiona el pool de conexiones a PostgreSQL"""
    
    _instance: Optional['DatabaseConnection'] = None
    _pool: Optional[SimpleConnectionPool] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pool is None:
            self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializa el pool de conexiones"""
        try:
            # Intentar cargar desde .env
            from dotenv import load_dotenv
            load_dotenv()
            
            self._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', 5432)),
                database=os.getenv('POSTGRES_DB', 'trading_bot'),
                user=os.getenv('POSTGRES_USER', 'trader'),
                password=os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
            )
            logger.info("✅ Pool de conexiones PostgreSQL inicializado")
        except Exception as e:
            logger.error(f"❌ Error inicializando pool PostgreSQL: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager para obtener conexión del pool"""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error en conexión DB: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, commit=True):
        """
        Context manager para obtener cursor con auto-commit
        
        Args:
            commit: Si True, hace commit automático al salir
        
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM trades")
                data = cursor.fetchall()
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error en operación DB: {e}")
                raise
            finally:
                cursor.close()
    
    def close_pool(self):
        """Cierra el pool de conexiones"""
        if self._pool:
            self._pool.closeall()
            logger.info("Pool de conexiones cerrado")
