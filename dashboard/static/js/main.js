// ============================================
// TRADING BOT DASHBOARD - MAIN JAVASCRIPT
// Optimized & Clean Code
// ============================================

const REFRESH_INTERVAL = 10000; // 10 segundos

// ============================================
// UTILITY FUNCTIONS
// ============================================

function formatCurrency(amount) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

function updateTimestamp() {
    const now = new Date();
    const element = document.getElementById('last-update');
    if (element) {
        element.textContent = now.toLocaleTimeString('es-ES');
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// ============================================
// API CALLS - ACCOUNT
// ============================================

async function updateAccount() {
    try {
        const response = await fetch('/api/account');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        const balanceEl = document.getElementById('balance');
        const availableEl = document.getElementById('available');
        const marginUsedEl = document.getElementById('margin-used');
        const marginPercentEl = document.getElementById('margin-percent');
        
        if (balanceEl) balanceEl.textContent = formatCurrency(data.balance);
        if (availableEl) availableEl.textContent = formatCurrency(data.available);
        if (marginUsedEl) marginUsedEl.textContent = formatCurrency(data.margin_used);
        if (marginPercentEl) marginPercentEl.textContent = data.margin_percent.toFixed(1) + '%';
        
    } catch (error) {
        console.error('Error actualizando cuenta:', error);
    }
}

// ============================================
// API CALLS - POSITIONS
// ============================================

async function updatePositions() {
    try {
        const response = await fetch('/api/positions');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        const countEl = document.getElementById('positions-count');
        const container = document.getElementById('positions-container');
        
        if (countEl) countEl.textContent = data.count;
        if (!container) return;
        
        if (data.count === 0) {
            container.innerHTML = '<p class="empty-state">No hay posiciones abiertas</p>';
            return;
        }
        
        let html = '';
        data.positions.forEach(pos => {
            const directionClass = pos.direction.toLowerCase();
            const tpDisplay = pos.limitLevel && pos.limitLevel > 0 
                ? formatCurrency(pos.limitLevel) 
                : '<span class="text-warning">N/A (no configurado)</span>';
            
            html += `
                <div class="position-card ${directionClass}">
                    <div class="position-header">
                        <span class="position-epic">${pos.epic}</span>
                        <span class="position-direction ${directionClass}">${pos.direction}</span>
                    </div>
                    <div class="position-details">
                        <div class="position-detail-item">
                            <span class="detail-label">Tamaño</span>
                            <span class="detail-value">${pos.size}</span>
                        </div>
                        <div class="position-detail-item">
                            <span class="detail-label">Precio Entrada</span>
                            <span class="detail-value">${formatCurrency(pos.level)}</span>
                        </div>
                        <div class="position-detail-item">
                            <span class="detail-label">Stop Loss</span>
                            <span class="detail-value">${formatCurrency(pos.stopLevel)}</span>
                        </div>
                        <div class="position-detail-item">
                            <span class="detail-label">Take Profit</span>
                            <span class="detail-value">${tpDisplay}</span>
                        </div>
                        <div class="position-detail-item">
                            <span class="detail-label">Deal ID</span>
                            <span class="detail-value" style="font-size: 0.75rem;">${pos.dealId}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error actualizando posiciones:', error);
    }
}

// ============================================
// API CALLS - CONFIGURATION
// ============================================

async function updateConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        const container = document.getElementById('config-container');
        if (!container) return;
        
        const html = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Activos</div>
                    <div class="stat-value" style="font-size: 1rem;">${data.assets.join(', ')}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Posiciones Máximas</div>
                    <div class="stat-value">${data.max_positions}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">% Margen Objetivo</div>
                    <div class="stat-value">${data.target_percent.toFixed(0)}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Riesgo Máximo</div>
                    <div class="stat-value">${data.max_risk.toFixed(0)}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Timeframe</div>
                    <div class="stat-value">${data.timeframe}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Horario Trading</div>
                    <div class="stat-value" style="font-size: 1rem;">${data.trading_hours}</div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error actualizando configuración:', error);
    }
}

// ============================================
// API CALLS - BOT STATUS
// ============================================

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (!statusDot || !statusText || !startBtn || !stopBtn) {
            console.error('Elementos del DOM no encontrados');
            return;
        }
        
        if (data.running) {
            statusDot.className = 'dot online';
            statusText.textContent = data.is_trading_hours ? '🟢 Operando' : '🟡 Esperando horario';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusDot.className = 'dot offline';
            statusText.textContent = '🔴 Pausado';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
        
    } catch (error) {
        console.error('Error actualizando estado:', error);
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        if (statusDot && statusText) {
            statusDot.className = 'dot offline';
            statusText.textContent = '🔴 Error de conexión';
        }
    }
}

// ============================================
// BOT CONTROL
// ============================================

async function startBot() {
    try {
        showToast('Iniciando bot...', 'info');
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('Bot iniciado correctamente', 'success');
            await updateStatus();
        } else {
            showToast('Error al iniciar bot', 'error');
        }
    } catch (error) {
        console.error('Error iniciando bot:', error);
        showToast('Error de conexión', 'error');
    }
}

async function stopBot() {
    try {
        showToast('Pausando bot...', 'info');
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('Bot pausado correctamente', 'success');
            await updateStatus();
        } else {
            showToast('Error al pausar bot', 'error');
        }
    } catch (error) {
        console.error('Error pausando bot:', error);
        showToast('Error de conexión', 'error');
    }
}

// ============================================
// TRADES HISTORY
// ============================================

async function loadTradesHistory() {
    try {
        const sessionId = document.getElementById('session-filter')?.value || '';
        const limit = document.getElementById('limit-filter')?.value || '50';
        
        let url = `/api/trades/history?limit=${limit}`;
        if (sessionId) url += `&session_id=${sessionId}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('trades-container');
        if (!container) return;
        
        if (!data.trades || data.trades.length === 0) {
            container.innerHTML = '<p class="empty-state">No hay trades disponibles</p>';
            return;
        }
        
        let html = '<table><thead><tr>';
        html += '<th>Epic</th><th>Dirección</th><th>Entrada</th><th>Salida</th>';
        html += '<th>P&L</th><th>P&L %</th><th>Razón Cierre</th></tr></thead><tbody>';
        
        data.trades.forEach(trade => {
            const pnlClass = trade.pnl >= 0 ? 'text-success' : 'text-danger';
            html += `
                <tr>
                    <td>${trade.epic}</td>
                    <td>${trade.direction}</td>
                    <td>${formatCurrency(trade.entry_price)}</td>
                    <td>${formatCurrency(trade.exit_price)}</td>
                    <td class="${pnlClass}">${formatCurrency(trade.pnl)}</td>
                    <td class="${pnlClass}">${trade.pnl_percent.toFixed(2)}%</td>
                    <td>${trade.close_reason || 'N/A'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error cargando historial:', error);
    }
}

// ============================================
// STATISTICS
// ============================================

async function loadStatistics() {
    try {
        const response = await fetch('/api/trades/stats');
        const data = await response.json();
        
        const container = document.getElementById('stats-container');
        if (!container || !data.stats) return;
        
        const stats = data.stats;
        
        const html = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Trades</div>
                    <div class="stat-value">${stats.total_trades || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Win Rate</div>
                    <div class="stat-value text-success">${(stats.win_rate || 0).toFixed(1)}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">P&L Total</div>
                    <div class="stat-value ${stats.total_pnl >= 0 ? 'text-success' : 'text-danger'}">
                        ${formatCurrency(stats.total_pnl || 0)}
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Profit Factor</div>
                    <div class="stat-value">${(stats.profit_factor || 0).toFixed(2)}</div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

// ============================================
// EXPORT FUNCTIONS
// ============================================

async function exportTradesCSV() {
    try {
        showToast('Descargando CSV...', 'info');
        const sessionId = document.getElementById('session-filter')?.value || '';
        let url = '/api/trades/export/csv';
        if (sessionId) url += `?session_id=${sessionId}`;
        
        window.location.href = url;
        showToast('CSV descargado', 'success');
    } catch (error) {
        console.error('Error exportando CSV:', error);
        showToast('Error al exportar', 'error');
    }
}

async function exportTradesExcel() {
    try {
        showToast('Descargando Excel...', 'info');
        const sessionId = document.getElementById('session-filter')?.value || '';
        let url = '/api/trades/export/excel';
        if (sessionId) url += `?session_id=${sessionId}`;
        
        window.location.href = url;
        showToast('Excel descargado', 'success');
    } catch (error) {
        console.error('Error exportando Excel:', error);
        showToast('Error al exportar', 'error');
    }
}

async function generateFullReport() {
    try {
        const sessionId = document.getElementById('session-filter')?.value;
        if (!sessionId) {
            showToast('Selecciona una sesión primero', 'error');
            return;
        }
        
        showToast('Generando reporte completo...', 'info');
        window.location.href = `/api/report/full?session_id=${sessionId}`;
        showToast('Reporte generado', 'success');
    } catch (error) {
        console.error('Error generando reporte:', error);
        showToast('Error al generar reporte', 'error');
    }
}

// ============================================
// BACKTESTING
// ============================================

async function runBacktest() {
    try {
        const days = document.getElementById('backtest-days')?.value || 30;
        const capital = document.getElementById('backtest-capital')?.value || 10000;
        
        showToast('Ejecutando backtest...', 'info');
        
        const response = await fetch('/api/backtest/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ days: parseInt(days), initial_capital: parseFloat(capital) })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
            return;
        }
        
        const container = document.getElementById('backtest-results');
        if (!container) return;
        
        const results = data.results;
        const html = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Capital Final</div>
                    <div class="stat-value">${formatCurrency(results.final_capital)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Retorno</div>
                    <div class="stat-value ${results.total_return >= 0 ? 'text-success' : 'text-danger'}">
                        ${results.total_return_percent.toFixed(2)}%
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Win Rate</div>
                    <div class="stat-value text-success">${results.win_rate.toFixed(1)}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Trades</div>
                    <div class="stat-value">${results.total_trades}</div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        showToast('Backtest completado', 'success');
        
    } catch (error) {
        console.error('Error en backtest:', error);
        showToast('Error ejecutando backtest', 'error');
    }
}

// ============================================
// SIGNALS
// ============================================

async function loadRecentSignals() {
    try {
        const response = await fetch('/api/signals/recent?limit=20');
        const data = await response.json();
        
        const container = document.getElementById('signals-container');
        if (!container) return;
        
        if (!data.signals || data.signals.length === 0) {
            container.innerHTML = '<p class="empty-state">No hay señales recientes</p>';
            return;
        }
        
        let html = '<table><thead><tr>';
        html += '<th>Epic</th><th>Señal</th><th>Confianza</th><th>Precio</th><th>Timestamp</th></tr></thead><tbody>';
        
        data.signals.forEach(signal => {
            const confidenceClass = signal.confidence >= 0.7 ? 'text-success' : signal.confidence >= 0.5 ? 'text-warning' : 'text-danger';
            html += `
                <tr>
                    <td>${signal.epic}</td>
                    <td>${signal.signal}</td>
                    <td class="${confidenceClass}">${(signal.confidence * 100).toFixed(1)}%</td>
                    <td>${formatCurrency(signal.price)}</td>
                    <td>${new Date(signal.timestamp).toLocaleString('es-ES')}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error cargando señales:', error);
    }
}

// ============================================
// MAIN UPDATE FUNCTION
// ============================================

async function updateAll() {
    updateTimestamp();
    await Promise.all([
        updateAccount(),
        updatePositions(),
        updateConfig(),
        updateStatus()
    ]);
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard inicializado');
    updateAll();
    loadTradesHistory();
    loadStatistics();
    
    // Auto-refresh
    setInterval(updateAll, REFRESH_INTERVAL);
});