// VPS监控系统 Web界面脚本

// 模拟数据 - 在实际部署中需要连接到后端API
let mockData = {
    monitors: [
        {
            id: '1',
            name: 'Racknerd 2G VPS',
            url: 'https://example.com/racknerd-2g',
            config: '2GB RAM, 20GB SSD',
            status: true,
            lastChecked: '2024-01-15 14:30:00'
        },
        {
            id: '2',
            name: 'Hostinger VPS',
            url: 'https://example.com/hostinger-vps',
            config: '4GB RAM, 40GB SSD',
            status: false,
            lastChecked: '2024-01-15 14:25:00'
        },
        {
            id: '3',
            name: 'DigitalOcean Droplet',
            url: 'https://example.com/do-droplet',
            config: '1GB RAM, 25GB SSD',
            status: null,
            lastChecked: '2024-01-15 14:20:00'
        }
    ],
    systemStatus: {
        running: true,
        uptime: '2天 14小时',
        lastCheck: '刚刚',
        totalChecks: 1547,
        successRate: 96.8
    },
    logs: [
        '[2024-01-15 14:30:15] INFO: 检查 Racknerd 2G VPS - 状态: 有货',
        '[2024-01-15 14:25:10] WARN: 检查 Hostinger VPS - 状态: 无货',
        '[2024-01-15 14:20:05] ERROR: 检查 DigitalOcean Droplet 失败 - 连接超时',
        '[2024-01-15 14:15:00] INFO: 监控服务启动',
        '[2024-01-15 14:10:32] INFO: 发送通知: Racknerd 2G VPS 现在有货!'
    ]
};

// 标签页切换
function showTab(tabName) {
    // 隐藏所有标签页内容
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // 移除所有标签的活动状态
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // 显示选中的标签页
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');
    
    // 根据标签页加载相应数据
    switch(tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'monitors':
            loadMonitors();
            break;
        case 'logs':
            loadLogs();
            break;
        case 'settings':
            loadSettings();
            break;
    }
}

