# trading/core/bot_orchestrator.py
"""
Orquestador principal del bot - coordina todos los componentes
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from trading.core.market_scanner import MarketScanner
from trading.core.trade_executor import TradeExecutor
from trading.core.position_manager import PositionManager
from utils.bot_state import BotState
from utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class BotOrchestrator:
    """Coordina todos los componentes del bot"""
    
    def __init__(self, api_client, db_manager, config):
        self.api = api_client
        self.db = db_manager
        self.config = config
        
        # Estado compartido
        self.state = BotState()
        
        # Componentes
        self.scanner = None
        self.executor = None
        self.position_manager = None
        self.circuit_breaker = None
        
        # Control
        self.running = False
        self.session_id = None
        
    async def initialize(self, strategy, indicators):
        """Inicializa todos los componentes"""
        try:
            # Obtener balance inicial
            account = await self.api.get_account_info()
            balance = account.get('balance', 0)
            
            # Inicializar componentes
            self.scanner = MarketScanner(self.api, strategy, indicators, self.config)
            self.executor = TradeExecutor(self.api, self.db, self.config)
            self.position_manager = PositionManager(self.api, self.db)
            self.circuit_breaker = CircuitBreaker(self.config, balance)
            
            # Iniciar sesión en BD
            self.session_id = self.db.start_session(balance)
            
            logger.info(f"✅ Orquestador inicializado - Balance: €{balance:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando orquestador: {e}")
            return False
    
    async def run_cycle(self) -> Dict[str, Any]:
        """Ejecuta un ciclo completo de trading"""
        cycle_results = {
            'signals_found': 0,
            'trades_executed': 0,
            'positions_closed': 0,
            'errors': 0
        }
        
        try:
            # 1. Verificar circuit breaker
            if not self._check_trading_allowed():
                cycle_results['status'] = 'CIRCUIT_BREAKER_ACTIVE'
                return cycle_results
            
            # 2. Actualizar posiciones existentes
            await self._update_positions()
            
            # 3. Escanear mercado
            signals = await self.scanner.scan_assets(self.config.ASSETS)
            cycle_results['signals_found'] = len(signals)
            
            # 4. Filtrar señales (no repetir activos con posición)
            valid_signals = self._filter_signals(signals)
            
            # 5. Ejecutar señales válidas
            for signal in valid_signals:
                if await self._process_signal(signal):
                    cycle_results['trades_executed'] += 1
            
            # 6. Guardar snapshot
            await self._save_snapshot()
            
            cycle_results['status'] = 'SUCCESS'
            
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            cycle_results['errors'] += 1
            cycle_results['status'] = 'ERROR'
        
        return cycle_results
    
    def _check_trading_allowed(self) -> bool:
        """Verifica si se permite trading"""
        # Circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_trade():
            logger.warning("🛑 Circuit breaker activo")
            return False
        
        # Estado del bot
        if not self.state._running:
            return False
        
        # Límite de posiciones
        if self.position_manager:
            open_count = len(self.position_manager.get_active_positions())
            if open_count >= self.config.MAX_POSITIONS:
                logger.info(f"Máximo de posiciones alcanzado: {open_count}")
                return False
        
        return True
    
    async def _update_positions(self):
        """Actualiza estado de posiciones abiertas"""
        if not self.position_manager:
            return
        
        try:
            # Obtener posiciones desde API
            api_positions = await self.api.get_open_positions()
            
            # Sincronizar con position manager
            current_deals = {p['dealReference'] for p in api_positions}
            tracked_deals = set(self.position_manager.positions.keys())
            
            # Detectar posiciones cerradas
            closed = tracked_deals - current_deals
            for deal_id in closed:
                logger.info(f"Posición cerrada detectada: {deal_id}")
                # TODO: Obtener precio de cierre y actualizar BD
                self.position_manager.positions.pop(deal_id, None)
            
        except Exception as e:
            logger.error(f"Error actualizando posiciones: {e}")
    
    def _filter_signals(self, signals: list) -> list:
        """Filtra señales válidas para ejecutar"""
        valid = []
        
        for signal in signals:
            epic = signal.get('epic')
            
            # No duplicar posiciones en mismo activo
            if self.position_manager and epic in [p.epic for p in self.position_manager.get_active_positions()]:
                logger.info(f"Ya existe posición en {epic}, saltando")
                continue
            
            valid.append(signal)
        
        return valid
    
    async def _process_signal(self, signal: Dict) -> bool:
        """Procesa y ejecuta una señal"""
        try:
            # Ejecutar trade
            deal_id = await self.executor.execute_signal(signal)
            
            if deal_id:
                # Registrar en position manager
                if self.position_manager:
                    await self.position_manager.open_position(signal)
                
                # Actualizar circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.register_trade()
                
                return True
                
        except Exception as e:
            logger.error(f"Error procesando señal: {e}")
        
        return False
    
    async def _save_snapshot(self):
        """Guarda snapshot del estado actual"""
        try:
            account = await self.api.get_account_info()
            
            snapshot_data = {
                'balance': account.get('balance', 0),
                'available': account.get('available', 0),
                'margin_used': account.get('deposit', 0),
                'margin_percent': account.get('usedMargin', 0),
                'open_positions_count': len(self.position_manager.positions) if self.position_manager else 0,
                'total_pnl': account.get('profitLoss', 0)
            }
            
            self.db.save_account_snapshot(snapshot_data)
            
        except Exception as e:
            logger.error(f"Error guardando snapshot: {e}")
    
    async def shutdown(self):
        """Cierra ordenadamente todos los componentes"""
        logger.info("Cerrando orquestador...")
        
        # Finalizar sesión en BD
        if self.session_id:
            try:
                account = await self.api.get_account_info()
                self.db.end_session(account.get('balance', 0))
            except:
                pass
        
        self.running = False