#!/bin/bash
# VPS监控系统 v2.0 - 主管理菜单（优化版）
# 作者: kure29
# 网站: https://kure29.com

set -e
cd "$(dirname "$0")/.."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# 状态缓存
declare -A status_cache
cache_timeout=30

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 显示Banner
show_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
 ██╗   ██╗██████╗ ███████╗    ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ 
 ██║   ██║██╔══██╗██╔════╝    ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗
 ██║   ██║██████╔╝███████╗    ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝
 ╚██╗ ██╔╝██╔═══╝ ╚════██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗
  ╚████╔╝ ██║     ███████║    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║
   ╚═══╝  ╚═╝     ╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
EOF
    echo -e "${NC}"
    echo -e "${PURPLE}VPS库存监控系统 v2.0 - 数据库优化版${NC}"
    echo -e "${CYAN}作者: kure29 | 网站: https://kure29.com${NC}"
    echo ""
}

# 缓存状态信息
cache_status() {
    local current_time=$(date +%s)
    
    status_cache[monitor_status]=$(get_monitor_status_direct)
    status_cache[process_info]=$(get_process_info_direct)
    status_cache[monitor_count]=$(get_monitor_count_direct)
    status_cache[cache_time]=$current_time
}

# 获取缓存的状态信息
get_cached_status() {
    local cache_time=${status_cache[cache_time]:-0}
    local current_time=$(date +%s)
    
    # 缓存超过指定时间则刷新
    if (( current_time - cache_time > cache_timeout )); then
        cache_status
    fi
    
    echo "${status_cache[monitor_status]}"
}

get_cached_process_info() {
    local cache_time=${status_cache[cache_time]:-0}
    local current_time=$(date +%s)
    
    if (( current_time - cache_time > cache_timeout )); then
        cache_status
    fi
    
    echo "${status_cache[process_info]}"
}

get_cached_monitor_count() {
    local cache_time=${status_cache[cache_time]:-0}
    local current_time=$(date +%s)
    
    if (( current_time - cache_time > cache_timeout )); then
        cache_status
    fi
    
    echo "${status_cache[monitor_count]}"
}

# 检查Python环境
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        log_debug "检测到Python版本: $python_version"
        
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
            return 0
        else
            log_warn "Python版本过低，需要3.7或更高版本，当前版本: $python_version"
            return 1
        fi
    else
        log_warn "未找到Python3"
        return 1
    fi
}

# 检查虚拟环境
check_venv() {
    if [[ -d "venv" && -f "venv/bin/activate" ]]; then
        log_debug "找到Python虚拟环境"
        return 0
    else
        log_warn "未找到Python虚拟环境"
        return 1
    fi
}

# 创建虚拟环境
create_venv() {
    log_info "创建Python虚拟环境..."
    python3 -m venv venv
    log_success "虚拟环境创建成功"
}

# 激活虚拟环境
activate_venv() {
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        log_debug "Python虚拟环境已激活"
        return 0
    else
        log_error "虚拟环境不存在"
        return 1
    fi
}

# 安装依赖
install_dependencies() {
    log_info "安装Python依赖包..."
    if [[ -f "requirements.txt" ]]; then
        pip install --upgrade pip
        pip install -r requirements.txt
        log_success "依赖安装完成"
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
}

# 检查配置文件
check_config() {
    if [[ -f "config.json" ]]; then
        if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
            log_debug "配置文件格式正确"
            
            # 检查关键配置
            local bot_token=$(python3 -c "import json; print(json.load(open('config.json')).get('bot_token', ''))" 2>/dev/null)
            local chat_id=$(python3 -c "import json; print(json.load(open('config.json')).get('chat_id', ''))" 2>/dev/null)
            
            if [[ "$bot_token" == "YOUR_TELEGRAM_BOT_TOKEN" || -z "$bot_token" ]]; then
                log_warn "请配置正确的bot_token"
                return 1
            fi
            
            if [[ "$chat_id" == "YOUR_TELEGRAM_CHAT_ID" || -z "$chat_id" ]]; then
                log_warn "请配置正确的chat_id"
                return 1
            fi
            
            log_debug "配置文件检查通过"
            return 0
        else
            log_error "配置文件格式错误"
            return 1
        fi
    else
        log_warn "配置文件不存在"
        if [[ -f "config/config.json.example" ]]; then
            cp config/config.json.example config.json
            log_info "已从示例创建配置文件"
        fi
        return 1
    fi
}

