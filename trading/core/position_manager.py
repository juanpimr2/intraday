"""
Gestión de posiciones y órdenes
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Representa una posición abierta"""
    deal_id: str
    epic: str
    direction: str
    size: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    @property
    def margin_required(self) -> float:
        """Calcula el margen requerido para esta posición"""
        return self.size * self.entry_price * 0.2  # 20% margen


class PositionManager:
    """Gestiona las posiciones abiertas"""
    
    def __init__(self, api_client, db_manager=None):
        self.api = api_client
        self.db = db_manager
        self.positions: Dict[str, Position] = {}
        
    async def open_position(self, signal: Dict[str, Any]) -> Optional[str]:
        """Abre una nueva posición basada en una señal"""
        try:
            # Crear orden
            order_data = self._build_order(signal)
            
            # Ejecutar orden via API
            result = await self.api.place_order(order_data)
            
            if result and result.get('dealReference'):
                # Crear objeto Position
                position = Position(
                    deal_id=result['dealReference'],
                    epic=signal['epic'],
                    direction=signal['direction'],
                    size=order_data['size'],
                    entry_price=result.get('level', signal['price']),
                    stop_loss=order_data.get('stopLevel'),
                    take_profit=order_data.get('limitLevel')
                )
                
                # Guardar en memoria
                self.positions[position.deal_id] = position
                
                # Guardar en BD si está disponible
                if self.db:
                    self.db.save_trade_open({
                        'deal_reference': position.deal_id,
                        'epic': position.epic,
                        'direction': position.direction,
                        'entry_price': position.entry_price,
                        'position_size': position.size,
                        'stop_loss': position.stop_loss,
                        'take_profit': position.take_profit,
                        'margin_used': position.margin_required,
                        'confidence': signal.get('confidence', 0)
                    })
                
                logger.info(f"✅ Posición abierta: {position.deal_id}")
                return position.deal_id
                
        except Exception as e:
            logger.error(f"Error abriendo posición: {e}")
            return None
    
    async def close_position(self, deal_id: str, reason: str = 'MANUAL') -> bool:
        """Cierra una posición existente"""
        try:
            # Cerrar via API
            result = await self.api.close_position(deal_id)
            
            if result:
                # Obtener precio de cierre
                exit_price = result.get('level', 0)
                
                # Actualizar BD
                if self.db and deal_id in self.positions:
                    self.db.close_trade(deal_id, exit_price, reason)
                
                # Eliminar de memoria
                if deal_id in self.positions:
                    del self.positions[deal_id]
                
                logger.info(f"✅ Posición cerrada: {deal_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error cerrando posición {deal_id}: {e}")
            return False
    
    def _build_order(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Construye los datos de la orden"""
        return {
            'epic': signal['epic'],
            'direction': signal['direction'],
            'size': signal.get('size', 0.1),
            'orderType': 'MARKET',
            'stopLevel': signal.get('stop_loss'),
            'limitLevel': signal.get('take_profit'),
            'guaranteedStop': False,
            'forceOpen': True
        }
    
    def get_active_positions(self) -> List[Position]:
        """Retorna lista de posiciones activas"""
        return list(self.positions.values())
    
    def get_position(self, deal_id: str) -> Optional[Position]:
        """Obtiene una posición específica"""
        return self.positions.get(deal_id)
    
    def total_margin_used(self) -> float:
        """Calcula el margen total usado"""
        return sum(pos.margin_required for pos in self.positions.values())