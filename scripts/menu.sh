#!/bin/bash
# VPS监控系统 v3.1 - 快速修复版
# 作者: kure29
# 网站: https://kure29.com

# 移除严格模式，避免未定义变量错误
set +e

# 自动切换到项目根目录
cd "$(dirname "$0")/.."

# 颜色定义（必须在最前面）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# 验证项目目录
if [[ ! -f "requirements.txt" || ! -d "src" ]]; then
    echo -e "${RED}[ERROR]${NC} 无法找到项目根目录"
    echo -e "${RED}[ERROR]${NC} 当前路径: $(pwd)"
    echo -e "${RED}[ERROR]${NC} 请确保在VPS监控项目中运行此脚本"
    exit 1
fi

echo -e "${GREEN}[INFO]${NC} 项目根目录: $(pwd)"

# 全局变量
MONITOR_LOG="monitor.log"
DATABASE_FILE="vps_monitor.db"
CONFIG_FILE="config.json"
VENV_DIR="venv"

# ====== 日志和输出函数 ======
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

# ====== 系统检查函数 ======
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local python_version
        python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
        
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)" 2>/dev/null; then
            log_debug "Python版本: $python_version"
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

check_venv() {
    if [[ -d "$VENV_DIR" && -f "$VENV_DIR/bin/activate" ]]; then
        log_debug "找到Python虚拟环境"
        return 0
    else
        log_debug "未找到Python虚拟环境"
        return 1
    fi
}

activate_venv() {
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        # shellcheck source=/dev/null
        source "$VENV_DIR/bin/activate" 2>/dev/null || {
            log_warn "虚拟环境激活失败"
            return 1
        }
        log_debug "Python虚拟环境已激活"
        return 0
    else
        log_debug "虚拟环境不存在"
        return 1
    fi
}

check_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        if python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
            log_debug "配置文件格式正确"
            
            # 检查关键配置
            local bot_token
            local chat_id
            bot_token=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('bot_token', ''))" 2>/dev/null || echo "")
            chat_id=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('chat_id', ''))" 2>/dev/null || echo "")
            
            if [[ "$bot_token" == "YOUR_TELEGRAM_BOT_TOKEN" || -z "$bot_token" ]]; then
                log_debug "需要配置bot_token"
                return 1
            fi
            
            if [[ "$chat_id" == "YOUR_TELEGRAM_CHAT_ID" || -z "$chat_id" ]]; then
                log_debug "需要配置chat_id"
                return 1
            fi
            
            log_debug "配置文件检查通过"
            return 0
        else
            log_error "配置文件格式错误"
            return 1
        fi
    else
        log_debug "配置文件不存在"
        return 1
    fi
}

# ====== 状态检测函数 ======
get_monitor_status() {
    local pids
    pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || echo "")
    
    if [[ -n "$pids" ]]; then
        echo "运行中"
        return 0
    else
        echo "已停止"
        return 1
    fi
}