# 检查数据库
check_database() {
    if [[ -f "vps_monitor.db" ]]; then
        log_debug "发现数据库文件: vps_monitor.db"
        local size=$(du -h vps_monitor.db | cut -f1)
        log_debug "数据库大小: $size"
        return 0
    else
        log_info "数据库文件不存在，将在首次运行时创建"
        return 1
    fi
}

# 初始化环境
init_environment() {
    log_info "首次运行，正在初始化环境..."
    
    # 检查Python
    log_info "正在设置Python环境..."
    if ! check_python; then
        log_error "Python环境检查失败"
        return 1
    fi
    
    # 检查并创建虚拟环境
    if ! check_venv; then
        create_venv
    fi
    
    # 激活虚拟环境
    if ! activate_venv; then
        log_error "无法激活虚拟环境"
        return 1
    fi
    
    # 安装依赖
    if ! install_dependencies; then
        log_error "依赖安装失败"
        return 1
    fi
    
    # 检查配置文件
    if ! check_config; then
        log_warn "请编辑config.json文件配置Telegram信息"
    fi
    
    # 检查数据库
    check_database
    
    log_success "环境初始化完成"
}

# 直接获取监控状态（不使用缓存）
get_monitor_status_direct() {
    local pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "运行中"
        return 0
    else
        echo "已停止"
        return 1
    fi
}

# 获取监控状态（使用缓存）
get_monitor_status() {
    get_cached_status
}

# 直接获取进程信息（不使用缓存）
get_process_info_direct() {
    local pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        for pid in $pids; do
            local runtime=$(ps -o etime= -p $pid 2>/dev/null | tr -d ' ' || echo "unknown")
            local memory=$(ps -o rss= -p $pid 2>/dev/null | awk '{printf "%.1fMB", $1/1024}' || echo "unknown")
            echo "PID=$pid, 运行时间=$runtime, 内存占用=$memory"
        done
    else
        echo "无运行进程"
    fi
}

# 获取进程信息（使用缓存）
get_process_info() {
    get_cached_process_info
}

