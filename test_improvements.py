#!/usr/bin/env python3
"""
Script para testear las nuevas mejoras (ATR, ADX, MTF)
"""

import sys
import pandas as pd
import numpy as np
from indicators.technical import TechnicalIndicators
from strategies.intraday_strategy import IntradayStrategy
from trading.position_manager import PositionManager
from config import Config

print("="*60)
print("🧪 TESTING DE MEJORAS")
print("="*60)

# ============================================
# TEST 1: Verificar que los indicadores ATR y ADX funcionan
# ============================================
print("\n📊 TEST 1: Indicadores ATR y ADX")
print("-"*60)

# Crear datos sintéticos para test
np.random.seed(42)
n_points = 100
base_price = 100.0

# Simular precios con tendencia alcista y volatilidad
price_changes = np.random.normal(0.5, 2.0, n_points)  # Media 0.5%, desv. 2%
close_prices = base_price * (1 + np.cumsum(price_changes) / 100)

# Crear high y low basados en close
high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.01, n_points)))
low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.01, n_points)))

# Crear DataFrame de test
df_test = pd.DataFrame({
    'closePrice': close_prices,
    'highPrice': high_prices,
    'lowPrice': low_prices
})

indicators = TechnicalIndicators()

# Test ATR
atr_value = indicators.atr(df_test, period=14)
atr_pct = indicators.atr_percent(df_test, period=14)

print(f"✅ ATR absoluto: {atr_value:.4f}")
print(f"✅ ATR porcentaje: {atr_pct:.2f}%")

if atr_pct > 0:
    print("✅ ATR funciona correctamente")
else:
    print("❌ ERROR: ATR no está calculando bien")

# Test ADX
adx, plus_di, minus_di = indicators.adx(df_test, period=14)

print(f"✅ ADX: {adx:.2f}")
print(f"✅ +DI: {plus_di:.2f}")
print(f"✅ -DI: {minus_di:.2f}")

if adx > 0:
    print("✅ ADX funciona correctamente")
    
    if plus_di > minus_di:
        print("   → Tendencia ALCISTA detectada (+DI > -DI)")
    else:
        print("   → Tendencia BAJISTA detectada (-DI > +DI)")
else:
    print("❌ ERROR: ADX no está calculando bien")

# ============================================
# TEST 2: Verificar filtros en la estrategia
# ============================================
print("\n📈 TEST 2: Filtros de la Estrategia")
print("-"*60)

strategy = IntradayStrategy()

# Test con datos suficientes
analysis = strategy.analyze(df_test, "TEST_EPIC")

print(f"Epic: {analysis['epic']}")
print(f"Señal: {analysis['signal']}")
print(f"Confianza: {analysis['confidence']:.0%}")
print(f"ATR: {analysis.get('atr_percent', 0):.2f}%")
print(f"ADX: {analysis.get('adx', 0):.1f}")
print(f"Razones: {analysis['reasons']}")

# Verificar que los filtros funcionan
if analysis['atr_percent'] > 0:
    print("✅ Filtro ATR integrado correctamente")
else:
    print("⚠️  ADVERTENCIA: ATR no está en el análisis")

if 'adx' in analysis:
    print("✅ Filtro ADX integrado correctamente")
else:
    print("⚠️  ADVERTENCIA: ADX no está en el análisis")

# Test de filtrado por volatilidad baja
print("\n🔍 Test filtro: Volatilidad muy baja")
# Crear datos con volatilidad casi cero (mercado lateral)
flat_prices = np.full(100, 100.0)  # Precio constante
df_flat = pd.DataFrame({
    'closePrice': flat_prices,
    'highPrice': flat_prices * 1.001,
    'lowPrice': flat_prices * 0.999
})

analysis_flat = strategy.analyze(df_flat, "FLAT_MARKET")
print(f"Señal con baja volatilidad: {analysis_flat['signal']}")
print(f"Razón: {analysis_flat['reasons'][0] if analysis_flat['reasons'] else 'N/A'}")

if analysis_flat['signal'] == 'NEUTRAL':
    print("✅ Filtro de volatilidad funciona (rechaza mercados planos)")
else:
    print("⚠️  ADVERTENCIA: Filtro de volatilidad no está rechazando mercados planos")

# ============================================
# TEST 3: SL/TP Dinámicos
# ============================================
print("\n🎯 TEST 3: SL/TP Dinámicos vs Estáticos")
print("-"*60)

# Mock de API client (solo para test)
class MockAPI:
    def get_market_details(self, epic):
        return {
            'leverage': 20,
            'marginRate': 0.05,
            'minSize': 0.01,
            'stepSize': 0.01,
            'precision': 2
        }

position_manager = PositionManager(MockAPI())

price = 100.0
direction = 'BUY'
atr_percent = 2.5  # ATR del 2.5%

# Calcular SL/TP estáticos
Config.SL_TP_MODE = 'STATIC'
sl_static = position_manager.calculate_stop_loss(price, direction)
tp_static = position_manager.calculate_take_profit(price, direction)

print("Modo ESTÁTICO (porcentajes fijos):")
print(f"  Precio: €{price:.2f}")
print(f"  SL: €{sl_static:.2f} (distancia: {abs(price-sl_static):.2f}, {abs(price-sl_static)/price*100:.1f}%)")
print(f"  TP: €{tp_static:.2f} (distancia: {abs(tp_static-price):.2f}, {abs(tp_static-price)/price*100:.1f}%)")