get_process_info() {
    local pids
    pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || echo "")
    
    if [[ -n "$pids" ]]; then
        local info_parts=()
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                local runtime
                local memory
                runtime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ' || echo "unknown")
                memory=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.1fMB", $1/1024}' 2>/dev/null || echo "unknown")
                
                info_parts+=("PID=$pid(运行时间:$runtime,内存:$memory)")
            fi
        done
        
        if [[ ${#info_parts[@]} -gt 0 ]]; then
            printf '%s\n' "${info_parts[@]}"
        else
            echo "进程信息获取失败"
        fi
    else
        echo "无运行进程"
    fi
}

get_monitor_count() {
    # 如果数据库不存在，返回0
    if [[ ! -f "$DATABASE_FILE" ]]; then
        echo "0"
        return 0
    fi
    
    # 检查Python是否可用
    if ! command -v python3 >/dev/null 2>&1; then
        echo "0"
        return 0
    fi
    
    local count
    count=$(python3 -c "
import sqlite3
import sys
try:
    conn = sqlite3.connect('$DATABASE_FILE')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM monitor_items WHERE enabled = 1')
    result = cursor.fetchone()
    print(result[0] if result else 0)
    conn.close()
except Exception:
    print(0)
" 2>/dev/null || echo "0")
    
    # 验证返回值是数字
    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$count"
    else
        echo "0"
    fi
}

get_database_size() {
    if [[ -f "$DATABASE_FILE" ]]; then
        du -h "$DATABASE_FILE" 2>/dev/null | cut -f1 || echo "未知"
    else
        echo "不存在"
    fi
}

# ====== Banner和状态显示 ======
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
    echo -e "${PURPLE}VPS库存监控系统 v3.1 - 多用户智能监控版${NC}"
    echo -e "${CYAN}作者: kure29 | 网站: https://kure29.com${NC}"
    echo ""
}

show_status() {
    local status
    local process_info
    local monitor_count
    local db_size
    
    # 直接获取状态
    status=$(get_monitor_status)
    process_info=$(get_process_info)
    monitor_count=$(get_monitor_count)
    db_size=$(get_database_size)
    
    echo "========================================"
    if [[ "$status" == "运行中" ]]; then
        echo -e "监控状态: ${GREEN}$status${NC}"
        echo "进程信息: $process_info"
    else
        echo -e "监控状态: ${RED}$status${NC}"
    fi
    echo "监控商品数: $monitor_count"
    echo "数据库大小: $db_size"
    
    # 显示智能提示
    show_smart_hints "$status" "$monitor_count"
}

show_smart_hints() {
    local status="$1"
    local count="$2"
    
    echo ""
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo -e "${YELLOW}💡 提示: 请先配置Telegram信息${NC}"
    elif ! check_config >/dev/null 2>&1; then
        echo -e "${YELLOW}💡 提示: 配置文件需要更新${NC}"
    elif [[ "$status" == "已停止" ]]; then
        echo -e "${YELLOW}💡 提示: 监控未运行，建议启动监控${NC}"
    elif [[ "$count" == "0" ]]; then
        echo -e "${YELLOW}💡 提示: 尚未添加监控商品${NC}"
    else
        echo -e "${GREEN}💡 系统运行正常${NC}"
    fi
}

# ====== 环境初始化 ======
create_venv() {
    log_info "创建Python虚拟环境..."
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        log_success "虚拟环境创建成功"
        return 0
    else
        log_error "虚拟环境创建失败"
        return 1
    fi
}

install_dependencies() {
    log_info "安装Python依赖包..."
    if [[ -f "requirements.txt" ]]; then
        if pip install --upgrade pip >/dev/null 2>&1 && pip install -r requirements.txt >/dev/null 2>&1; then
            log_success "依赖安装完成"
            return 0
        else
            log_error "依赖安装失败"
            return 1
        fi
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
}

init_environment() {
    log_info "初始化环境..."
    
    # 检查Python
    if ! check_python; then
        log_error "Python环境检查失败"
        return 1
    fi
    
    # 检查并创建虚拟环境
    if ! check_venv; then
        log_info "创建虚拟环境..."
        if ! create_venv; then
            log_error "虚拟环境创建失败"
            return 1
        fi
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
        log_warn "请配置Telegram信息"
    fi
    
    log_success "环境初始化完成"
    return 0
}

# ====== Telegram配置 ======
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
    
    # 处理管理员ID
    local admin_ids_json="[]"
    if [[ -n "$admin_ids" ]]; then
        # 将逗号分隔的ID转换为JSON数组
        admin_ids_json="[$(echo "$admin_ids" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/' | sed 's/""//g')]"
    fi
    
    # 创建配置文件
    cat > "$CONFIG_FILE" << EOF
{
    "bot_token": "$bot_token",
    "chat_id": "$chat_id",
    "channel_id": "$channel_id",
    "admin_ids": $admin_ids_json,
    "check_interval": 180,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600,
    "request_timeout": 30,
    "retry_delay": 60,
    "items_per_page": 10,
    "debug": false,
    "log_level": "INFO",
    "enable_selenium": true,
    "enable_api_discovery": true,
    "enable_visual_comparison": false,
    "confidence_threshold": 0.6,
    "daily_add_limit": 50,
    "enable_vendor_optimization": true
}
EOF
    
    log_success "配置文件已保存"
    
    # 测试配置
    echo -n "是否测试Telegram连接? (y/N): "
    read -r test_conn
    
    if [[ "$test_conn" == "y" || "$test_conn" == "Y" ]]; then
        test_telegram_connection
    fi
}

test_telegram_connection() {
    log_info "测试Telegram连接..."
    
    if activate_venv; then
        python3 -c "
import requests
import json
import sys

try:
    with open('$CONFIG_FILE') as f:
        config = json.load(f)
    
    # 测试Bot连接
    resp = requests.get(
        f'https://api.telegram.org/bot{config[\"bot_token\"]}/getMe', 
        timeout=10
    )
    
    if resp.json().get('ok'):
        print('✅ Telegram Bot连接成功')
        
        # 发送测试消息
        test_resp = requests.post(
            f'https://api.telegram.org/bot{config[\"bot_token\"]}/sendMessage', 
            json={
                'chat_id': config['chat_id'], 
                'text': '🤖 VPS监控系统 v3.1 测试消息 - 连接正常'
            }, 
            timeout=10
        )
        
        if test_resp.json().get('ok'):
            print('✅ 测试消息发送成功')
        else:
            print('❌ 测试消息发送失败，请检查Chat ID')
            print(f'错误: {test_resp.json()}')
    else:
        print('❌ Telegram Bot连接失败，请检查Token')
        print(f'错误: {resp.json()}')
        
except requests.exceptions.RequestException as e:
    print(f'❌ 网络连接失败: {e}')
except Exception as e:
    print(f'❌ 测试失败: {e}')
" 2>&1
    else
        log_error "无法激活虚拟环境"
    fi
}

# ====== 监控控制 ======
start_monitor() {
    echo "启动监控"
    echo "========"
    
    # 检查是否已在运行
    if [[ "$(get_monitor_status)" == "运行中" ]]; then
        log_warn "监控程序已在运行中"
        return 1
    fi
    
    # 检查配置
    if ! check_config; then
        log_error "请先配置Telegram信息"
        return 1
    fi
    
    # 检查监控脚本
    if [[ ! -f "src/monitor.py" ]]; then
        log_error "监控脚本不存在: src/monitor.py"
        return 1
    fi
    
    # 激活虚拟环境
    if ! activate_venv; then
        log_error "无法激活虚拟环境"
        return 1
    fi
    
    log_info "启动监控程序..."
    
    # 启动监控（后台运行）
    nohup python3 src/monitor.py > "$MONITOR_LOG" 2>&1 &
    local pid=$!
    
    # 等待并检查是否成功启动
    sleep 3
    
    if kill -0 "$pid" 2>/dev/null; then
        log_success "监控程序启动成功 (PID: $pid)"
        log_info "日志文件: $MONITOR_LOG"
        
        # 显示启动后的状态
        echo ""
        echo "当前状态:"
        show_status
    else
        log_error "监控程序启动失败，请查看日志文件"
        if [[ -f "$MONITOR_LOG" ]]; then
            echo ""
            echo "最近的错误日志:"
            tail -n 10 "$MONITOR_LOG" | grep -i "error\|exception" || echo "没有发现明显错误"
        fi
        return 1
    fi
}

stop_monitor() {
    echo "停止监控"
    echo "========"
    
    local pids
    pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || echo "")
    
    if [[ -n "$pids" ]]; then
        log_info "停止监控程序..."
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                log_info "已发送停止信号给进程 $pid"
            fi
        done
        
        # 等待进程停止
        sleep 3
        
        # 检查是否还在运行
        local remaining_pids
        remaining_pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || echo "")
        if [[ -n "$remaining_pids" ]]; then
            log_warn "强制停止残留进程..."
            for pid in $remaining_pids; do
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid"
                    log_info "强制停止进程 $pid"
                fi
            done
        fi
        
        log_success "监控程序已停止"
        
        # 显示停止后的状态
        echo ""
        echo "当前状态:"
        show_status
    else
        log_warn "监控程序未运行"
    fi
}

