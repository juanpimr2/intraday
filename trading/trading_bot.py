"""
MODIFICACIONES PARA trading/trading_bot.py

Estos son los cambios que debes hacer en tu archivo trading_bot.py existente
para integrar las mejoras de ATR, ADX y MTF.
"""

# ============================================
# MODIFICACIÓN 1: En el método _analyze_markets()
# Cambiar para soportar MTF (múltiples timeframes)
# ============================================

def _analyze_markets(self) -> List[Dict]:
    """Analiza todos los mercados con soporte MTF"""
    analyses = []
    
    for epic in Config.ASSETS:
        try:
            # CAMBIO: Obtener datos de ambos timeframes
            if Config.ENABLE_MTF:
                # Timeframe rápido (señales de entrada)
                market_data_fast = self.api.get_market_data(
                    epic, 
                    Config.TIMEFRAME_FAST,
                    max_values=200
                )
                
                # Timeframe lento (filtro de tendencia)
                market_data_slow = self.api.get_market_data(
                    epic, 
                    Config.TIMEFRAME_SLOW,
                    max_values=100
                )
                
                if not market_data_fast or not market_data_slow:
                    logger.warning(f"⚠️  Datos incompletos para {epic}")
                    continue
                
                # Convertir a DataFrames
                df_fast = self._convert_to_dataframe(market_data_fast)
                df_slow = self._convert_to_dataframe(market_data_slow)
                
                if df_fast.empty or df_slow.empty:
                    continue
                
                # CAMBIO: Analizar con MTF
                analysis = self.strategy.analyze_with_mtf(df_fast, df_slow, epic)
                
            else:
                # Modo sin MTF (timeframe único)
                market_data = self.api.get_market_data(epic, Config.TIMEFRAME)
                
                if not market_data or 'prices' not in market_data:
                    logger.warning(f"⚠️  No hay datos para {epic}")
                    continue
                
                df = self._convert_to_dataframe(market_data)
                
                if df.empty:
                    continue
                
                # Analizar con timeframe único
                analysis = self.strategy.analyze(df, epic)
            
            # Si hay señal válida, guardar
            if analysis['signal'] in ['BUY', 'SELL'] and analysis['current_price'] > 0:
                analyses.append(analysis)
                
                # CAMBIO: Log más completo con nuevos indicadores
                logger.info(
                    f"📊 {epic}: {analysis['signal']} "
                    f"(conf {analysis['confidence']:.0%}) | "
                    f"RSI {analysis['indicators'].get('rsi', 0):.1f} | "
                    f"ATR {analysis.get('atr_percent', 0):.2f}% | "
                    f"ADX {analysis.get('adx', 0):.1f}"
                    + (f" | MTF {analysis.get('slow_trend', 'N/A')}" if Config.ENABLE_MTF else "")
                )
            
            time.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Error analizando {epic}: {e}")
            continue
    
    return analyses


# ============================================
# MODIFICACIÓN 2: Nuevo método auxiliar
# Para convertir datos de API a DataFrame
# ============================================

def _convert_to_dataframe(self, market_data: Dict) -> pd.DataFrame:
    """
    Convierte datos de mercado de la API a DataFrame limpio
    
    Args:
        market_data: Respuesta de la API con 'prices'
        
    Returns:
        DataFrame con precios limpios y validados
    """
    if not market_data or 'prices' not in market_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(market_data['prices'])
    
    # Convertir precios a float
    for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: safe_float(x))
    
    # Asegurar que closePrice es numérico y sin NaN
    df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
    df = df.dropna(subset=['closePrice'])
    
    return df


# ============================================
# MODIFICACIÓN 3: En el método _plan_trades()
# Usar SL/TP dinámicos con ATR
# ============================================

def _plan_trades(self, analyses: List[Dict], per_trade_margin: float, balance: float) -> List[Dict]:
    """Planifica las operaciones con SL/TP dinámicos"""
    plans = []
    margin_by_asset = self.position_manager.get_margin_by_asset()
    asset_limit = balance * Config.MAX_MARGIN_PER_ASSET
    
    for analysis in analyses:
        epic = analysis['epic']
        price = safe_float(analysis['current_price'])
        direction = analysis['signal']
        atr_percent = analysis.get('atr_percent', 0)  # NUEVO
        
        # Calcular tamaño de posición
        size, details, margin_est = self.position_manager.calculate_position_size(
            epic, price, per_trade_margin
        )
        
        # Verificar límite por activo
        asset_used = margin_by_asset.get(epic, 0.0)
        
        if asset_used + margin_est > asset_limit:
            logger.warning(
                f"⛔ {epic}: Límite por activo excedido "
                f"(actual €{asset_used:.2f} + nuevo €{margin_est:.2f} > €{asset_limit:.2f})"
            )
            continue
        
        # CAMBIO: Calcular SL y TP (ahora con soporte dinámico)
        stop_loss = self.position_manager.calculate_stop_loss(
            price, 
            direction,
            atr_percent if Config.SL_TP_MODE == 'DYNAMIC' else None
        )
        
        take_profit = self.position_manager.calculate_take_profit(
            price, 
            direction,
            atr_percent if Config.SL_TP_MODE == 'DYNAMIC' else None
        )
        
        # NUEVO: Calcular y mostrar ratio riesgo/beneficio
        rr_ratio = self.position_manager.get_risk_reward_ratio(
            price, stop_loss, take_profit, direction
        )
        
        # NUEVO: Filtrar trades con mal ratio R/R (opcional)
        if rr_ratio < 1.0:  # No aceptar trades donde arriesgas más de lo que puedes ganar
            logger.warning(f"⛔ {epic}: Ratio R/R desfavorable ({rr_ratio:.2f})")
            continue
        
        plans.append({
            'epic': epic,
            'direction': direction,
            'price': price,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'margin_est': margin_est,
            'confidence': analysis['confidence'],
            'reasons': analysis['reasons'],
            'indicators': analysis['indicators'],
            'atr_percent': atr_percent,  # NUEVO: Para logs
            'adx': analysis.get('adx', 0),  # NUEVO: Para logs
            'rr_ratio': rr_ratio  # NUEVO: Para logs
        })
    
    return plans


