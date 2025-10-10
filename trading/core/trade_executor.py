# trading/core/trade_executor.py
"""
Ejecutor de operaciones de trading
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Ejecuta y gestiona operaciones de trading"""
    
    def __init__(self, api_client, db_manager, config):
        self.api = api_client
        self.db = db_manager
        self.config = config
        
    async def execute_signal(self, signal: Dict[str, Any]) -> Optional[str]:
        """Ejecuta una señal de trading"""
        try:
            # Calcular tamaño de posición
            size = self._calculate_position_size(signal)
            if size <= 0:
                logger.warning(f"Tamaño de posición inválido: {size}")
                return None
            
            # Preparar orden
            order = self._prepare_order(signal, size)
            
            # Ejecutar orden
            logger.info(f"📤 Ejecutando orden: {signal['epic']} {signal['direction']}")
            result = await self.api.place_order(order)
            
            if result and result.get('dealReference'):
                deal_id = result['dealReference']
                
                # Guardar en BD
                self._save_to_database(signal, result, size)
                
                logger.info(f"✅ Orden ejecutada: {deal_id}")
                return deal_id
            else:
                logger.error(f"❌ Fallo al ejecutar orden: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error ejecutando señal: {e}")
            return None
    
    async def close_position(self, deal_id: str, reason: str = 'MANUAL') -> bool:
        """Cierra una posición existente"""
        try:
            result = await self.api.close_position(deal_id)
            
            if result:
                # Actualizar BD
                exit_price = result.get('level', 0)
                self.db.close_trade(deal_id, exit_price, reason)
                
                logger.info(f"✅ Posición cerrada: {deal_id} - Razón: {reason}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cerrando posición {deal_id}: {e}")
            return False
    
    def _calculate_position_size(self, signal: Dict[str, Any]) -> float:
        """Calcula el tamaño apropiado de la posición"""
        # Por ahora usar tamaño fijo
        # TODO: Implementar cálculo dinámico basado en riesgo
        base_size = self.config.MIN_POSITION_SIZE
        
        # Ajustar por confianza
        confidence = signal.get('confidence', 0.5)
        adjusted_size = base_size * (0.5 + confidence)
        
        return round(adjusted_size, 2)
    
    def _prepare_order(self, signal: Dict[str, Any], size: float) -> Dict:
        """Prepara los datos de la orden"""
        return {
            'epic': signal['epic'],
            'direction': signal['direction'],
            'size': size,
            'orderType': 'MARKET',
            'stopLevel': signal.get('stop_loss'),
            'limitLevel': signal.get('take_profit'),
            'guaranteedStop': False,
            'forceOpen': True
        }
    
    def _save_to_database(self, signal: Dict, result: Dict, size: float):
        """Guarda la operación en la base de datos"""
        try:
            trade_data = {
                'deal_reference': result['dealReference'],
                'epic': signal['epic'],
                'direction': signal['direction'],
                'entry_price': result.get('level', signal.get('entry_price')),
                'position_size': size,
                'stop_loss': signal.get('stop_loss'),
                'take_profit': signal.get('take_profit'),
                'confidence': signal.get('confidence', 0),
                'margin_used': size * result.get('level', 0) * 0.2
            }
            
            self.db.save_trade_open(trade_data)
            
        except Exception as e:
            logger.error(f"Error guardando trade en BD: {e}")