# 直接获取监控商品数量（不使用缓存）
get_monitor_count_direct() {
    if [[ -f "vps_monitor.db" ]] && activate_venv; then
        local count=$(python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM monitor_items WHERE enabled = 1')
    result = cursor.fetchone()
    print(result[0] if result else 0)
    conn.close()
except:
    print(0)
" 2>/dev/null || echo "0")
        echo "$count"
    else
        echo "0"
    fi
}

# 获取监控商品数量（使用缓存）
get_monitor_count() {
    get_cached_monitor_count
}

# 显示系统状态
show_status() {
    local status=$(get_monitor_status)
    local process_info=$(get_process_info)
    local monitor_count=$(get_monitor_count)
    
    echo "========================================"
    if [[ "$status" == "运行中" ]]; then
        echo -e "监控状态: ${GREEN}$status${NC}"
        echo "进程信息: $process_info"
    else
        echo -e "监控状态: ${RED}$status${NC}"
    fi
    echo "监控商品数: $monitor_count"
    
    # 显示数据库信息
    if [[ -f "vps_monitor.db" ]]; then
        local db_size=$(du -h vps_monitor.db | cut -f1)
        echo "数据库大小: $db_size"
    fi
    
    # 显示智能提示
    show_smart_hints
}

# 智能提示
show_smart_hints() {
    echo ""
    if [[ ! -f "config.json" ]]; then
        echo -e "${YELLOW}💡 提示: 请先配置Telegram信息${NC}"
    elif ! check_config >/dev/null 2>&1; then
        echo -e "${YELLOW}💡 提示: 配置文件需要更新${NC}"
    elif [[ $(get_monitor_status) == "已停止" ]]; then
        echo -e "${YELLOW}💡 提示: 监控未运行，建议启动监控${NC}"
    elif [[ $(get_monitor_count) == "0" ]]; then
        echo -e "${YELLOW}💡 提示: 尚未添加监控商品${NC}"
    else
        echo -e "${GREEN}💡 系统运行正常${NC}"
    fi
}

# 配置Telegram信息
configure_telegram() {
    echo "配置Telegram信息"
    echo "================"
    
    echo "获取Bot Token的步骤："
    echo "1. 在Telegram中搜索 @BotFather"
    echo "2. 发送 /newbot 命令"
    echo "3. 按提示创建机器人并获取Token"
    echo ""
    
    echo -n "请输入Bot Token: "
    read -r bot_token
    
    if [[ -z "$bot_token" ]]; then
        log_error "Bot Token不能为空"
        return 1
    fi
    
    echo ""
    echo "获取Chat ID的步骤："
    echo "1. 在Telegram中搜索 @userinfobot"
    echo "2. 发送 /start 命令"
    echo "3. 复制返回的数字ID"
    echo ""
    
    echo -n "请输入Chat ID: "
    read -r chat_id
    
    if [[ -z "$chat_id" ]]; then
        log_error "Chat ID不能为空"
        return 1
    fi
    
    # 可选配置
    echo ""
    echo "可选配置（留空使用默认值）："
    echo -n "频道ID（用于发送通知，留空则发送到私聊）: "
    read -r channel_id
    
    echo -n "管理员ID（多个ID用逗号分隔，留空则所有人可管理）: "
    read -r admin_ids
    
    # 创建配置文件
    cat > config.json << EOF
{
    "bot_token": "$bot_token",
    "chat_id": "$chat_id",
    "channel_id": "$channel_id",
    "admin_ids": [$(echo "$admin_ids" | sed 's/,/", "/g' | sed 's/.*/\"&\"/' | sed 's/\"\"//g')],
    "check_interval": 180,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600,
    "request_timeout": 30,
    "retry_delay": 60,
    "items_per_page": 10
}
EOF
    
    log_success "配置文件已保存"
    
    # 清除缓存，强制刷新状态
    unset status_cache
    declare -A status_cache
    
    # 测试配置
    echo -n "是否测试Telegram连接? (y/N): "
    read -r test_conn
    
    if [[ "$test_conn" == "y" || "$test_conn" == "Y" ]]; then
        test_telegram_connection
    fi
}

# 测试Telegram连接
test_telegram_connection() {
    log_info "测试Telegram连接..."
    
    if activate_venv; then
        python3 -c "
import requests
import json

try:
    config = json.load(open('config.json'))
    resp = requests.get(f'https://api.telegram.org/bot{config[\"bot_token\"]}/getMe', timeout=10)
    
    if resp.json().get('ok'):
        print('✅ Telegram Bot连接成功')
        
        # 发送测试消息
        test_resp = requests.post(
            f'https://api.telegram.org/bot{config[\"bot_token\"]}/sendMessage', 
            json={'chat_id': config['chat_id'], 'text': '🤖 VPS监控系统 v2.0 测试消息'}, 
            timeout=10
        )
        
        if test_resp.json().get('ok'):
            print('✅ 测试消息发送成功')
        else:
            print('❌ 测试消息发送失败，请检查Chat ID')
    else:
        print('❌ Telegram Bot连接失败，请检查Token')
except Exception as e:
    print(f'❌ 测试失败: {e}')
" 2>&1
    fi
}

# 启动监控
start_monitor() {
    echo "启动监控"
    echo "========"
    
    # 检查是否已在运行
    if get_monitor_status_direct >/dev/null; then
        log_warn "监控程序已在运行中"
        return 1
    fi
    
    # 检查配置
    if ! check_config; then
        log_error "请先配置Telegram信息"
        return 1
    fi
    
    # 激活虚拟环境
    if ! activate_venv; then
        return 1
    fi
    
    log_info "启动监控程序..."
    
    # 启动监控（后台运行）
    nohup python3 src/monitor.py > monitor.log 2>&1 &
    local pid=$!
    
    # 等待一下检查是否成功启动
    sleep 3
    
    if kill -0 $pid 2>/dev/null; then
        log_success "监控程序启动成功 (PID: $pid)"
        log_info "日志文件: monitor.log"
        
        # 清除缓存，强制刷新状态
        unset status_cache
        declare -A status_cache
    else
        log_error "监控程序启动失败，请查看日志文件"
        return 1
    fi
}

# 停止监控
stop_monitor() {
    echo "停止监控"
    echo "========"
    
    local pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || true)
    
    if [[ -n "$pids" ]]; then
        log_info "停止监控程序..."
        for pid in $pids; do
            kill $pid
            log_info "已发送停止信号给进程 $pid"
        done
        
        # 等待进程停止
        sleep 2
        
        # 检查是否还在运行
        local remaining_pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || true)
        if [[ -n "$remaining_pids" ]]; then
            log_warn "强制停止残留进程..."
            for pid in $remaining_pids; do
                kill -9 $pid
                log_info "强制停止进程 $pid"
            done
        fi
        
        log_success "监控程序已停止"
        
        # 清除缓存，强制刷新状态
        unset status_cache
        declare -A status_cache
    else
        log_warn "监控程序未运行"
    fi
}

