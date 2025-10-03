"""
Gestor de posiciones y margen con SL/TP dinámicos
"""

import math
import logging
from typing import Dict, Tuple, List
from config import Config
from utils.helpers import safe_float, looks_like_equity

logger = logging.getLogger(__name__)


class PositionManager:
    """Gestiona posiciones, margen y sizing con SL/TP adaptativos"""
    
    def __init__(self, api_client):
        self.api = api_client
        self.market_details_cache: Dict[str, Dict] = {}
    
    def get_account_balance(self, account_info: Dict) -> Tuple[float, float]:
        """
        Obtiene balance y disponible de la cuenta
        
        Returns:
            tuple: (balance, disponible)
        """
        balance = safe_float(account_info.get('balance', {}).get('balance', 0))
        available = safe_float(account_info.get('balance', {}).get('available', 0))
        return balance, available
    
    def calculate_margin_used(self, account_info: Dict) -> float:
        """
        Calcula el margen usado (balance - disponible)
        
        Returns:
            float: Margen usado en EUR
        """
        balance, available = self.get_account_balance(account_info)
        return max(balance - available, 0.0)
    
    def get_market_details(self, epic: str) -> Dict:
        """
        Obtiene detalles del mercado (con caché)
        
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
            return self._fallback_market_details(epic)
    
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
            details['marginRate'] = float(margin_rate) if margin_rate is not None else None
        except:
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
        
        # Fallback conservador si no hay leverage ni marginRate
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
            epic: Identificador del activo (opcional, para fallback)
            
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
        
        # Fallback conservador
        fallback_rate = 0.20 if (epic and looks_like_equity(epic)) else 0.05
        return price * size * fallback_rate
    
    def calculate_position_size(self, epic: str, price: float, target_margin: float) -> Tuple[float, Dict, float]:
        """
        Calcula el tamaño de posición para un margen objetivo
        
        CAMBIO PRINCIPAL: Ahora calcula correctamente el size para aproximarse al target_margin
        sin exceder los límites por activo.
        
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
        
        # Obtener parámetros de sizing
        step = safe_float(details.get('stepSize', 0.01), 0.01)
        min_size = safe_float(details.get('minSize', Config.MIN_POSITION_SIZE))
        precision = int(safe_float(details.get('precision', 2)))
        
        # Calcular margen rate efectivo
        if details.get('marginRate'):
            effective_margin_rate = details['marginRate']
        elif details.get('leverage') and details['leverage'] > 0:
            effective_margin_rate = 1.0 / details['leverage']
        else:
            effective_margin_rate = 0.20 if looks_like_equity(epic) else 0.05
        
        # Calcular tamaño para el target_margin
        # Fórmula: size = target_margin / (price * margin_rate)
        size_for_target = target_margin / max(price * effective_margin_rate, 1e-9)
        
        # Ajustar al step size (redondeando hacia ABAJO para no exceder)
        size = math.floor(size_for_target / step) * step
        
        # Aplicar tamaño mínimo
        size = max(size, min_size)
        
        # Aplicar precisión
        size = round(size, precision)
        
        # Calcular margen estimado REAL con el tamaño ajustado
        margin_est = self.calculate_margin(price, size, details, epic)
        
        logger.debug(
            f"{epic}: Size calculado={size:.{precision}f}, "
            f"Margen estimado=€{margin_est:.2f}, Target=€{target_margin:.2f}"
        )
        
        # Verificar si aún excede mucho el target
        if margin_est > target_margin * 1.2:  # Si excede en más del 20%
            logger.warning(
                f"⚠️  {epic}: Margen estimado (€{margin_est:.2f}) excede objetivo (€{target_margin:.2f}). "
                f"Ajustando..."
            )
            
            # Recalcular con 80% del target para dar margen de seguridad
            adjusted_target = target_margin * 0.8
            size_adjusted = adjusted_target / max(price * effective_margin_rate, 1e-9)
            
            # Re-ajustar
            size = math.floor(size_adjusted / step) * step
            size = max(size, min_size)
            size = round(size, precision)
            
            # Recalcular margen FINAL
            margin_est = self.calculate_margin(price, size, details, epic)
            
            logger.info(
                f"✅ {epic}: Size ajustado a {size:.{precision}f}, "
                f"Nuevo margen: €{margin_est:.2f}"
            )
        
        return size, details, margin_est
    
    def get_positions(self) -> List[Dict]:
        """Obtiene posiciones actuales"""
        return self.api.get_positions()
    
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
    
    # ============================================
    # MÉTODOS DE STOP LOSS / TAKE PROFIT
    # ============================================
    
    def calculate_stop_loss(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de stop loss (estático o dinámico según Config)
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR como porcentaje (para modo dinámico)
            
        Returns:
            float: Nivel de stop loss
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_stop_loss_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_stop_loss_static(price, direction)
    
    def calculate_take_profit(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de take profit (estático o dinámico según Config)
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR como porcentaje (para modo dinámico)
            
        Returns:
            float: Nivel de take profit
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_take_profit_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_take_profit_static(price, direction)
    
    # ============================================
    # SL/TP ESTÁTICOS (PORCENTAJES FIJOS)
    # ============================================
    
    def calculate_stop_loss_static(self, price: float, direction: str) -> float:
        """
        Calcula SL estático usando porcentajes fijos de Config
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            
        Returns:
            float: Nivel de stop loss
        """
        if direction == 'BUY':
            return round(price * (1 - Config.STOP_LOSS_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 + Config.STOP_LOSS_PERCENT_SELL), 2)
    
    def calculate_take_profit_static(self, price: float, direction: str) -> float:
        """
        Calcula TP estático usando porcentajes fijos de Config
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            
        Returns:
            float: Nivel de take profit
        """
        if direction == 'BUY':
            return round(price * (1 + Config.TAKE_PROFIT_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 - Config.TAKE_PROFIT_PERCENT_SELL), 2)
    
    # ============================================
    # SL/TP DINÁMICOS (BASADOS EN ATR)
    # ============================================
    
    def calculate_stop_loss_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        """
        Calcula SL dinámico basado en ATR (volatilidad real del mercado)
        
        Ventajas:
        - Se adapta automáticamente a la volatilidad del activo
        - SL más ajustados en mercados tranquilos
        - SL más amplios en mercados volátiles
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR como porcentaje del precio
            
        Returns:
            float: Nivel de stop loss
        """
        # Distancia del SL = ATR * multiplicador
        sl_distance_percent = atr_percent * Config.ATR_MULTIPLIER_SL
        
        # Limitar distancia mínima y máxima (para evitar extremos)
        sl_distance_percent = max(sl_distance_percent, 1.0)   # Mínimo 1%
        sl_distance_percent = min(sl_distance_percent, 10.0)  # Máximo 10%
        
        if direction == 'BUY':
            # Para compras: SL por debajo del precio
            sl_level = price * (1 - sl_distance_percent / 100)
        else:  # SELL
            # Para ventas: SL por encima del precio
            sl_level = price * (1 + sl_distance_percent / 100)
        
        logger.debug(
            f"SL dinámico calculado: Precio={price:.2f}, ATR={atr_percent:.2f}%, "
            f"Distancia={sl_distance_percent:.2f}%, SL={sl_level:.2f}"
        )
        
        return round(sl_level, 2)
    
    def calculate_take_profit_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        """
        Calcula TP dinámico basado en ATR
        
        El TP se coloca más lejos que el SL para mantener un ratio
        riesgo/beneficio favorable (típicamente 1:1.5 o mejor)
        
        Args:
            price: Precio actual
            direction: 'BUY' o 'SELL'
            atr_percent: ATR como porcentaje del precio
            
        Returns:
            float: Nivel de take profit
        """
        # Distancia del TP = ATR * multiplicador (mayor que SL)
        tp_distance_percent = atr_percent * Config.ATR_MULTIPLIER_TP
        
        # Limitar distancia mínima y máxima
        tp_distance_percent = max(tp_distance_percent, 2.0)   # Mínimo 2%
        tp_distance_percent = min(tp_distance_percent, 15.0)  # Máximo 15%
        
        if direction == 'BUY':
            # Para compras: TP por encima del precio
            tp_level = price * (1 + tp_distance_percent / 100)
        else:  # SELL
            # Para ventas: TP por debajo del precio
            tp_level = price * (1 - tp_distance_percent / 100)
        
        logger.debug(
            f"TP dinámico calculado: Precio={price:.2f}, ATR={atr_percent:.2f}%, "
            f"Distancia={tp_distance_percent:.2f}%, TP={tp_level:.2f}"
        )
        
        return round(tp_level, 2)
    
    def get_risk_reward_ratio(self, price: float, stop_loss: float, take_profit: float, direction: str) -> float:
        """
        Calcula el ratio riesgo/beneficio de una operación
        
        Args:
            price: Precio de entrada
            stop_loss: Nivel de SL
            take_profit: Nivel de TP
            direction: 'BUY' o 'SELL'
            
        Returns:
            float: Ratio R/R (ej: 1.5 = ganarías 1.5x lo que arriesgas)
        """
        if direction == 'BUY':
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
        else:  # SELL
            risk = abs(stop_loss - price)
            reward = abs(price - take_profit)
        
        if risk > 0:
            return reward / risk
        return 0.0