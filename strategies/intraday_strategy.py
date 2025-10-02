"""
Estrategia de trading intraday mejorada
Incluye: ATR (volatilidad), ADX (fuerza tendencia), MTF (múltiples timeframes)
"""

import pandas as pd
import logging
from typing import Dict, Optional
from indicators.technical import TechnicalIndicators
from config import Config

logger = logging.getLogger(__name__)


class IntradayStrategy:
    """Estrategia de trading intraday basada en indicadores técnicos"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze(self, df: pd.DataFrame, epic: str) -> Dict:
        """
        Analiza el mercado y genera señales de trading (timeframe único)
        
        Args:
            df: DataFrame con datos de mercado (debe tener closePrice, highPrice, lowPrice)
            epic: Identificador del activo
            
        Returns:
            Dict: {
                'epic': str,
                'signal': 'BUY'|'SELL'|'NEUTRAL',
                'confidence': float (0-1),
                'current_price': float,
                'reasons': list[str],
                'indicators': dict,
                'atr_percent': float,
                'adx': float
            }
        """
        if df.empty or len(df) < Config.SMA_LONG:
            return self._neutral_signal(epic, 0.0, reason="Datos insuficientes")
        
        # Preparar serie de precios
        close_series = pd.Series(df['closePrice'].values)
        current_price = float(close_series.iloc[-1])
        
        # ============================================
        # FILTRO 1: VOLATILIDAD (ATR)
        # ============================================
        atr_pct = self.indicators.atr_percent(df, period=Config.ATR_PERIOD)
        
        # Descartar mercados con volatilidad muy baja (laterales)
        if atr_pct < Config.MIN_ATR_PERCENT:
            return self._neutral_signal(
                epic, current_price,
                reason=f"Volatilidad muy baja (ATR {atr_pct:.2f}% < {Config.MIN_ATR_PERCENT}%)"
            )
        
        # Evitar mercados excesivamente volátiles (noticias/pánico)
        if atr_pct > Config.MAX_ATR_PERCENT:
            return self._neutral_signal(
                epic, current_price,
                reason=f"Volatilidad excesiva (ATR {atr_pct:.2f}% > {Config.MAX_ATR_PERCENT}%)"
            )
        
        # ============================================
        # FILTRO 2: FUERZA DE TENDENCIA (ADX)
        # ============================================
        adx_value, plus_di, minus_di = 0.0, 0.0, 0.0
        
        if Config.ENABLE_ADX_FILTER:
            adx_value, plus_di, minus_di = self.indicators.adx(df, period=Config.ADX_PERIOD)
            
            # Solo operar si hay tendencia definida (ADX > umbral)
            if adx_value < Config.MIN_ADX_TREND:
                return self._neutral_signal(
                    epic, current_price,
                    reason=f"Mercado lateral (ADX {adx_value:.1f} < {Config.MIN_ADX_TREND})"
                )
        
        # ============================================
        # CALCULAR INDICADORES TÉCNICOS
        # ============================================
        rsi = self.indicators.rsi(close_series)
        macd, macd_signal, macd_hist = self.indicators.macd(close_series)
        sma_short = self.indicators.sma(close_series, Config.SMA_SHORT)
        sma_long = self.indicators.sma(close_series, Config.SMA_LONG)
        momentum = self.indicators.momentum(close_series)
        
        # ============================================
        # EVALUAR SEÑALES Y CALCULAR PUNTUACIÓN
        # ============================================
        buy_score = 0
        sell_score = 0
        reasons = []
        
        # 1. Análisis de tendencia (SMAs)
        golden_cross = sma_short > sma_long
        price_above_long = current_price > sma_long
        
        if golden_cross and price_above_long:
            buy_score += 2
            reasons.append("Tendencia alcista clara (Golden Cross)")
        elif not golden_cross and not price_above_long:
            sell_score += 2
            reasons.append("Tendencia bajista clara (Death Cross)")
        
        # 2. RSI (Sobreventa/Sobrecompra)
        if rsi < Config.RSI_OVERSOLD:
            buy_score += 2
            reasons.append(f"RSI en sobreventa ({rsi:.1f})")
        elif rsi > Config.RSI_OVERBOUGHT:
            sell_score += 2
            reasons.append(f"RSI en sobrecompra ({rsi:.1f})")
        
        # 3. MACD (Momentum)
        if macd > macd_signal and macd_hist > 0:
            buy_score += 2
            reasons.append("MACD alcista")
        elif macd < macd_signal and macd_hist < 0:
            sell_score += 2
            reasons.append("MACD bajista")
        
        # 4. Momentum
        if momentum > 2:
            buy_score += 1
            reasons.append(f"Momentum positivo ({momentum:.1f}%)")
        elif momentum < -2:
            sell_score += 1
            reasons.append(f"Momentum negativo ({momentum:.1f}%)")
        
        # 5. Posición del precio respecto a SMAs
        if current_price > sma_short and current_price > sma_long:
            buy_score += 1
            reasons.append("Precio sobre ambas medias móviles")
        elif current_price < sma_short and current_price < sma_long:
            sell_score += 1
            reasons.append("Precio bajo ambas medias móviles")
        
        # ============================================
        # BONUS: CONFIRMACIÓN CON ADX
        # ============================================
        if Config.ENABLE_ADX_FILTER and adx_value > Config.MIN_ADX_TREND:
            # Usar +DI y -DI para confirmar dirección de la tendencia
            if plus_di > minus_di:
                buy_score += 2
                reasons.append(f"Tendencia alcista fuerte (ADX {adx_value:.1f}, +DI > -DI)")
            elif minus_di > plus_di:
                sell_score += 2
                reasons.append(f"Tendencia bajista fuerte (ADX {adx_value:.1f}, -DI > +DI)")
            
            # Boost adicional si ADX muy fuerte
            if adx_value > Config.STRONG_ADX_THRESHOLD:
                if buy_score > sell_score:
                    buy_score += 1
                    reasons.append(f"Tendencia muy fuerte (ADX {adx_value:.1f})")
                elif sell_score > buy_score:
                    sell_score += 1
                    reasons.append(f"Tendencia muy fuerte (ADX {adx_value:.1f})")
        
        # ============================================
        # BONUS: VOLATILIDAD ÓPTIMA
        # ============================================
        if Config.OPTIMAL_ATR_MIN <= atr_pct <= Config.OPTIMAL_ATR_MAX:
            # En el "sweet spot" de volatilidad
            if buy_score > 0:
                buy_score += 1
            if sell_score > 0:
                sell_score += 1
            reasons.append(f"Volatilidad óptima (ATR {atr_pct:.2f}%)")
        
        # ============================================
        # DETERMINAR SEÑAL FINAL
        # ============================================
        if buy_score >= Config.MIN_SIGNALS_TO_TRADE and buy_score > sell_score:
            signal = 'BUY'
            confidence = min(buy_score / 10, 1.0)  # Normalizar a 0-1
        elif sell_score >= Config.MIN_SIGNALS_TO_TRADE and sell_score > buy_score:
            signal = 'SELL'
            confidence = min(sell_score / 10, 1.0)
        else:
            signal = 'NEUTRAL'
            confidence = 0.0
        
        return {
            'epic': epic,
            'signal': signal,
            'confidence': confidence,
            'current_price': current_price,
            'reasons': reasons,
            'atr_percent': atr_pct,
            'adx': adx_value,
            'indicators': {
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'macd_hist': macd_hist,
                'sma_short': sma_short,
                'sma_long': sma_long,
                'momentum': momentum,
                'atr_percent': atr_pct,
                'adx': adx_value,
                'plus_di': plus_di,
                'minus_di': minus_di
            }
        }
    
    def analyze_with_mtf(self, df_fast: pd.DataFrame, df_slow: pd.DataFrame, epic: str) -> Dict:
        """
        Análisis con múltiples timeframes (MTF)
        Analiza en timeframe rápido pero confirma con timeframe lento
        
        Args:
            df_fast: DataFrame del timeframe rápido (ej: HOUR)
            df_slow: DataFrame del timeframe lento (ej: HOUR_4 o DAY)
            epic: Identificador del activo
            
        Returns:
            Dict con análisis combinado
        """
        # Análisis del timeframe rápido (señales de entrada)
        fast_analysis = self.analyze(df_fast, epic)
        
        # Si no hay señal en timeframe rápido, no continuar
        if fast_analysis['signal'] == 'NEUTRAL':
            return fast_analysis
        
        # ============================================
        # ANÁLISIS DEL TIMEFRAME LENTO (FILTRO)
        # ============================================
        if df_slow.empty or len(df_slow) < Config.SMA_LONG:
            # Si no hay datos suficientes en TF lento, usar solo análisis rápido
            logger.warning(f"⚠️  {epic}: Datos insuficientes en timeframe lento")
            return fast_analysis
        
        slow_close = pd.Series(df_slow['closePrice'].values)
        slow_sma_short = self.indicators.sma(slow_close, Config.SMA_SHORT)
        slow_sma_long = self.indicators.sma(slow_close, Config.SMA_LONG)
        slow_rsi = self.indicators.rsi(slow_close)
        
        # Determinar tendencia del timeframe superior
        slow_trend = None
        if slow_sma_short > slow_sma_long and slow_rsi > 50:
            slow_trend = 'BULLISH'
        elif slow_sma_short < slow_sma_long and slow_rsi < 50:
            slow_trend = 'BEARISH'
        else:
            slow_trend = 'NEUTRAL'
        
        # ============================================
        # FILTRO MTF: VERIFICAR ALINEACIÓN
        # ============================================
        # Solo operar si ambos timeframes están alineados
        if fast_analysis['signal'] == 'BUY' and slow_trend != 'BULLISH':
            return self._neutral_signal(
                epic, fast_analysis['current_price'],
                reason=f"Desalineación MTF: señal BUY pero TF superior {slow_trend}"
            )
        
        if fast_analysis['signal'] == 'SELL' and slow_trend != 'BEARISH':
            return self._neutral_signal(
                epic, fast_analysis['current_price'],
                reason=f"Desalineación MTF: señal SELL pero TF superior {slow_trend}"
            )
        
        # ============================================
        # BOOST: ALINEACIÓN PERFECTA
        # ============================================
        # Si hay alineación perfecta, aumentar confianza
        if (fast_analysis['signal'] == 'BUY' and slow_trend == 'BULLISH') or \
           (fast_analysis['signal'] == 'SELL' and slow_trend == 'BEARISH'):
            
            fast_analysis['confidence'] = min(fast_analysis['confidence'] * 1.2, 1.0)
            fast_analysis['reasons'].append(f"✅ Alineación MTF perfecta (TF superior {slow_trend})")
        
        # Agregar info del timeframe lento
        fast_analysis['slow_trend'] = slow_trend
        fast_analysis['slow_sma_short'] = slow_sma_short
        fast_analysis['slow_sma_long'] = slow_sma_long
        fast_analysis['slow_rsi'] = slow_rsi
        
        return fast_analysis
    
    def _neutral_signal(self, epic: str, price: float, reason: str = "") -> Dict:
        """
        Retorna una señal neutral
        
        Args:
            epic: Identificador del activo
            price: Precio actual
            reason: Razón por la que es neutral
            
        Returns:
            Dict con señal NEUTRAL
        """
        result = {
            'epic': epic,
            'signal': 'NEUTRAL',
            'confidence': 0.0,
            'current_price': price,
            'reasons': [],
            'atr_percent': 0.0,
            'adx': 0.0,
            'indicators': {}
        }
        
        if reason:
            result['reasons'].append(reason)
        
        return result