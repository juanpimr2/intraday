#!/usr/bin/env python3
"""
Verifica posiciones actuales en Capital.com
"""

from api.capital_client import CapitalClient
from utils.helpers import safe_float
import json

print("="*60)
print("📊 VERIFICANDO POSICIONES EN CAPITAL.COM")
print("="*60)

api = CapitalClient()

if not api.authenticate():
    print("❌ Error de autenticación")
    exit(1)

print("✅ Autenticado correctamente\n")

# Obtener posiciones
positions = api.get_positions()

print(f"Posiciones abiertas: {len(positions)}\n")

if positions:
    for i, pos in enumerate(positions, 1):
        pos_data = pos.get('position', {})
        market = pos.get('market', {})
        
        print(f"{'='*60}")
        print(f"POSICIÓN {i}")
        print(f"{'='*60}")
        print(f"Epic: {pos_data.get('epic', 'Unknown')}")
        print(f"Dirección: {pos_data.get('direction', 'Unknown')}")
        print(f"Tamaño: {pos_data.get('size', 0)}")
        print(f"Precio entrada: €{safe_float(pos_data.get('level', 0)):.2f}")
        print(f"Stop Loss: €{safe_float(pos_data.get('stopLevel', 0)):.2f}")
        print(f"Take Profit: €{safe_float(pos_data.get('limitLevel', 0)):.2f}")
        print(f"Deal ID: {pos_data.get('dealId', 'N/A')}")
        print(f"Fecha apertura: {pos_data.get('createdDate', 'N/A')}")
        
        print(f"\n📋 Datos completos (JSON):")
        print(json.dumps(pos, indent=2, default=str))
        print()

else:
    print("ℹ️  No hay posiciones abiertas")

print("="*60)