#!/bin/bash
# VPS监控系统 v2.0 - 主管理菜单
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
NC='\033[0m' # No Color

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

# 检查Python环境
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        log_info "检测到Python版本: $python_version"
        
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
        log_info "找到Python虚拟环境"
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
    log_info "虚拟环境创建成功"
}

# 激活虚拟环境
activate_venv() {
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        log_info "Python虚拟环境已激活"
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
        log_info "依赖安装完成"
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
}

# 检查配置文件
check_config() {
    if [[ -f "config.json" ]]; then
        if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
            log_info "配置文件格式正确"
            
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
            
            log_info "配置文件检查通过"
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
        log_info "发现数据库文件: vps_monitor.db"
        local size=$(du -h vps_monitor.db | cut -f1)
        log_info "数据库大小: $size"
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
    
    log_info "环境初始化完成"
}

# 获取监控状态
get_monitor_status() {
    local pids=$(pgrep -f "python3.*monitor.py" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "运行中"
        return 0
    else
        echo "已停止"
        return 1
    fi
}

# 获取进程信息
get_process_info() {
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

# 获取监控商品数量
get_monitor_count() {
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
    
    log_info "配置文件已保存"
    
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
    if get_monitor_status >/dev/null; then
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
        log_info "监控程序启动成功 (PID: $pid)"
        log_info "日志文件: monitor.log"
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
        
        log_info "监控程序已停止"
    else
        log_warn "监控程序未运行"
    fi
}

# 查看监控状态
check_monitor_status() {
    echo "监控状态"
    echo "========"
    
    local status=$(get_monitor_status)
    local process_info=$(get_process_info)
    local monitor_count=$(get_monitor_count)
    
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
    
    conn.close()
except Exception as e:
    print(f'获取统计失败: {e}')
" 2>&1
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
    echo -n "请选择 (1-4): "
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
    echo -n "请选择操作 (1-5): "
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
        log_info "数据库备份成功: $backup_file"
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
        echo "7. 从旧版本迁移数据"
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
        echo "===================="
        
        echo -n "请选择操作 (0-7): "
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
    
    # 显示主菜单
    show_menu
}

# 运行主函数
main "$@"