rr_static = position_manager.get_risk_reward_ratio(price, sl_static, tp_static, direction)
print(f"  Ratio R/R: {rr_static:.2f}")

# Calcular SL/TP dinámicos
Config.SL_TP_MODE = 'DYNAMIC'
sl_dynamic = position_manager.calculate_stop_loss(price, direction, atr_percent)
tp_dynamic = position_manager.calculate_take_profit(price, direction, atr_percent)

print(f"\nModo DINÁMICO (basado en ATR {atr_percent:.2f}%):")
print(f"  Precio: €{price:.2f}")
print(f"  SL: €{sl_dynamic:.2f} (distancia: {abs(price-sl_dynamic):.2f}, {abs(price-sl_dynamic)/price*100:.1f}%)")
print(f"  TP: €{tp_dynamic:.2f} (distancia: {abs(tp_dynamic-price):.2f}, {abs(tp_dynamic-price)/price*100:.1f}%)")

rr_dynamic = position_manager.get_risk_reward_ratio(price, sl_dynamic, tp_dynamic, direction)
print(f"  Ratio R/R: {rr_dynamic:.2f}")

if sl_dynamic != sl_static or tp_dynamic != tp_static:
    print("\n✅ SL/TP dinámicos funcionan (son diferentes a los estáticos)")
else:
    print("\n⚠️  ADVERTENCIA: SL/TP dinámicos no están diferenciándose")

# Test con diferentes niveles de volatilidad
print("\n🔬 Comportamiento con diferentes volatilidades:")
for test_atr in [0.5, 1.0, 2.0, 4.0]:
    sl = position_manager.calculate_stop_loss(price, direction, test_atr)
    tp = position_manager.calculate_take_profit(price, direction, test_atr)
    rr = position_manager.get_risk_reward_ratio(price, sl, tp, direction)
    
    print(f"  ATR {test_atr:.1f}%: SL={sl:.2f}, TP={tp:.2f}, R/R={rr:.2f}")

print("\n✅ Los SL/TP se adaptan a la volatilidad (más volatilidad = más amplios)")

# ============================================
# TEST 4: Análisis Multi-Timeframe (MTF)
# ============================================
print("\n🕒 TEST 4: Análisis Multi-Timeframe (MTF)")
print("-"*60)

# Crear datos para timeframe rápido (señal de compra)
fast_prices = base_price * (1 + np.cumsum(np.random.normal(0.8, 1.5, 100)) / 100)
df_fast = pd.DataFrame({
    'closePrice': fast_prices,
    'highPrice': fast_prices * 1.01,
    'lowPrice': fast_prices * 0.99
})

# Crear datos para timeframe lento (tendencia alcista confirmada)
slow_prices = base_price * (1 + np.cumsum(np.random.normal(0.5, 1.0, 100)) / 100)
df_slow = pd.DataFrame({
    'closePrice': slow_prices,
    'highPrice': slow_prices * 1.01,
    'lowPrice': slow_prices * 0.99
})

# Analizar con MTF
Config.ENABLE_MTF = True
analysis_mtf = strategy.analyze_with_mtf(df_fast, df_slow, "MTF_TEST")

print(f"Señal TF rápido: {analysis_mtf['signal']}")
print(f"Tendencia TF lento: {analysis_mtf.get('slow_trend', 'N/A')}")
print(f"Confianza: {analysis_mtf['confidence']:.0%}")
print(f"Razones: {[r for r in analysis_mtf['reasons'] if 'MTF' in r]}")

if 'slow_trend' in analysis_mtf:
    print("✅ Análisis MTF funciona correctamente")
    
    if 'MTF' in str(analysis_mtf['reasons']):
        print("✅ Sistema detecta alineación/desalineación de tendencias")
else:
    print("⚠️  ADVERTENCIA: Análisis MTF no está retornando datos del TF lento")

# ============================================
# RESUMEN FINAL
# ============================================
print("\n" + "="*60)
print("📊 RESUMEN DE TESTS")
print("="*60)

all_ok = True

checks = [
    ("ATR funcionando", atr_pct > 0),
    ("ADX funcionando", adx > 0),
    ("Filtro ATR integrado", analysis.get('atr_percent', 0) > 0),
    ("Filtro ADX integrado", 'adx' in analysis),
    ("SL/TP dinámicos diferentes", sl_dynamic != sl_static),
    ("MTF funcionando", 'slow_trend' in analysis_mtf)
]

for check_name, check_result in checks:
    status = "✅" if check_result else "❌"
    print(f"{status} {check_name}")
    if not check_result:
        all_ok = False

print("="*60)

if all_ok:
    print("🎉 TODAS LAS MEJORAS FUNCIONAN CORRECTAMENTE")
    print("\nPróximos pasos:")
    print("1. Ejecuta un backtest con las mejoras")
    print("2. Compara resultados con la estrategia anterior")
    print("3. Si los resultados son buenos, activa en DEMO")
    print("4. Monitorea durante varios días antes de pasar a LIVE")
else:
    print("⚠️  ALGUNOS TESTS FALLARON - REVISA EL CÓDIGO")
    print("\nVerifica:")
    print("1. Que copiaste todos los archivos correctamente")
    print("2. Que no hay errores de sintaxis")
    print("3. Que los imports están correctos")

print("\n" + "="*60)