# ====== 状态和日志查看 ======
check_monitor_status() {
    echo "监控状态详情"
    echo "============"
    
    local status
    local process_info
    local monitor_count
    
    status=$(get_monitor_status)
    process_info=$(get_process_info)
    monitor_count=$(get_monitor_count)
    
    if [[ "$status" == "运行中" ]]; then
        echo -e "状态: ${GREEN}$status${NC}"
        echo "进程信息: $process_info"
        echo "监控商品数: $monitor_count"
        
        # 显示最近日志
        if [[ -f "$MONITOR_LOG" ]]; then
            echo ""
            echo "最近日志 (最后10行):"
            echo "==================="
            tail -n 10 "$MONITOR_LOG"
        fi
    else
        echo -e "状态: ${RED}$status${NC}"
        echo "监控商品数: $monitor_count"
        
        if [[ -f "$MONITOR_LOG" ]]; then
            echo ""
            echo "最后的错误日志:"
            echo "=============="
            tail -n 10 "$MONITOR_LOG" | grep -i "error\|exception\|fail" || echo "没有发现错误"
        fi
    fi
    
    # 显示数据库统计
    show_database_stats
}

show_database_stats() {
    if [[ -f "$DATABASE_FILE" ]] && activate_venv; then
        echo ""
        echo "数据库统计:"
        echo "=========="
        python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('$DATABASE_FILE')
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
    tables = [row[0] for row in cursor.fetchall()]
    
    if 'check_history' in tables:
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
    
    if 'monitor_items' in tables:
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

view_logs() {
    echo "监控日志"
    echo "========"
    
    if [[ ! -f "$MONITOR_LOG" ]]; then
        log_warn "日志文件不存在"
        return 1
    fi
    
    echo "日志文件: $MONITOR_LOG"
    echo "文件大小: $(du -h "$MONITOR_LOG" | cut -f1)"
    echo ""
    
    echo "选择查看方式："
    echo "1. 查看最新50行"
    echo "2. 查看全部日志"
    echo "3. 实时监控日志"
    echo "4. 查看错误日志"
    echo -n "请选择 (1-4): "
    read -r choice
    
    case $choice in
        1)
            echo "最新50行日志:"
            echo "============="
            tail -n 50 "$MONITOR_LOG"
            ;;
        2)
            echo "全部日志:"
            echo "========"
            less "$MONITOR_LOG"
            ;;
        3)
            echo "实时监控日志 (按Ctrl+C退出):"
            echo "=========================="
            tail -f "$MONITOR_LOG"
            ;;
        4)
            echo "错误日志:"
            echo "========"
            grep -i "error\|exception\|fail" "$MONITOR_LOG" | tail -n 20 || echo "没有发现错误日志"
            ;;
        *)
            log_error "无效选择"
            ;;
    esac
}

