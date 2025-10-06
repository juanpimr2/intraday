"""
Gestor de logs estructurado por sesión y fecha
Crea directorios en formato: logs/[DIA_MES_AÑO] Sesion X/
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class SessionLogger:
    """Gestiona logs estructurados por sesión y fecha"""
    
    def __init__(self, session_id: Optional[int] = None):
        """
        Inicializa el logger de sesión
        
        Args:
            session_id: ID de la sesión de trading (si existe)
        """
        self.session_id = session_id
        self.logs_base_dir = Path('logs')
        self.current_log_dir = None
        self.file_handler = None
        
        # Crear directorio base si no existe
        self.logs_base_dir.mkdir(exist_ok=True)
        
        # Configurar logs
        self._setup_session_logging()
    
    def _setup_session_logging(self):
        """Configura logging para la sesión actual"""
        # Formato: [06_OCT_2025] Sesion 1
        date_str = datetime.now().strftime("%d_%b_%Y").upper()
        
        if self.session_id:
            dir_name = f"[{date_str}] Sesion {self.session_id}"
        else:
            # Sesión temporal (sin BD)
            timestamp = datetime.now().strftime("%H%M%S")
            dir_name = f"[{date_str}] Sesion Temp {timestamp}"
        
        self.current_log_dir = self.logs_base_dir / dir_name
        self.current_log_dir.mkdir(exist_ok=True)
        
        # Archivo de log principal
        log_file = self.current_log_dir / "trading_bot.log"
        
        # Configurar handler de archivo
        self.file_handler = logging.FileHandler(
            log_file, 
            encoding='utf-8',
            mode='a'  # Append mode
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.file_handler.setFormatter(formatter)
        
        # Agregar handler al logger raíz
        root_logger = logging.getLogger()
        root_logger.addHandler(self.file_handler)
        
        logging.info("="*70)
        logging.info(f"📁 LOGS DE SESIÓN: {self.current_log_dir}")
        logging.info("="*70)
    
    def log_trade_open(self, trade_data: dict):
        """
        Guarda log específico de apertura de trade
        
        Args:
            trade_data: Datos del trade abierto
        """
        trades_log = self.current_log_dir / "trades_opened.log"
        
        try:
            with open(trades_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n{'='*70}\n")
                f.write(f"[{timestamp}] TRADE OPENED\n")
                f.write(f"{'='*70}\n")
                f.write(f"Deal ID:       {trade_data.get('deal_reference', 'N/A')}\n")
                f.write(f"Epic:          {trade_data.get('epic', 'N/A')}\n")
                f.write(f"Direction:     {trade_data.get('direction', 'N/A')}\n")
                f.write(f"Entry Price:   €{trade_data.get('entry_price', 0):.2f}\n")
                f.write(f"Size:          {trade_data.get('size', 0)}\n")
                f.write(f"Stop Loss:     €{trade_data.get('stop_loss', 0):.2f}\n")
                f.write(f"Take Profit:   €{trade_data.get('take_profit', 0):.2f}\n")
                f.write(f"Margin:        €{trade_data.get('margin_est', 0):.2f}\n")
                f.write(f"Confidence:    {trade_data.get('confidence', 0):.0%}\n")
                f.write(f"SL/TP Mode:    {trade_data.get('sl_tp_mode', 'N/A')}\n")
                
                if trade_data.get('atr_percent'):
                    f.write(f"ATR:           {trade_data['atr_percent']:.2f}%\n")
                
                reasons = trade_data.get('reasons', [])
                if reasons:
                    f.write(f"Reasons:\n")
                    for reason in reasons:
                        f.write(f"  - {reason}\n")
                
                f.write(f"{'='*70}\n")
        except Exception as e:
            logging.error(f"Error guardando log de trade abierto: {e}")
    
    def log_trade_close(self, trade_data: dict):
        """
        Guarda log específico de cierre de trade
        
        Args:
            trade_data: Datos del trade cerrado
        """
        trades_log = self.current_log_dir / "trades_closed.log"
        
        try:
            with open(trades_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n{'='*70}\n")
                f.write(f"[{timestamp}] TRADE CLOSED\n")
                f.write(f"{'='*70}\n")
                f.write(f"Deal ID:       {trade_data.get('deal_reference', 'N/A')}\n")
                f.write(f"Epic:          {trade_data.get('epic', 'N/A')}\n")
                f.write(f"Exit Price:    €{trade_data.get('exit_price', 0):.2f}\n")
                f.write(f"Exit Reason:   {trade_data.get('exit_reason', 'N/A')}\n")
                f.write(f"P&L:           €{trade_data.get('pnl', 0):.2f}\n")
                f.write(f"P&L %:         {trade_data.get('pnl_percent', 0):.2f}%\n")
                
                duration = trade_data.get('duration_minutes', 0)
                if duration:
                    hours = duration // 60
                    minutes = duration % 60
                    f.write(f"Duration:      {hours}h {minutes}m\n")
                
                f.write(f"{'='*70}\n")
        except Exception as e:
            logging.error(f"Error guardando log de trade cerrado: {e}")
    
    def log_signal(self, signal_data: dict):
        """
        Guarda log de señal detectada
        
        Args:
            signal_data: Datos de la señal
        """
        signals_log = self.current_log_dir / "signals.log"
        
        try:
            with open(signals_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                signal_emoji = "🟢" if signal_data['signal'] == 'BUY' else "🔴"
                
                f.write(
                    f"[{timestamp}] {signal_emoji} {signal_data['epic']} - "
                    f"{signal_data['signal']} "
                    f"(Conf: {signal_data['confidence']:.0%}"
                )
                
                if signal_data.get('atr_percent'):
                    f.write(f", ATR: {signal_data['atr_percent']:.2f}%")
                
                if signal_data.get('adx'):
                    f.write(f", ADX: {signal_data['adx']:.1f}")
                
                f.write(")\n")
                
                # Razones (indentadas)
                reasons = signal_data.get('reasons', [])
                if reasons:
                    for reason in reasons[:3]:  # Primeras 3 razones
                        f.write(f"    └─ {reason}\n")
                    
        except Exception as e:
            logging.error(f"Error guardando log de señal: {e}")
    
    def log_scan_summary(self, summary: dict):
        """
        Guarda resumen de escaneo de mercados
        
        Args:
            summary: Resumen del escaneo
        """
        scan_log = self.current_log_dir / "scans_summary.log"
        
        try:
            with open(scan_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n[{timestamp}] SCAN COMPLETED\n")
                f.write(f"  Assets analyzed:  {summary.get('total_assets', 0)}\n")
                f.write(f"  Signals found:    {summary.get('signals_found', 0)}\n")
                f.write(f"  Trades executed:  {summary.get('trades_executed', 0)}\n")
                
                if summary.get('margin_used'):
                    f.write(f"  Margin used:      €{summary['margin_used']:.2f}\n")
                
                f.write(f"  {'-'*50}\n")
        except Exception as e:
            logging.error(f"Error guardando resumen de escaneo: {e}")
    
    def log_account_snapshot(self, account_data: dict):
        """
        Guarda snapshot periódico de la cuenta
        
        Args:
            account_data: Datos de la cuenta
        """
        account_log = self.current_log_dir / "account_snapshots.log"
        
        try:
            with open(account_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                balance = account_data.get('balance', 0)
                available = account_data.get('available', 0)
                margin_used = balance - available
                margin_percent = (margin_used / balance * 100) if balance > 0 else 0
                
                f.write(
                    f"[{timestamp}] "
                    f"Balance: €{balance:.2f} | "
                    f"Available: €{available:.2f} | "
                    f"Margin: €{margin_used:.2f} ({margin_percent:.1f}%) | "
                    f"Positions: {account_data.get('open_positions', 0)}\n"
                )
        except Exception as e:
            logging.error(f"Error guardando snapshot de cuenta: {e}")
    
    def log_error(self, error_msg: str, exception: Exception = None):
        """
        Guarda log de error crítico
        
        Args:
            error_msg: Mensaje de error
            exception: Excepción (opcional)
        """
        error_log = self.current_log_dir / "errors.log"
        
        try:
            with open(error_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n{'='*70}\n")
                f.write(f"[{timestamp}] ERROR\n")
                f.write(f"{'='*70}\n")
                f.write(f"{error_msg}\n")
                
                if exception:
                    import traceback
                    f.write(f"\nTraceback:\n")
                    f.write(traceback.format_exc())
                
                f.write(f"{'='*70}\n")
        except Exception as e:
            logging.error(f"Error guardando log de error: {e}")
    
    def get_log_directory(self) -> Path:
        """
        Obtiene el directorio de logs actual
        
        Returns:
            Path: Ruta al directorio de logs
        """
        return self.current_log_dir
    
    def close(self):
        """Cierra el handler de logs y guarda resumen final"""
        try:
            # Log de cierre
            logging.info("="*70)
            logging.info("📁 SESIÓN FINALIZADA - Logs guardados en:")
            logging.info(f"   {self.current_log_dir}")
            logging.info("="*70)
            
            # Remover handler
            if self.file_handler:
                root_logger = logging.getLogger()
                root_logger.removeHandler(self.file_handler)
                self.file_handler.close()
        except Exception as e:
            logging.error(f"Error cerrando logger: {e}")