// 加载仪表盘数据
function loadDashboard() {
    const inStockCount = mockData.monitors.filter(m => m.status === true).length;
    const outStockCount = mockData.monitors.filter(m => m.status === false).length;
    
    document.getElementById('monitor-count').textContent = mockData.monitors.length;
    document.getElementById('in-stock-count').textContent = inStockCount;
    document.getElementById('out-stock-count').textContent = outStockCount;
    document.getElementById('last-check').textContent = mockData.systemStatus.lastCheck;
    
    // 更新系统状态
    document.getElementById('system-status').innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div>
                <strong>服务状态:</strong> 
                <span style="color: ${mockData.systemStatus.running ? '#28a745' : '#dc3545'}">
                    ${mockData.systemStatus.running ? '🟢 运行中' : '🔴 已停止'}
                </span>
            </div>
            <div><strong>运行时间:</strong> ${mockData.systemStatus.uptime}</div>
            <div><strong>总检查次数:</strong> ${mockData.systemStatus.totalChecks}</div>
            <div><strong>成功率:</strong> ${mockData.systemStatus.successRate}%</div>
        </div>
    `;
}

// 加载监控列表
function loadMonitors() {
    const container = document.getElementById('monitor-list');
    
    if (mockData.monitors.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6c757d; padding: 40px;">暂无监控项目</p>';
        return;
    }
    
    let html = '';
    mockData.monitors.forEach(monitor => {
        let statusBadge = '';
        if (monitor.status === true) {
            statusBadge = '<span class="status-badge in-stock">有货</span>';
        } else if (monitor.status === false) {
            statusBadge = '<span class="status-badge out-of-stock">无货</span>';
        } else {
            statusBadge = '<span class="status-badge unknown">未知</span>';
        }
        
        html += `
            <div class="monitor-item">
                <div class="monitor-info">
                    <h4>${monitor.name}</h4>
                    <p>🔗 ${monitor.url}</p>
                    ${monitor.config ? `<p>⚙️ ${monitor.config}</p>` : ''}
                    <p>🕒 最后检查: ${monitor.lastChecked}</p>
                </div>
                <div class="monitor-status">
                    ${statusBadge}
                    <button class="btn btn-danger" onclick="deleteMonitor('${monitor.id}')">🗑️</button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// 加载日志
function loadLogs() {
    const container = document.getElementById('log-container');
    let html = '';
    
    mockData.logs.forEach(log => {
        let className = 'log-line';
        if (log.includes('ERROR')) className += ' error';
        else if (log.includes('WARN')) className += ' warning';
        else if (log.includes('INFO')) className += ' info';
        
        html += `<div class="${className}">${log}</div>`;
    });
    
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight; // 滚动到底部
}

// 加载设置
function loadSettings() {
    // 这里可以从服务器加载当前设置
    console.log('设置页面已加载');
}

// 刷新日志
function refreshLogs() {
    // 模拟添加新日志
    const now = new Date().toISOString().replace('T', ' ').substr(0, 19);
    mockData.logs.unshift(`[${now}] INFO: 手动刷新日志`);
    if (mockData.logs.length > 50) {
        mockData.logs = mockData.logs.slice(0, 50); // 保持最新50条
    }
    loadLogs();
}

// 显示添加监控模态框
function showAddModal() {
    document.getElementById('addModal').style.display = 'block';
}

// 关闭模态框
function closeModal() {
    document.getElementById('addModal').style.display = 'none';
    // 清空表单
    document.getElementById('add-name').value = '';
    document.getElementById('add-config').value = '';
    document.getElementById('add-url').value = '';
}

// 添加监控项目
function addMonitor() {
    const name = document.getElementById('add-name').value.trim();
    const config = document.getElementById('add-config').value.trim();
    const url = document.getElementById('add-url').value.trim();
    
    if (!name || !url) {
        alert('请填写产品名称和URL');
        return;
    }
    
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        alert('URL必须以http://或https://开头');
        return;
    }
    
    // 检查URL是否已存在
    if (mockData.monitors.some(m => m.url === url)) {
        alert('该URL已在监控列表中');
        return;
    }
    
    // 添加到模拟数据
    const newMonitor = {
        id: Date.now().toString(),
        name: name,
        url: url,
        config: config,
        status: null,
        lastChecked: '从未检查'
    };
    
    mockData.monitors.push(newMonitor);
    closeModal();
    
    // 刷新监控列表
    if (document.getElementById('monitors').classList.contains('active')) {
        loadMonitors();
    }
    
    // 显示成功消息
    showAlert('success', '监控项目添加成功！');
}

// 删除监控项目
function deleteMonitor(id) {
    if (confirm('确定要删除这个监控项目吗？')) {
        mockData.monitors = mockData.monitors.filter(m => m.id !== id);
        loadMonitors();
        showAlert('success', '监控项目已删除');
    }
}

// 保存设置
function saveSettings() {
    const interval = document.getElementById('check-interval').value;
    const maxNotifications = document.getElementById('max-notifications').value;
    const timeout = document.getElementById('request-timeout').value;
    
    // 这里应该发送到服务器保存
    console.log('保存设置:', { interval, maxNotifications, timeout });
    showAlert('success', '设置保存成功！');
}

// 重启服务
function restartService() {
    if (confirm('确定要重启监控服务吗？这可能会短暂中断监控。')) {
        showAlert('warning', '正在重启服务...');
        // 这里应该调用服务器API重启服务
        setTimeout(() => {
            showAlert('success', '服务重启成功！');
        }, 3000);
    }
}

// 显示提示消息
function showAlert(type, message) {
    const alertHtml = `
        <div class="alert alert-${type}" style="position: fixed; top: 20px; right: 20px; z-index: 1001; min-width: 300px;">
            ${message}
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // 3秒后自动移除
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        if (alerts.length > 0) {
            alerts[alerts.length - 1].remove();
        }
    }, 3000);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 关闭模态框事件
    document.querySelector('.close').onclick = closeModal;
    
    // 点击模态框外部关闭
    window.onclick = function(event) {
        const modal = document.getElementById('addModal');
        if (event.target === modal) {
            closeModal();
        }
    };
    
    // 加载初始数据
    loadDashboard();
    
    // 定期刷新数据 (每30秒)
    setInterval(() => {
        if (document.getElementById('dashboard').classList.contains('active')) {
            loadDashboard();
        }
    }, 30000);
});