# 查看监控状态
check_monitor_status() {
    echo "监控状态详情"
    echo "============"
    
    local status=$(get_monitor_status_direct)
    local process_info=$(get_process_info_direct)
    local monitor_count=$(get_monitor_count_direct)
    
    if [[ "$status" == "运行中" ]]; then
        echo -e "状态: ${GREEN}$status${NC}"
        echo "进程信息: $process_info"
        echo "监控商品数: $monitor_count"
        
        # 显示最近日志
        if [[ -f "monitor.log" ]]; then
            echo ""
            echo "最近日志 (最后10行):"
            echo "==================="
            tail -n 10 monitor.log
        fi
    else
        echo -e "状态: ${RED}$status${NC}"
        echo "监控商品数: $monitor_count"
        
        if [[ -f "monitor.log" ]]; then
            echo ""
            echo "最后的错误日志:"
            echo "=============="
            tail -n 5 monitor.log | grep -i error || echo "没有发现错误"
        fi
    fi
    
    # 显示数据库统计
    show_database_stats
}

# 显示数据库统计
show_database_stats() {
    if [[ -f "vps_monitor.db" ]] && activate_venv; then
        echo ""
        echo "数据库统计:"
        echo "=========="
        python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 获取最近24小时的检查统计
    since = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ?', (since,))
    checks_24h = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ? AND status = 1', (since,))
    success_24h = cursor.fetchone()[0]
    
    print(f'最近24小时检查: {checks_24h} 次')
    print(f'检查成功次数: {success_24h} 次')
    
    if checks_24h > 0:
        success_rate = (success_24h / checks_24h) * 100
        print(f'成功率: {success_rate:.1f}%')
    
    # 获取商品统计
    cursor.execute('SELECT COUNT(*) FROM monitor_items WHERE enabled = 1')
    enabled_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM monitor_items WHERE enabled = 0')
    disabled_items = cursor.fetchone()[0]
    
    print(f'启用商品: {enabled_items} 个')
    print(f'禁用商品: {disabled_items} 个')
    
    conn.close()
except Exception as e:
    print(f'获取统计失败: {e}')
" 2>&1
    fi
}

# 数据统计分析
show_statistics() {
    echo "数据统计分析"
    echo "============"
    
    if [[ ! -f "vps_monitor.db" ]]; then
        log_error "数据库文件不存在"
        return 1
    fi
    
    if ! activate_venv; then
        return 1
    fi
    
    echo "1. 成功率趋势分析"
    echo "2. 商品可用性统计"
    echo "3. 检查频率分析"
    echo "4. 最近错误统计"
    echo "5. 导出统计报告"
    echo "0. 返回主菜单"
    echo ""
    echo -n "请选择分析类型 (0-5): "
    read -r choice
    
    case $choice in
        1)
            analyze_success_rate
            ;;
        2)
            analyze_item_availability
            ;;
        3)
            analyze_check_frequency
            ;;
        4)
            analyze_recent_errors
            ;;
        5)
            export_statistics
            ;;
        0)
            return 0
            ;;
        *)
            log_error "无效选择"
            ;;
    esac
}

# 分析成功率趋势
analyze_success_rate() {
    echo ""
    echo "成功率趋势分析"
    echo "=============="
    
    python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 按天统计最近7天的成功率
    for i in range(7, 0, -1):
        date = datetime.now() - timedelta(days=i)
        start_time = date.replace(hour=0, minute=0, second=0).isoformat()
        end_time = date.replace(hour=23, minute=59, second=59).isoformat()
        
        cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ? AND check_time <= ?', (start_time, end_time))
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ? AND check_time <= ? AND status = 1', (start_time, end_time))
        success = cursor.fetchone()[0]
        
        if total > 0:
            rate = (success / total) * 100
            bar = '█' * int(rate / 5) + '░' * (20 - int(rate / 5))
            print(f'{date.strftime(\"%m-%d\")}: {bar} {rate:.1f}% ({success}/{total})')
        else:
            print(f'{date.strftime(\"%m-%d\")}: 无检查记录')
    
    conn.close()
except Exception as e:
    print(f'分析失败: {e}')
" 2>&1
}