# ============================================
# MODIFICACIÓN 4: En el método _execute_trades()
# Mejorar logs con nueva información
# ============================================

def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float):
    """Ejecuta las operaciones planificadas con logs mejorados"""
    plans.sort(key=lambda x: x['confidence'], reverse=True)
    
    executed = 0
    current_margin = margin_used
    
    for plan in plans:
        new_total = current_margin + plan['margin_est']
        
        if new_total > total_limit:
            logger.warning(
                f"⛔ Saltada {plan['epic']}: Límite total excedido "
                f"(nuevo total €{new_total:.2f} > €{total_limit:.2f})"
            )
            continue
        
        # Preparar orden
        order_data = {
            'epic': plan['epic'],
            'direction': plan['direction'],
            'size': plan['size'],
            'guaranteedStop': False,
            'stopLevel': plan['stop_loss'],
            'profitLevel': plan['take_profit']
        }
        
        # CAMBIO: Log mejorado con nueva información
        logger.info("-"*60)
        logger.info(f"📤 ORDEN {plan['direction']}: {plan['epic']} @ €{plan['price']:.2f}")
        logger.info(f"   Size: {plan['size']} | Margen: €{plan['margin_est']:.2f} | Conf: {plan['confidence']:.0%}")
        logger.info(
            f"   SL: €{plan['stop_loss']:.2f} | TP: €{plan['take_profit']:.2f} | "
            f"R/R: {plan.get('rr_ratio', 0):.2f}"
        )
        
        # NUEVO: Mostrar tipo de SL/TP usado
        if Config.SL_TP_MODE == 'DYNAMIC':
            logger.info(f"   SL/TP Dinámico basado en ATR {plan.get('atr_percent', 0):.2f}%")
        else:
            logger.info(f"   SL/TP Estático (porcentajes fijos)")
        
        # NUEVO: Mostrar indicadores clave
        logger.info(
            f"   Indicadores: ADX {plan.get('adx', 0):.1f} | "
            f"ATR {plan.get('atr_percent', 0):.2f}%"
        )
        
        logger.info(f"   Razones: {', '.join(plan['reasons'][:3])}")  # Mostrar top 3
        
        # Ejecutar orden
        result = self.api.place_order(order_data)
        
        if result:
            deal_ref = result.get('dealReference', 'n/a')
            logger.info(f"✅ Orden ejecutada - Deal ID: {deal_ref}")
            current_margin += plan['margin_est']
            executed += 1
        else:
            logger.error(f"❌ Error ejecutando orden")
        
        time.sleep(1)
    
    logger.info("="*60)
    logger.info(f"📊 RESUMEN: {executed}/{len(plans)} órdenes ejecutadas")
    logger.info(f"💰 Margen estimado tras ejecuciones: €{current_margin:.2f} (límite €{total_limit:.2f})")
    logger.info("="*60)


# ============================================
# RESUMEN DE CAMBIOS
# ============================================
"""
CAMBIOS PRINCIPALES:

1. _analyze_markets():
   - Soporta MTF (múltiples timeframes)
   - Usa analyze_with_mtf() cuando Config.ENABLE_MTF = True
   - Logs mejorados con ATR, ADX y tendencia MTF

2. _convert_to_dataframe():
   - Nuevo método auxiliar
   - Limpia y valida datos de la API

3. _plan_trades():
   - Usa SL/TP dinámicos cuando Config.SL_TP_MODE = 'DYNAMIC'
   - Calcula y muestra ratio riesgo/beneficio
   - Filtra trades con mal R/R

4. _execute_trades():
   - Logs mucho más informativos
   - Muestra tipo de SL/TP usado (dinámico vs estático)
   - Muestra indicadores clave (ATR, ADX)
   - Muestra ratio R/R

PARA APLICAR ESTOS CAMBIOS:
1. Abre tu archivo trading/trading_bot.py
2. Busca cada método mencionado arriba
3. Reemplaza el código existente con el nuevo código
4. Importa pandas si no lo tienes: from typing import List, Dict
5. ¡Listo! Tu bot ahora usa las mejoras
"""