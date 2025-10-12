#!/usr/bin/env python3
"""
Script de organización del proyecto
Mueve/elimina archivos sueltos de la raíz manteniendo la estructura limpia
"""

import os
import shutil
from pathlib import Path
from datetime import datetime


class ProjectOrganizer:
    """Organiza archivos del proyecto"""
    
    def __init__(self, dry_run: bool = True):
        """
        Args:
            dry_run: Si es True, solo muestra qué haría sin hacer cambios
        """
        self.dry_run = dry_run
        self.base_path = Path.cwd()
        self.actions = []
    
    def log_action(self, action_type: str, source: str, dest: str = None):
        """Registra una acción"""
        self.actions.append({
            'type': action_type,
            'source': source,
            'dest': dest,
            'timestamp': datetime.now()
        })
    
    def move_file(self, source: str, dest_dir: str):
        """Mueve un archivo a un directorio"""
        source_path = self.base_path / source
        
        if not source_path.exists():
            print(f"   ⚠️  {source} no existe, omitiendo")
            return
        
        dest_path = self.base_path / dest_dir
        dest_path.mkdir(parents=True, exist_ok=True)
        
        dest_file = dest_path / source_path.name
        
        if self.dry_run:
            print(f"   📦 {source} → {dest_dir}/")
        else:
            shutil.move(str(source_path), str(dest_file))
            print(f"   ✅ {source} → {dest_dir}/")
        
        self.log_action('move', source, dest_dir)
    
    def delete_file(self, filepath: str):
        """Elimina un archivo"""
        file_path = self.base_path / filepath
        
        if not file_path.exists():
            print(f"   ⚠️  {filepath} no existe, omitiendo")
            return
        
        if self.dry_run:
            print(f"   🗑️  {filepath}")
        else:
            file_path.unlink()
            print(f"   ✅ {filepath} eliminado")
        
        self.log_action('delete', filepath)
    
    def organize(self):
        """Ejecuta la organización completa"""
        print("="*70)
        print("🧹 ORGANIZANDO PROYECTO")
        print("="*70)
        
        if self.dry_run:
            print("⚠️  MODO DRY-RUN: Solo mostrando cambios (no ejecuta)")
        else:
            print("✅ MODO EJECUCIÓN: Aplicando cambios")
        
        print()
        
        # ============================================
        # PASO 1: Mover a /scripts
        # ============================================
        print("📂 PASO 1: Moviendo scripts a /scripts/")
        print("-" * 70)
        
        scripts_to_move = [
            'sync_trades_from_api.py',
            'health_check.py',
            'start_all.py',
            'setup_analytics_system.py',
            'setup_dashboard.py',
            'setup_python_files.py',
            'fix_strategy_init.py'
        ]
        
        for script in scripts_to_move:
            self.move_file(script, 'scripts')
        
        print()
        
        # ============================================
        # PASO 2: Mover a /tests
        # ============================================
        print("🧪 PASO 2: Moviendo tests a /tests/")
        print("-" * 70)
        
        tests_to_move = [
            'test.py',
            'test_logger.py'
        ]
        
        for test in tests_to_move:
            self.move_file(test, 'tests')
        
        print()
        
        # ============================================
        # PASO 3: Crear carpeta deployment y mover
        # ============================================
        print("🚂 PASO 3: Moviendo archivos de deployment a /deployment/")
        print("-" * 70)
        
        deployment_files = [
            'config_railway.py',
            'Procfile',
            'railway.toml',
            'railway_notes.txt'
        ]
        
        for deploy_file in deployment_files:
            self.move_file(deploy_file, 'deployment')
        
        print()
        
        # ============================================
        # PASO 4: Eliminar archivos temporales
        # ============================================
        print("🗑️  PASO 4: Eliminando archivos temporales")
        print("-" * 70)
        
        files_to_delete = [
            'bot_state.json',
            'db_status.txtclear',
            'trading_bot.db'
        ]
        
        for file in files_to_delete:
            self.delete_file(file)
        
        print()
        
        # ============================================
        # Resumen
        # ============================================
        print("="*70)
        print("📊 RESUMEN")
        print("="*70)
        
        moves = len([a for a in self.actions if a['type'] == 'move'])
        deletes = len([a for a in self.actions if a['type'] == 'delete'])
        
        print(f"   📦 Archivos movidos: {moves}")
        print(f"   🗑️  Archivos eliminados: {deletes}")
        print()
        
        if self.dry_run:
            print("⚠️  Para aplicar los cambios, ejecuta:")
            print("   python organize_project.py --execute")
        else:
            print("✅ Organización completada exitosamente")
        
        print("="*70)
        print()
        
        # Mostrar estructura resultante esperada
        if self.dry_run:
            print("📁 ESTRUCTURA RESULTANTE EN RAÍZ:")
            print("-" * 70)
            print("✅ Archivos esenciales:")
            print("   - main.py")
            print("   - config.py")
            print("   - requirements.txt")
            print("   - pytest.ini")
            print("   - .env / .env.example")
            print("   - .gitignore / .gitattributes")
            print("   - README.md / INSTALLATION.md")
            print("   - docker-compose.yml")
            print()
            print("📂 Carpetas organizadas:")
            print("   - /scripts/     → Scripts de utilidad y setup")
            print("   - /tests/       → Tests unitarios")
            print("   - /deployment/  → Configuración Railway/producción")
            print("   - /api/, /strategies/, /trading/, etc. → Módulos principales")
            print()


def main():
    """Función principal"""
    import sys
    
    # Verificar argumentos
    execute = '--execute' in sys.argv or '-e' in sys.argv
    
    organizer = ProjectOrganizer(dry_run=not execute)
    organizer.organize()
    
    if not execute:
        print("💡 CONSEJOS:")
        print("   1. Revisa los cambios propuestos arriba")
        print("   2. Si todo se ve bien, ejecuta:")
        print("      python organize_project.py --execute")
        print("   3. Después puedes actualizar .gitignore si es necesario")
        print()


if __name__ == "__main__":
    main()