# ====== 系统健康检查 ======
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
    
    # 检查关键文件
    if [[ -f "src/monitor.py" ]]; then
        echo "✅ 监控脚本存在"
    else
        echo "❌ 监控脚本缺失"
        ((issues++))
    fi
    
    # 检查数据库
    if [[ -f "$DATABASE_FILE" ]]; then
        echo "✅ 数据库文件存在"
    else
        echo "⚠️  数据库文件不存在（首次运行时创建）"
    fi
    
    # 检查网络连接
    echo ""
    echo "🌐 检查网络连接..."
    if curl -s --connect-timeout 5 https://api.telegram.org >/dev/null 2>&1; then
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

# ====== 主菜单 ======
show_menu() {
    while true; do
        clear
        show_banner
        show_status
        
        echo " ============== VPS库存监控系统 v3.1 ============== "
        echo "1. 配置Telegram信息"
        echo "2. 启动监控"
        echo "3. 停止监控"
        echo "4. 查看监控状态"
        echo "5. 查看监控日志"
        echo "6. 系统健康检查"
        echo "0. 退出"
        echo "================== 快速状态 =================="
        
        # 显示当前状态摘要
        local status
        local monitor_count
        local db_size
        
        status=$(get_monitor_status)
        monitor_count=$(get_monitor_count)
        db_size=$(get_database_size)
        
        if [[ "$status" == "运行中" ]]; then
            local pids
            pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null | head -1)
            echo -e "监控状态: ${GREEN}运行中${NC} (PID: ${pids:-unknown})"
        else
            echo -e "监控状态: ${RED}未运行${NC}"
        fi
        
        echo -e "监控商品: ${WHITE}$monitor_count${NC} 个"
        echo -e "数据库: ${WHITE}$db_size${NC}"
        echo "======================================"
        
        echo -n "请选择操作 (0-6): "
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
                health_check
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

# ====== 主函数 ======
main() {
    # 显示项目信息
    log_debug "脚本位置: $(dirname "$0")"
    log_debug "项目根目录: $(pwd)"
    
    # 检查是否首次运行
    if [[ ! -f "$VENV_DIR/bin/activate" ]] || [[ ! -f "$CONFIG_FILE" ]]; then
        log_info "检测到首次运行，开始初始化环境..."
        if ! init_environment; then
            log_error "环境初始化失败"
            exit 1
        fi
    fi
    
    # 显示主菜单
    show_menu
}

# 执行主函数
main "$@"