# 分析商品可用性
analyze_item_availability() {
    echo ""
    echo "商品可用性统计"
    echo "=============="
    
    python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 获取所有商品的最新状态
    cursor.execute('''
        SELECT m.name, m.url, h.status, h.check_time
        FROM monitor_items m
        LEFT JOIN (
            SELECT item_id, status, check_time
            FROM check_history h1
            WHERE check_time = (
                SELECT MAX(check_time)
                FROM check_history h2
                WHERE h2.item_id = h1.item_id
            )
        ) h ON m.id = h.item_id
        WHERE m.enabled = 1
        ORDER BY m.name
    ''')
    
    results = cursor.fetchall()
    
    print(f'{"商品名称":<20} {"状态":<8} {"最后检查时间"}')
    print('-' * 60)
    
    available = 0
    unavailable = 0
    unknown = 0
    
    for name, url, status, check_time in results:
        if status is None:
            status_text = '未知'
            unknown += 1
        elif status == 1:
            status_text = '可用'
            available += 1
        else:
            status_text = '不可用'
            unavailable += 1
        
        if check_time:
            check_time = datetime.fromisoformat(check_time).strftime('%m-%d %H:%M')
        else:
            check_time = '从未检查'
        
        print(f'{name[:20]:<20} {status_text:<8} {check_time}')
    
    print('')
    print(f'可用: {available}, 不可用: {unavailable}, 未知: {unknown}')
    
    conn.close()
except Exception as e:
    print(f'分析失败: {e}')
" 2>&1
}

# 分析检查频率
analyze_check_frequency() {
    echo ""
    echo "检查频率分析"
    echo "============"
    
    python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 按小时统计最近24小时的检查次数
    print('最近24小时检查频率:')
    print('时间段      检查次数')
    print('-' * 25)
    
    for i in range(24, 0, -1):
        start_time = datetime.now() - timedelta(hours=i)
        end_time = start_time + timedelta(hours=1)
        
        cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ? AND check_time < ?', 
                      (start_time.isoformat(), end_time.isoformat()))
        count = cursor.fetchone()[0]
        
        bar = '█' * min(count, 20)
        print(f'{start_time.strftime(\"%H:00\")}:    {bar} {count}')
    
    # 平均检查间隔
    cursor.execute('SELECT check_time FROM check_history ORDER BY check_time DESC LIMIT 100')
    times = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
    
    if len(times) > 1:
        intervals = [(times[i] - times[i+1]).total_seconds() for i in range(len(times)-1)]
        avg_interval = sum(intervals) / len(intervals)
        print(f'\\n平均检查间隔: {avg_interval:.0f} 秒')
    
    conn.close()
except Exception as e:
    print(f'分析失败: {e}')
" 2>&1
}

# 分析最近错误
analyze_recent_errors() {
    echo ""
    echo "最近错误统计"
    echo "============"
    
    python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 获取最近的错误记录
    since = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute('''
        SELECT m.name, h.check_time, h.error_message
        FROM check_history h
        JOIN monitor_items m ON h.item_id = m.id
        WHERE h.status = 0 AND h.check_time >= ?
        ORDER BY h.check_time DESC
        LIMIT 20
    ''', (since,))
    
    results = cursor.fetchall()
    
    if results:
        print(f'{"时间":<16} {"商品名称":<20} {"错误信息"}')
        print('-' * 70)
        
        for name, check_time, error_msg in results:
            check_time = datetime.fromisoformat(check_time).strftime('%m-%d %H:%M')
            error_msg = error_msg[:30] + '...' if error_msg and len(error_msg) > 30 else error_msg or '未知错误'
            print(f'{check_time:<16} {name[:20]:<20} {error_msg}')
    else:
        print('最近7天内没有错误记录')
    
    conn.close()
except Exception as e:
    print(f'分析失败: {e}')
" 2>&1
}

# 导出统计报告
export_statistics() {
    echo ""
    echo "导出统计报告"
    echo "============"
    
    local export_file="reports/statistics_report_$(date +%Y%m%d_%H%M%S).txt"
    
    # 创建报告目录
    mkdir -p reports
    
    if activate_venv; then
        python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    report = []
    report.append(f'VPS监控系统统计报告')
    report.append(f'生成时间: {datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}')
    report.append('=' * 50)
    report.append('')
    
    # 总体统计
    cursor.execute('SELECT COUNT(*) FROM monitor_items WHERE enabled = 1')
    enabled_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM check_history')
    total_checks = cursor.fetchone()[0]
    
    since_24h = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ?', (since_24h,))
    checks_24h = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM check_history WHERE check_time >= ? AND status = 1', (since_24h,))
    success_24h = cursor.fetchone()[0]
    
    report.append('总体统计:')
    report.append(f'  活跃监控商品: {enabled_count} 个')
    report.append(f'  历史检查总数: {total_checks} 次')
    report.append(f'  24小时检查: {checks_24h} 次')
    if checks_24h > 0:
        success_rate = (success_24h / checks_24h) * 100
        report.append(f'  24小时成功率: {success_rate:.1f}%')
    report.append('')
    
    # 保存报告
    with open('$export_file', 'w', encoding='utf-8') as f:
        f.write('\\n'.join(report))
    
    print(f'报告已导出到: $export_file')
    conn.close()
except Exception as e:
    print(f'导出失败: {e}')
" 2>&1
    fi
}

