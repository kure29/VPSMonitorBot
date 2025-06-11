#!/bin/bash
# VPS监控系统 v1.0 - 主管理菜单
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
    echo -e "${PURPLE}VPS库存监控系统 v1.0${NC}"
    echo -e "${CYAN}作者: kure29 | 网站: https://kure29.com${NC}"
    echo ""
}

# 检查Python环境
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        log_info "检测到Python版本: $python_version"
        
        # 修复版本比较逻辑
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
            return 0
        else
            log_warn "Python版本过低，需要3.7或更高版本，当前版本: $python_version"
            return 1
        fi
    else
        log_warn "未找到Python3，将在依赖安装阶段安装"
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
    if [[ -f "urls.json" ]] && command -v jq >/dev/null 2>&1; then
        jq 'length' urls.json 2>/dev/null || echo "0"
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
}

# 添加监控网址
add_url() {
    echo "添加监控网址"
    echo "=============="
    
    if ! activate_venv; then
        return 1
    fi
    
    echo -n "请输入商品名称: "
    read -r name
    
    if [[ -z "$name" ]]; then
        log_error "商品名称不能为空"
        return 1
    fi
    
    echo -n "请输入商品配置(可选): "
    read -r config
    
    echo -n "请输入监控URL: "
    read -r url
    
    if [[ -z "$url" ]]; then
        log_error "URL不能为空"
        return 1
    fi
    
    if [[ ! "$url" =~ ^https?:// ]]; then
        log_error "URL必须以http://或https://开头"
        return 1
    fi
    
    # 检查URL是否已存在
    if [[ -f "urls.json" ]] && command -v jq >/dev/null 2>&1; then
        if jq -e --arg url "$url" 'to_entries[] | select(.value.URL == $url)' urls.json >/dev/null 2>&1; then
            log_error "该URL已在监控列表中"
            return 1
        fi
    fi
    
    # 添加到JSON文件
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local id=$(date +%s)
    
    if [[ ! -f "urls.json" ]]; then
        echo '{}' > urls.json
    fi
    
    if command -v jq >/dev/null 2>&1; then
        jq --arg id "$id" --arg name "$name" --arg url "$url" --arg config "$config" --arg time "$timestamp" \
           '.[$id] = {"名称": $name, "URL": $url, "配置": $config, "created_at": $time}' urls.json > urls.json.tmp
        mv urls.json.tmp urls.json
        log_info "监控已添加: $name - $url"
    else
        log_error "需要安装jq工具来管理JSON文件"
        return 1
    fi
}

# 删除监控网址
delete_url() {
    echo "删除监控网址"
    echo "=============="
    
    if [[ ! -f "urls.json" ]]; then
        log_warn "没有监控的网址"
        return 1
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        log_error "需要安装jq工具来管理JSON文件"
        return 1
    fi
    
    echo "当前监控的网址："
    jq -r 'to_entries[] | "\(.key). \(.value.名称) - \(.value.URL)"' urls.json 2>/dev/null || {
        log_error "读取监控列表失败"
        return 1
    }
    
    echo -n "请输入要删除的编号: "
    read -r id
    
    if [[ -z "$id" ]]; then
        log_error "编号不能为空"
        return 1
    fi
    
    if jq -e --arg id "$id" 'has($id)' urls.json >/dev/null 2>&1; then
        jq --arg id "$id" 'del(.[$id])' urls.json > urls.json.tmp
        mv urls.json.tmp urls.json
        log_info "监控已删除"
    else
        log_error "找不到指定的监控项"
        return 1
    fi
}

# 显示所有监控网址
show_urls() {
    echo "所有监控网址"
    echo "=============="
    
    if [[ ! -f "urls.json" ]]; then
        log_warn "没有监控的网址"
        return 1
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        log_error "需要安装jq工具来查看JSON文件"
        return 1
    fi
    
    local count=$(jq 'length' urls.json 2>/dev/null || echo "0")
    if [[ "$count" == "0" ]]; then
        log_warn "没有监控的网址"
        return 1
    fi
    
    echo "共有 $count 个监控项："
    echo ""
    
    jq -r 'to_entries[] | "ID: \(.key)\n名称: \(.value.名称)\nURL: \(.value.URL)\n配置: \(.value.配置 // "无")\n创建时间: \(.value.created_at // "未知")\n"' urls.json 2>/dev/null || {
        log_error "读取监控列表失败"
        return 1
    }
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
    
    # 创建配置文件
    cat > config.json << EOF
{
    "bot_token": "$bot_token",
    "chat_id": "$chat_id",
    "check_interval": 300,
    "max_notifications": 3,
    "request_timeout": 30,
    "retry_delay": 60
}
EOF
    
    log_info "配置文件已保存"
    
    # 测试配置
    echo -n "是否测试Telegram连接? (y/N): "
    read -r test_conn
    
    if [[ "$test_conn" == "y" || "$test_conn" == "Y" ]]; then
        log_info "测试Telegram连接..."
        if activate_venv && python3 -c "
import requests
import json

config = json.load(open('config.json'))
resp = requests.get(f'https://api.telegram.org/bot{config[\"bot_token\"]}/getMe', timeout=10)
if resp.json().get('ok'):
    print('✅ Telegram Bot连接成功')
    # 发送测试消息
    test_resp = requests.post(f'https://api.telegram.org/bot{config[\"bot_token\"]}/sendMessage', 
                             json={'chat_id': config['chat_id'], 'text': '🤖 VPS监控系统测试消息'}, timeout=10)
    if test_resp.json().get('ok'):
        print('✅ 测试消息发送成功')
    else:
        print('❌ 测试消息发送失败，请检查Chat ID')
else:
    print('❌ Telegram Bot连接失败，请检查Token')
" 2>/dev/null; then
            log_info "Telegram配置测试完成"
        else
            log_error "Telegram配置测试失败"
        fi
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

# 主菜单
show_menu() {
    while true; do
        clear
        show_banner
        show_status
        
        echo " ============== VPS库存监控系统  ============== "
        echo "1. 添加监控网址"
        echo "2. 删除监控网址"
        echo "3. 显示所有监控网址"
        echo "4. 配置Telegram信息"
        echo "5. 启动监控"
        echo "6. 停止监控"
        echo "7. 查看监控状态"
        echo "8. 查看监控日志"
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
        
        echo -n "请选择操作 (0-8): "
        read -r choice
        
        case $choice in
            1)
                echo ""
                add_url
                ;;
            2)
                echo ""
                delete_url
                ;;
            3)
                echo ""
                show_urls
                ;;
            4)
                echo ""
                configure_telegram
                ;;
            5)
                echo ""
                start_monitor
                ;;
            6)
                echo ""
                stop_monitor
                ;;
            7)
                echo ""
                check_monitor_status
                ;;
            8)
                echo ""
                view_logs
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
