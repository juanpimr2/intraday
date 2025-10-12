# -*- coding: utf-8 -*-
"""
Fix directo - Reemplaza reason por exit_reason en líneas específicas
"""

from pathlib import Path

analytics_path = Path('database/queries/analytics.py')

print("="*70)
print("FIX DIRECTO - REASON -> EXIT_REASON")
print("="*70)

if not analytics_path.exists():
    print(f"ERROR: {analytics_path} no existe")
    exit(1)

print("\n[1] Leyendo archivo...")
with open(analytics_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"    Total lineas: {len(lines)}")

print("\n[2] Buscando y reemplazando 'reason'...")

changes = 0
for i, line in enumerate(lines):
    # Buscar líneas con "reason," pero NO "exit_reason" o "reasons"
    if 'reason,' in line and 'exit_reason' not in line and 'reasons' not in line:
        old_line = line
        new_line = line.replace('reason,', 'exit_reason,')
        lines[i] = new_line
        changes += 1
        print(f"    Linea {i+1}:")
        print(f"      Antes:  {old_line.strip()}")
        print(f"      Despues: {new_line.strip()}")

if changes > 0:
    print(f"\n[3] Guardando {changes} cambios...")
    with open(analytics_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("    [OK] Archivo actualizado")
else:
    print("\n[3] No se encontraron cambios necesarios")

print("\n" + "="*70)
print("FIX COMPLETADO")
print("="*70)