# 系统健康检查
health_check() {
    echo "系统健康检查"
    echo "============"
    
    local issues=0
    
    echo "🔍 检查环境..."
    
    # 检查Python环境
    if check_python >/dev/null 2>&1; then
        echo "✅ Python环境正常"
    else
        echo "❌ Python环境异常"
        ((issues++))
    fi
    
    # 检查虚拟环境
    if check_venv >/dev/null 2>&1; then
        echo "✅ 虚拟环境正常"
    else
        echo "❌ 虚拟环境异常"
        ((issues++))
    fi
    
    # 检查配置文件
    if check_config >/dev/null 2>&1; then
        echo "✅ 配置文件正常"
    else
        echo "❌ 配置文件异常"
        ((issues++))
    fi
    
    # 检查数据库
    if check_database >/dev/null 2>&1; then
        echo "✅ 数据库文件存在"
        
        # 检查数据库完整性
        if activate_venv && python3 -c "
import sqlite3
conn = sqlite3.connect('vps_monitor.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check')
result = cursor.fetchone()[0]
conn.close()
exit(0 if result == 'ok' else 1)
" 2>/dev/null; then
            echo "✅ 数据库完整性正常"
        else
            echo "❌ 数据库完整性异常"
            ((issues++))
        fi
    else
        echo "⚠️  数据库文件不存在"
    fi
    
    # 检查日志文件
    if [[ -f "monitor.log" ]]; then
        local log_size=$(du -h monitor.log | cut -f1)
        echo "✅ 日志文件存在 (大小: $log_size)"
        
        # 检查是否有过多错误
        local error_count=$(grep -c "ERROR" monitor.log 2>/dev/null || echo "0")
        if [[ $error_count -gt 10 ]]; then
            echo "⚠️  日志中发现较多错误 ($error_count 个)"
        fi
    else
        echo "⚠️  日志文件不存在"
    fi
    
    # 检查磁盘空间
    local disk_usage=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -lt 90 ]]; then
        echo "✅ 磁盘空间充足 (已使用: ${disk_usage}%)"
    else
        echo "❌ 磁盘空间不足 (已使用: ${disk_usage}%)"
        ((issues++))
    fi
    
    # 检查网络连接
    echo ""
    echo "🌐 检查网络连接..."
    if curl -s --connect-timeout 5 https://api.telegram.org >/dev/null; then
        echo "✅ Telegram API 连接正常"
    else
        echo "❌ Telegram API 连接失败"
        ((issues++))
    fi
    
    # 生成健康报告
    echo ""
    echo "📊 健康检查报告:"
    echo "================"
    if [[ $issues -eq 0 ]]; then
        echo -e "${GREEN}🎉 系统健康状况良好，没有发现问题！${NC}"
    elif [[ $issues -eq 1 ]]; then
        echo -e "${YELLOW}⚠️  发现 $issues 个问题，建议修复${NC}"
    else
        echo -e "${RED}❌ 发现 $issues 个问题，需要立即处理${NC}"
    fi
}

# 查看监控日志
view_logs() {
    echo "监控日志"
    echo "========"
    
    if [[ ! -f "monitor.log" ]]; then
        log_warn "日志文件不存在"
        return 1
    fi
    
    echo "日志文件: monitor.log"
    echo "文件大小: $(du -h monitor.log | cut -f1)"
    echo ""
    
    echo "选择查看方式："
    echo "1. 查看最新50行"
    echo "2. 查看全部日志"
    echo "3. 实时监控日志"
    echo "4. 查看错误日志"
    echo "5. 按时间查看日志"
    echo -n "请选择 (1-5): "
    read -r choice
    
    case $choice in
        1)
            echo "最新50行日志:"
            echo "============="
            tail -n 50 monitor.log
            ;;
        2)
            echo "全部日志:"
            echo "========"
            less monitor.log
            ;;
        3)
            echo "实时监控日志 (按Ctrl+C退出):"
            echo "=========================="
            tail -f monitor.log
            ;;
        4)
            echo "错误日志:"
            echo "========"
            grep -i "error\|exception\|fail" monitor.log | tail -n 20
            ;;
        5)
            echo -n "请输入查看时间 (格式: 2024-01-01): "
            read -r date_filter
            echo "指定日期日志:"
            echo "============="
            grep "$date_filter" monitor.log || echo "未找到指定日期的日志"
            ;;
        *)
            log_error "无效选择"
            ;;
    esac
}

