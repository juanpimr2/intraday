# trading/core/position_manager.py
"""
Gestión de posiciones - COMPLETO con todos los métodos requeridos
Compatible con trading_bot.py + funcionalidades nuevas
"""

import math
import logging
from typing import Dict, Tuple, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from config import Config
from utils.helpers import safe_float, looks_like_equity

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
    """
    Gestiona posiciones, margen y sizing
    Compatible con trading_bot.py original + nuevas funcionalidades
    """
    
    def __init__(self, api_client, db_manager=None):
        self.api = api_client
        self.db = db_manager
        self.market_details_cache: Dict[str, Dict] = {}
        self.positions: Dict[str, Position] = {}
        
    # ============================================
    # MÉTODOS REQUERIDOS POR TRADING_BOT.PY
    # ============================================
    
    def get_account_balance(self, account_info: Dict) -> Tuple[float, float]:
        """
        Obtiene balance y disponible de la cuenta
        
        Args:
            account_info: Dict con info de la cuenta desde API
            
        Returns:
            tuple: (balance, disponible)
        """
        balance = safe_float(account_info.get('balance', {}).get('balance', 0))
        available = safe_float(account_info.get('balance', {}).get('available', 0))
        return balance, available
    
    def calculate_margin_used(self, account_info: Dict) -> float:
        """
        Calcula el margen usado (balance - disponible)
        
        Args:
            account_info: Dict con info de la cuenta
            
        Returns:
            float: Margen usado en EUR
        """
        balance, available = self.get_account_balance(account_info)
        return max(balance - available, 0.0)
    
    def get_positions(self) -> List[Dict]:
        """
        Obtiene posiciones actuales desde la API
        
        Returns:
            List[Dict]: Lista de posiciones abiertas
        """
        try:
            return self.api.get_positions()
        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return []
    
    def get_margin_by_asset(self) -> Dict[str, float]:
        """
        Calcula el margen usado por cada activo
        
        Returns:
            Dict: {epic: margen_usado}
        """
        margin_by_asset = {}
        
        for position in self.get_positions():
            pos_data = position.get('position') or {}
            epic = pos_data.get('epic') or 'Unknown'
            level = safe_float(pos_data.get('level', 0))
            size = safe_float(pos_data.get('size', 0))
            
            if level <= 0 or size <= 0 or epic == 'Unknown':
                continue
            
            details = self.get_market_details(epic)
            margin = self.calculate_margin(level, size, details, epic)
            margin_by_asset[epic] = margin_by_asset.get(epic, 0.0) + margin
        
        return margin_by_asset
    
    def get_market_details(self, epic: str) -> Dict:
        """
        Obtiene detalles del mercado (con caché)
        
        Args:
            epic: Identificador del activo
            
        Returns:
            Dict con: leverage, marginRate, minSize, stepSize, precision
        """
        if epic in self.market_details_cache:
            return self.market_details_cache[epic]
        
        try:
            data = self.api.get_market_details(epic)
            details = self._parse_market_details(data, epic)
            self.market_details_cache[epic] = details
            return details
        except Exception as e:
            logger.warning(f"Error obteniendo detalles de {epic}: {e}. Usando fallback.")
            details = self._fallback_market_details(epic)
            self.market_details_cache[epic] = details
            return details
    
    def _parse_market_details(self, data: Dict, epic: str) -> Dict:
        """Parsea los detalles del mercado desde la respuesta de la API"""
        
        def deep_search(d, keys):
            """Búsqueda recursiva de keys en dict anidado"""
            if not isinstance(d, dict):
                return None
            for k in keys:
                if k in d and d[k]:
                    return d[k]
            for v in d.values():
                if isinstance(v, dict):
                    result = deep_search(v, keys)
                    if result is not None:
                        return result
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            result = deep_search(item, keys)
                            if result is not None:
                                return result
            return None
        
        details = {}
        details['leverage'] = deep_search(data, ['leverage', 'leverageFactor'])
        margin_rate = deep_search(data, ['marginRate', 'marginFactor'])
        
        try:
            if margin_rate is not None:
                margin_rate_float = float(margin_rate)
                if margin_rate_float > 1:
                    details['marginRate'] = margin_rate_float / 100
                else:
                    details['marginRate'] = margin_rate_float
            else:
                details['marginRate'] = None
        except Exception:
            details['marginRate'] = None
        
        details['minSize'] = safe_float(
            deep_search(data, ['minDealSize', 'minSize']),
            Config.MIN_POSITION_SIZE
        )
        details['stepSize'] = safe_float(
            deep_search(data, ['dealSizeStep', 'stepSize']),
            0.01
        )
        details['precision'] = int(safe_float(
            deep_search(data, ['lotSizePrecision']),
            2
        ))
        
        if not details['marginRate'] and not details['leverage']:
            details['marginRate'] = 0.20 if looks_like_equity(epic) else 0.05
        
        return details
    
    def _fallback_market_details(self, epic: str) -> Dict:
        """Detalles de mercado con fallback conservador"""
        return {
            'leverage': None,
            'marginRate': 0.20 if looks_like_equity(epic) else 0.05,
            'minSize': Config.MIN_POSITION_SIZE,
            'stepSize': 0.01,
            'precision': 2
        }
    
    def calculate_margin(self, price: float, size: float, market_details: Dict, epic: str = None) -> float:
        """
        Calcula el margen requerido para una posición
        
        Args:
            price: Precio del activo
            size: Tamaño de la posición
            market_details: Detalles del mercado
            epic: Identificador del activo (opcional)
            
        Returns:
            float: Margen requerido en EUR
        """
        price = safe_float(price)
        size = safe_float(size)
        
        leverage = market_details.get('leverage')
        margin_rate = market_details.get('marginRate')
        
        if leverage and leverage > 0:
            return (price * size) / leverage
        if margin_rate and margin_rate > 0:
            return price * size * margin_rate
        
        fallback_rate = 0.20 if (epic and looks_like_equity(epic)) else 0.05
        return price * size * fallback_rate
    
    def calculate_position_size(self, epic: str, price: float, target_margin: float) -> Tuple[float, Dict, float]:
        """
        Calcula el tamaño de posición para un margen objetivo
        
        Args:
            epic: Identificador del activo
            price: Precio actual
            target_margin: Margen objetivo en EUR
            
        Returns:
            tuple: (size, market_details, estimated_margin)
        """
        price = safe_float(price)
        target_margin = safe_float(target_margin)
        
        details = self.get_market_details(epic)
        
        margin_rate = details.get('marginRate')
        leverage = details.get('leverage')
        step = safe_float(details.get('stepSize', 0.01), 0.01)
        min_size = safe_float(details.get('minSize', Config.MIN_POSITION_SIZE))
        precision = int(safe_float(details.get('precision', 2)))
        
        # Calcular tamaño base
        if margin_rate and margin_rate > 0:
            size_raw = target_margin / max(price * margin_rate, 1e-9)
        elif leverage and leverage > 0:
            size_raw = (target_margin * leverage) / max(price, 1e-9)
        else:
            fallback_rate = 0.20 if looks_like_equity(epic) else 0.05
            size_raw = target_margin / max(price * fallback_rate, 1e-9)
        
        # Ajustar a step, mínimo y precisión
        size_adjusted = math.floor(size_raw / step) * step
        if size_adjusted < min_size:
            size_adjusted = min_size
        size = round(size_adjusted, precision)
        
        margin_est = self.calculate_margin(price, size, details, epic)
        
        return size, details, margin_est
    
    # ============================================
    # STOP LOSS / TAKE PROFIT
    # ============================================
    
    def calculate_stop_loss(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de stop loss
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR en porcentaje (opcional, para modo dinámico)
            
        Returns:
            float: Nivel de stop loss
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_stop_loss_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_stop_loss_static(price, direction)
    
    def calculate_take_profit(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de take profit
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR en porcentaje (opcional, para modo dinámico)
            
        Returns:
            float: Nivel de take profit
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_take_profit_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_take_profit_static(price, direction)
    
    def calculate_stop_loss_static(self, price: float, direction: str) -> float:
        """SL estático basado en porcentajes fijos"""
        if direction == 'BUY':
            return round(price * (1 - Config.STOP_LOSS_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 + Config.STOP_LOSS_PERCENT_SELL), 2)
    
    def calculate_take_profit_static(self, price: float, direction: str) -> float:
        """TP estático basado en porcentajes fijos"""
        if direction == 'BUY':
            return round(price * (1 + Config.TAKE_PROFIT_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 - Config.TAKE_PROFIT_PERCENT_SELL), 2)
    
    def calculate_stop_loss_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        """SL dinámico basado en ATR"""
        sl_distance_percent = atr_percent * Config.ATR_MULTIPLIER_SL
        sl_distance_percent = max(sl_distance_percent, 1.0)
        sl_distance_percent = min(sl_distance_percent, 10.0)
        
        if direction == 'BUY':
            sl_level = price * (1 - sl_distance_percent / 100)
        else:  # SELL
            sl_level = price * (1 + sl_distance_percent / 100)
        
        return round(sl_level, 2)
    
    def calculate_take_profit_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        """TP dinámico basado en ATR"""
        tp_distance_percent = atr_percent * Config.ATR_MULTIPLIER_TP
        tp_distance_percent = max(tp_distance_percent, 2.0)
        tp_distance_percent = min(tp_distance_percent, 15.0)
        
        if direction == 'BUY':
            tp_level = price * (1 + tp_distance_percent / 100)
        else:  # SELL
            tp_level = price * (1 - tp_distance_percent / 100)
        
        return round(tp_level, 2)
    
    def get_risk_reward_ratio(self, price: float, stop_loss: float, take_profit: float, direction: str) -> float:
        """
        Calcula el ratio riesgo/beneficio
        
        Args:
            price: Precio de entrada
            stop_loss: Nivel de stop loss
            take_profit: Nivel de take profit
            direction: 'BUY' o 'SELL'
            
        Returns:
            float: Ratio R/R (reward/risk)
        """
        if direction == 'BUY':
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
        else:  # SELL
            risk = abs(stop_loss - price)
            reward = abs(price - take_profit)
        
        return reward / risk if risk > 0 else 0.0
    
    # ============================================
    # MÉTODOS ASYNC (para uso futuro)
    # ============================================
    
    async def open_position(self, signal: Dict[str, Any]) -> Optional[str]:
        """Abre una nueva posición basada en una señal"""
        try:
            order_data = self._build_order(signal)
            result = await self.api.place_order(order_data)
            
            if result and result.get('dealReference'):
                position = Position(
                    deal_id=result['dealReference'],
                    epic=signal['epic'],
                    direction=signal['direction'],
                    size=order_data['size'],
                    entry_price=result.get('level', signal['price']),
                    stop_loss=order_data.get('stopLevel'),
                    take_profit=order_data.get('limitLevel')
                )
                
                self.positions[position.deal_id] = position
                
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
            result = await self.api.close_position(deal_id)
            
            if result:
                exit_price = result.get('level', 0)
                
                if self.db and deal_id in self.positions:
                    self.db.close_trade(deal_id, exit_price, reason)
                
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
        """Retorna lista de posiciones activas en memoria"""
        return list(self.positions.values())
    
    def get_position(self, deal_id: str) -> Optional[Position]:
        """Obtiene una posición específica"""
        return self.positions.get(deal_id)
    
    def total_margin_used(self) -> float:
        """Calcula el margen total usado (posiciones en memoria)"""
        return sum(pos.margin_required for pos in self.positions.values())