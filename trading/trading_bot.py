# trading/trading_bot.py
"""
Bot de Trading Intraday - REFACTORIZADO Y SIMPLIFICADO
Orquesta todos los componentes del sistema
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from api.capital_client import CapitalClient
from strategies.intraday_strategy import IntradayStrategy
from indicators.technical import TechnicalIndicators
from database.database_manager import DatabaseManager
from trading.core.bot_orchestrator import BotOrchestrator
from utils.bot_controller import BotController
from utils.bot_state import BotState
from utils.logger_manager import SessionLogger
from config import Config

logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading principal - versión simplificada"""
    
    def __init__(self):
        """Inicializa el bot con configuración mínima"""
        self.config = Config
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.indicators = TechnicalIndicators()
        self.db_manager = DatabaseManager()
        self.controller = BotController()
        self.state = BotState()
        self.orchestrator = BotOrchestrator(self.api, self.db_manager, self.config)
        
        # Control
        self.running = False
        self.session_name = None
        
    async def initialize(self) -> bool:
        """Inicializa todos los componentes del bot"""
        try:
            # Setup logging
            self.session_name = datetime.now().strftime("[%d_%b_%Y] Sesion %H%M%S")
            self.session_logger = SessionLogger()
            self.session_logger.setup_session_logging(self.session_name)
            
            logger.info("="*60)
            logger.info("BOT INTRADAY TRADING - v7.0 REFACTORIZADO")
            logger.info("="*60)
            
            # Autenticar con API
            logger.info("Autenticando con Capital.com...")
            await self.api.authenticate()
            logger.info("✅ Autenticación exitosa")
            
            # Obtener info de cuenta
            account_info = await self.api.get_account_info()
            balance = account_info.get('balance', 0)
            available = account_info.get('available', 0)
            logger.info(f"💼 Balance: €{balance:.2f} | Disponible: €{available:.2f}")
            
            # Inicializar orquestador con todos los componentes
            await self.orchestrator.initialize(self.strategy, self.indicators)
            
            # Actualizar estado
            self.state.start()
            
            logger.info(f"📁 LOGS: {log_dir}")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando bot: {e}")
            return False
    
    async def run(self):
        """Loop principal del bot"""
        if not await self.initialize():
            logger.error("Fallo en inicialización, abortando...")
            return
        
        logger.info("🔄 LOOP PRINCIPAL INICIADO")
        self.running = True
        
        cycle_count = 0
        error_count = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Verificar si está pausado
                if self.controller.is_paused():
                    logger.info("⏸️  Bot pausado. Esperando comando...")
                    await asyncio.sleep(5)
                    continue
                
                cycle_count += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"📊 CICLO #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"{'='*50}")
                
                # Ejecutar ciclo de trading
                results = await self.orchestrator.run_cycle()
                
                # Log resultados del ciclo
                self._log_cycle_results(results)
                
                # Reset contador de errores si fue exitoso
                if results.get('status') == 'SUCCESS':
                    error_count = 0
                else:
                    error_count += 1
                
                # Verificar errores consecutivos
                if error_count >= max_consecutive_errors:
                    logger.error(f"❌ {error_count} errores consecutivos. Deteniendo bot...")
                    break
                
                # Esperar antes del próximo ciclo
                await asyncio.sleep(self.config.SCAN_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("⚠️  Interrupción manual detectada")
                break
                
            except Exception as e:
                logger.error(f"❌ Error en loop principal: {e}")
                error_count += 1
                await asyncio.sleep(30)
        
        await self.shutdown()
    
    def _log_cycle_results(self, results: dict):
        """Registra los resultados del ciclo"""
        status = results.get('status', 'UNKNOWN')
        
        if status == 'CIRCUIT_BREAKER_ACTIVE':
            logger.warning("🛑 Circuit breaker activo - trading pausado")
        elif status == 'SUCCESS':
            logger.info(f"✅ Ciclo completado:")
            logger.info(f"   📍 Señales encontradas: {results.get('signals_found', 0)}")
            logger.info(f"   📈 Trades ejecutados: {results.get('trades_executed', 0)}")
            logger.info(f"   📉 Posiciones cerradas: {results.get('positions_closed', 0)}")
        else:
            logger.warning(f"⚠️  Ciclo con errores: {results.get('errors', 0)}")
    
    async def shutdown(self):
        """Cierra el bot de manera ordenada"""
        logger.info("\n" + "="*60)
        logger.info("🛑 CERRANDO BOT...")
        logger.info("="*60)
        
        self.running = False
        self.state.stop()
        
        # Cerrar orquestador
        if self.orchestrator:
            await self.orchestrator.shutdown()
        
        # Cerrar API
        if self.api:
            await self.api.close()
        
        logger.info("✅ Bot cerrado correctamente")
        logger.info("="*60)
    
    def get_status(self) -> dict:
        """Retorna el estado actual del bot"""
        return {
            'running': self.running,
            'paused': self.controller.is_paused(),
            'session_name': self.session_name,
            'uptime_minutes': getattr(self.state, 'uptime_minutes', 0),
            'orchestrator_ready': self.orchestrator is not None
        }


async def main():
    """Función principal para ejecutar el bot"""
    bot = TradingBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupción por teclado")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
    finally:
        if bot.running:
            await bot.shutdown()


if __name__ == "__main__":
    # Configuración básica de logging para inicio
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Ejecutar bot
    asyncio.run(main())