# 数据库管理
manage_database() {
    echo "数据库管理"
    echo "=========="
    
    if [[ ! -f "vps_monitor.db" ]]; then
        log_warn "数据库文件不存在"
        return 1
    fi
    
    echo "1. 查看数据库信息"
    echo "2. 备份数据库"
    echo "3. 导出数据到JSON"
    echo "4. 从JSON导入数据"
    echo "5. 清理历史数据"
    echo "6. 数据库优化"
    echo -n "请选择操作 (1-6): "
    read -r choice
    
    case $choice in
        1)
            view_database_info
            ;;
        2)
            backup_database
            ;;
        3)
            export_database
            ;;
        4)
            import_database
            ;;
        5)
            cleanup_database
            ;;
        6)
            optimize_database
            ;;
        *)
            log_error "无效选择"
            ;;
    esac
}

# 查看数据库信息
view_database_info() {
    echo ""
    echo "数据库信息:"
    echo "==========="
    
    local db_size=$(du -h vps_monitor.db | cut -f1)
    echo "文件大小: $db_size"
    
    if activate_venv; then
        python3 -c "
import sqlite3

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 获取表信息
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
    tables = cursor.fetchall()
    print(f'\\n数据表: {len(tables)} 个')
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
        count = cursor.fetchone()[0]
        print(f'  - {table[0]}: {count} 条记录')
    
    # 获取数据库大小信息
    cursor.execute('PRAGMA page_count')
    page_count = cursor.fetchone()[0]
    cursor.execute('PRAGMA page_size')
    page_size = cursor.fetchone()[0]
    
    print(f'\\n页面数量: {page_count}')
    print(f'页面大小: {page_size} bytes')
    print(f'数据库大小: {(page_count * page_size) / 1024 / 1024:.2f} MB')
    
    conn.close()
except Exception as e:
    print(f'读取数据库失败: {e}')
" 2>&1
    fi
}

# 备份数据库
backup_database() {
    echo ""
    local backup_file="backup/vps_monitor_$(date +%Y%m%d_%H%M%S).db"
    
    # 创建备份目录
    mkdir -p backup
    
    if cp vps_monitor.db "$backup_file"; then
        log_success "数据库备份成功: $backup_file"
        
        # 压缩备份文件
        if command -v gzip >/dev/null 2>&1; then
            gzip "$backup_file"
            log_info "备份文件已压缩: ${backup_file}.gz"
        fi
    else
        log_error "数据库备份失败"
    fi
}

# 导出数据库
export_database() {
    echo ""
    local export_file="export/vps_monitor_export_$(date +%Y%m%d_%H%M%S).json"
    
    # 创建导出目录
    mkdir -p export
    
    if activate_venv; then
        python3 -c "
import sys
sys.path.append('.')
from database_manager import DatabaseManager
import asyncio

async def export():
    db = DatabaseManager()
    await db.initialize()
    success = await db.export_to_json('$export_file')
    if success:
        print('✅ 数据导出成功: $export_file')
    else:
        print('❌ 数据导出失败')

asyncio.run(export())
" 2>&1
    fi
}

# 导入数据库
import_database() {
    echo ""
    echo -n "请输入要导入的JSON文件路径: "
    read -r import_file
    
    if [[ ! -f "$import_file" ]]; then
        log_error "文件不存在: $import_file"
        return 1
    fi
    
    if activate_venv; then
        python3 -c "
import sys
sys.path.append('.')
from database_manager import DatabaseManager
import asyncio

async def import_data():
    db = DatabaseManager()
    await db.initialize()
    success = await db.import_from_json('$import_file')
    if success:
        print('✅ 数据导入成功')
    else:
        print('❌ 数据导入失败')

asyncio.run(import_data())
" 2>&1
    fi
}

# 清理数据库
cleanup_database() {
    echo ""
    echo -n "清理多少天前的历史记录？(默认90天): "
    read -r days
    
    if [[ -z "$days" ]]; then
        days=90
    fi
    
    if activate_venv; then
        python3 -c "
import sys
sys.path.append('.')
from database_manager import DatabaseManager
import asyncio

async def cleanup():
    db = DatabaseManager()
    await db.initialize()
    deleted = await db.cleanup_old_history(days=$days)
    print(f'✅ 已清理 {deleted} 条历史记录')

asyncio.run(cleanup())
" 2>&1
    fi
}

# 数据库优化
optimize_database() {
    echo ""
    echo "数据库优化"
    echo "=========="
    
    if activate_venv; then
        python3 -c "
import sqlite3

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    print('正在优化数据库...')
    
    # 分析数据库
    cursor.execute('ANALYZE')
    print('✅ 数据库分析完成')
    
    # 清理碎片
    cursor.execute('VACUUM')
    print('✅ 数据库碎片清理完成')
    
    # 重建索引
    cursor.execute('REINDEX')
    print('✅ 索引重建完成')
    
    conn.close()
    print('✅ 数据库优化完成')
except Exception as e:
    print(f'❌ 数据库优化失败: {e}')
" 2>&1
    fi
}

# 从旧版本迁移数据
migrate_from_json() {
    echo "从JSON迁移到数据库"
    echo "=================="
    
    if [[ ! -f "urls.json" ]]; then
        log_warn "未找到urls.json文件"
        return 1
    fi
    
    log_info "开始迁移数据..."
    
    if activate_venv; then
        python3 -c "
import json
import asyncio
from database_manager import DatabaseManager

async def migrate():
    try:
        # 读取旧数据
        with open('urls.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # 初始化数据库
        db = DatabaseManager()
        await db.initialize()
        
        # 迁移数据
        migrated = 0
        for item_id, item_data in old_data.items():
            name = item_data.get('名称', '')
            url = item_data.get('URL', '')
            config = item_data.get('配置', '')
            
            # 检查是否已存在
            existing = await db.get_monitor_item_by_url(url)
            if not existing:
                await db.add_monitor_item(name, url, config)
                migrated += 1
                print(f'  ✅ 已迁移: {name}')
            else:
                print(f'  ⏭️  跳过已存在: {name}')
        
        print(f'\\n✅ 迁移完成，共迁移 {migrated} 个商品')
        
        # 备份旧文件
        import shutil
        shutil.copy('urls.json', 'urls.json.backup')
        print('✅ 旧数据已备份到 urls.json.backup')
        
    except Exception as e:
        print(f'❌ 迁移失败: {e}')

asyncio.run(migrate())
" 2>&1
    fi
}

# 主菜单
show_menu() {
    while true; do
        clear
        show_banner
        show_status
        
        echo " ============== VPS库存监控系统 v2.0 ============== "
        echo "1. 配置Telegram信息"
        echo "2. 启动监控"
        echo "3. 停止监控"
        echo "4. 查看监控状态"
        echo "5. 查看监控日志"
        echo "6. 数据库管理"
        echo "7. 数据统计分析         ${CYAN}[新功能]${NC}"
        echo "8. 系统健康检查         ${CYAN}[新功能]${NC}"
        echo "9. 从旧版本迁移数据"
        echo "0. 退出"
        echo "===================="
        
        # 显示当前状态
        local status=$(get_monitor_status)
        if [[ "$status" == "运行中" ]]; then
            local pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null | head -1)
            echo -e "监控状态: ${GREEN}运行中${NC} (PID: $pids)"
        else
            echo -e "监控状态: ${RED}未运行${NC}"
        fi
        
        # 显示统计信息
        local monitor_count=$(get_monitor_count)
        echo -e "监控商品: ${WHITE}$monitor_count${NC} 个"
        
        if [[ -f "vps_monitor.db" ]]; then
            local db_size=$(du -h vps_monitor.db | cut -f1)
            echo -e "数据库: ${WHITE}$db_size${NC}"
        fi
        
        echo "===================="
        
        echo -n "请选择操作 (0-9): "
        read -r choice
        
        case $choice in
            1)
                echo ""
                configure_telegram
                ;;
            2)
                echo ""
                start_monitor
                ;;
            3)
                echo ""
                stop_monitor
                ;;
            4)
                echo ""
                check_monitor_status
                ;;
            5)
                echo ""
                view_logs
                ;;
            6)
                echo ""
                manage_database
                ;;
            7)
                echo ""
                show_statistics
                ;;
            8)
                echo ""
                health_check
                ;;
            9)
                echo ""
                migrate_from_json
                ;;
            0)
                echo ""
                log_info "退出程序"
                exit 0
                ;;
            *)
                echo ""
                log_error "无效选择，请重新输入"
                ;;
        esac
        
        echo ""
        echo -n "按Enter键继续..."
        read -r
    done
}

# 主函数
main() {
    # 检查是否首次运行
    if [[ ! -f "venv/bin/activate" ]] || [[ ! -f "config.json" ]]; then
        init_environment
    fi
    
    # 预缓存状态信息
    cache_status
    
    # 显示主菜单
    show_menu
}

# 运行主函数
main "$@"
