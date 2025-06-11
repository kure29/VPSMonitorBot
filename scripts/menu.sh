#!/bin/bash

# =========================================
# 作者: kure29
# 日期: 2025年6月
# 网站：maibi.de
# 版本：V1.0
# 描述: VPS库存监控系统
# =========================================

# 颜色定义
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# 配置文件
readonly CONFIG_FILE="config.json"
readonly URLS_FILE="urls.json"
readonly MONITOR_LOG="monitor.log"
readonly INIT_MARK=".initialized"
readonly VENV_DIR="venv"
readonly REQUIREMENTS_FILE="requirements.txt"
readonly MONITOR_SCRIPT="monitor.py"

# 全局变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 错误处理
set -euo pipefail
trap 'handle_error $? $LINENO' ERR

handle_error() {
    local exit_code=$1
    local line_no=$2
    echo -e "${RED}错误：脚本在第 $line_no 行发生错误，退出码 $exit_code${NC}" >&2
    exit $exit_code
}

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
    [[ "${DEBUG:-0}" == "1" ]] && echo -e "${CYAN}[DEBUG]${NC} $1"
}

# 系统检测函数
detect_os() {
    if [[ -f "/etc/debian_version" ]]; then
        echo "debian"
    elif [[ -f "/etc/redhat-release" ]]; then
        echo "redhat"
    elif [[ -f "/etc/arch-release" ]]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

# 包管理器操作
install_packages() {
    local packages=("$@")
    local os_type
    os_type=$(detect_os)
    
    log_info "检测到系统类型: $os_type"
    log_info "安装软件包: ${packages[*]}"
    
    case $os_type in
        debian)
            apt-get update -qq
            apt-get install -y "${packages[@]}"
            ;;
        redhat)
            yum install -y "${packages[@]}"
            ;;
        arch)
            pacman -S --noconfirm "${packages[@]}"
            ;;
        *)
            log_error "不支持的操作系统，请手动安装: ${packages[*]}"
            return 1
            ;;
    esac
}

# 检查必需的系统工具
check_system_tools() {
    local tools=("curl" "jq" "python3")
    local missing_tools=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_warn "缺少系统工具: ${missing_tools[*]}"
        log_info "正在安装缺少的工具..."
        
        case $(detect_os) in
            debian)
                install_packages python3 python3-pip python3-venv curl jq
                ;;
            redhat)
                install_packages python3 python3-pip python3-venv curl jq
                ;;
            arch)
                install_packages python python-pip curl jq
                ;;
        esac
    fi
}

# 检查监控状态的增强函数
check_monitor_status() {
    local pid
    if pid=$(pgrep -f "python3.*$MONITOR_SCRIPT" 2>/dev/null); then
        local uptime cpu_usage memory_usage
        uptime=$(ps -o etime= -p "$pid" | tr -d ' ')
        cpu_usage=$(ps -o %cpu= -p "$pid" | tr -d ' ')
        memory_usage=$(ps -o rss= -p "$pid" | awk '{printf "%.1fMB", $1/1024}')
        
        echo -e "${GREEN}运行中${NC} (PID: ${BLUE}$pid${NC}, 运行时间: ${CYAN}$uptime${NC})"
        echo -e "  CPU: ${YELLOW}$cpu_usage%${NC}, 内存: ${YELLOW}$memory_usage${NC}"
        return 0
    else
        echo -e "${RED}未运行${NC}"
        return 1
    fi
}

# 显示详细的监控信息
show_monitor_details() {
    local pid
    if pid=$(pgrep -f "python3.*$MONITOR_SCRIPT" 2>/dev/null); then
        echo -e "\n${BLUE}=== 监控进程详情 ===${NC}"
        printf "%-15s %s\n" "进程ID:" "$pid"
        printf "%-15s %s\n" "运行时间:" "$(ps -o etime= -p "$pid" | tr -d ' ')"
        printf "%-15s %s\n" "内存使用:" "$(ps -o rss= -p "$pid" | awk '{printf "%.1fMB", $1/1024}')"
        printf "%-15s %s\n" "CPU使用率:" "$(ps -o %cpu= -p "$pid" | tr -d ' ')%"
        
        if [[ -f "$MONITOR_LOG" ]]; then
            echo -e "\n${BLUE}=== 最近日志 (最后5行) ===${NC}"
            tail -n 5 "$MONITOR_LOG" | sed 's/^/  /'
        fi
        
        if [[ -f "$URLS_FILE" ]] && command -v jq &> /dev/null; then
            local url_count
            url_count=$(jq 'length' "$URLS_FILE" 2>/dev/null || echo "0")
            echo -e "\n${BLUE}=== 监控统计 ===${NC}"
            printf "%-15s %s\n" "监控商品数:" "$url_count"
            
            # 显示最后检查时间
            if [[ -s "$MONITOR_LOG" ]]; then
                local last_check
                last_check=$(tail -n 1 "$MONITOR_LOG" | cut -d' ' -f1-2 2>/dev/null || echo "未知")
                printf "%-15s %s\n" "最后检查:" "$last_check"
            fi
        fi
    else
        log_warn "监控程序未运行"
    fi
}

# 增强的启动监控函数
start_monitor() {
    # 检查配置文件
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "未找到配置文件，请先配置Telegram信息"
        return 1
    fi
    
    # 验证配置文件格式
    if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
        log_error "配置文件格式错误，请重新配置"
        return 1
    fi
    
    # 检查监控文件
    if [[ ! -s "$URLS_FILE" ]]; then
        log_error "未找到监控商品，请先添加监控商品"
        return 1
    fi
    
    # 检查是否已在运行
    if pgrep -f "python3.*$MONITOR_SCRIPT" &> /dev/null; then
        log_warn "监控程序已在运行中"
        show_monitor_details
        return 0
    fi
    
    # 检查监控脚本
    if [[ ! -f "$MONITOR_SCRIPT" ]]; then
        log_error "未找到监控脚本 $MONITOR_SCRIPT"
        return 1
    fi
    
    log_info "正在启动监控程序..."
    
    # 激活虚拟环境并启动
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        source "$VENV_DIR/bin/activate"
        nohup python3 "$MONITOR_SCRIPT" >> "$MONITOR_LOG" 2>&1 &
        local start_pid=$!
        sleep 3
        
        # 验证启动是否成功
        if kill -0 "$start_pid" 2>/dev/null && pgrep -f "python3.*$MONITOR_SCRIPT" &> /dev/null; then
            log_info "监控程序启动成功"
            show_monitor_details
        else
            log_error "监控程序启动失败"
            if [[ -f "$MONITOR_LOG" ]]; then
                echo -e "${YELLOW}最近的错误日志：${NC}"
                tail -n 5 "$MONITOR_LOG" | sed 's/^/  /'
            fi
            return 1
        fi
    else
        log_error "虚拟环境未找到，请重新初始化"
        return 1
    fi
}

# 增强的停止监控函数
stop_monitor() {
    local pids
    mapfile -t pids < <(pgrep -f "python3.*$MONITOR_SCRIPT" 2>/dev/null || true)
    
    if [[ ${#pids[@]} -eq 0 ]]; then
        log_warn "没有运行中的监控程序"
        return 0
    fi
    
    log_info "发现 ${#pids[@]} 个监控进程，正在停止..."
    
    for pid in "${pids[@]}"; do
        log_info "停止进程 $pid..."
        if kill "$pid" 2>/dev/null; then
            # 等待进程正常退出
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
            done
            
            # 如果进程仍在运行，强制终止
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "进程 $pid 未能正常停止，强制终止..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            log_info "进程 $pid 已停止"
        else
            log_warn "无法停止进程 $pid"
        fi
    done
    
    # 最终检查
    if ! pgrep -f "python3.*$MONITOR_SCRIPT" &> /dev/null; then
        log_info "所有监控程序已成功停止"
    else
        log_error "部分监控程序可能仍在运行"
    fi
}

# 增强的添加URL函数
add_url() {
    local product_name product_config product_url
    
    echo -e "\n${YELLOW}=== 添加监控商品 ===${NC}"
    
    # 输入产品名称
    while true; do
        echo -e "${YELLOW}请输入产品名称: ${NC}"
        read -r product_name
        if [[ -n "$product_name" ]]; then
            break
        else
            log_error "产品名称不能为空，请重新输入"
        fi
    done
    
    # 输入产品配置（可选）
    echo -e "${YELLOW}请输入产品配置（可选，直接回车跳过）: ${NC}"
    read -r product_config
    
    # 输入产品URL
    while true; do
        echo -e "${YELLOW}请输入产品URL: ${NC}"
        read -r product_url
        
        if [[ -z "$product_url" ]]; then
            log_error "URL不能为空，请重新输入"
            continue
        fi
        
        if ! [[ "$product_url" =~ ^https?:// ]]; then
            log_error "无效的URL格式，必须以 http:// 或 https:// 开头"
            continue
        fi
        
        # 检查URL是否已存在
        if [[ -f "$URLS_FILE" ]] && jq -e "to_entries[] | select(.value.URL == \"$product_url\")" "$URLS_FILE" &>/dev/null; then
            log_error "该URL已存在于监控列表中"
            continue
        fi
        
        # 验证URL可访问性（可选）
        echo -e "${CYAN}是否验证URL可访问性? [y/N] ${NC}"
        read -r verify_choice
        if [[ "$verify_choice" =~ ^[Yy]$ ]]; then
            echo -e "${CYAN}正在验证URL...${NC}"
            if curl -s --head --max-time 10 "$product_url" | head -n 1 | grep -q "HTTP/[12].[01] [23].."; then
                log_info "URL验证成功"
            else
                log_warn "URL验证失败，但仍可添加"
            fi
        fi
        
        break
    done
    
    # 确保文件存在且格式正确
    if [[ ! -f "$URLS_FILE" ]] || [[ ! -s "$URLS_FILE" ]]; then
        echo '{}' > "$URLS_FILE"
    fi
    
    # 验证JSON格式
    if ! jq empty "$URLS_FILE" 2>/dev/null; then
        log_warn "数据文件格式错误，重新创建"
        echo '{}' > "$URLS_FILE"
    fi
    
    # 生成唯一ID
    local id
    id=$(date +%s%N | cut -b1-13)  # 更精确的时间戳
    
    # 构建JSON数据
    local json_data
    json_data=$(jq -n \
        --arg id "$id" \
        --arg name "$product_name" \
        --arg url "$product_url" \
        --arg config "$product_config" \
        --arg created "$(date -Iseconds)" \
        '{($id): {"名称": $name, "URL": $url, "配置": $config, "created_at": $created, "status": null, "notification_count": 0}}')
    
    # 合并数据
    if jq -s '.[0] * .[1]' "$URLS_FILE" <(echo "$json_data") > "$URLS_FILE.tmp"; then
        mv "$URLS_FILE.tmp" "$URLS_FILE"
        
        echo -e "\n${GREEN}✅ 添加成功${NC}"
        echo -e "${BLUE}产品名称:${NC} $product_name"
        echo -e "${BLUE}产品URL:${NC} $product_url"
        [[ -n "$product_config" ]] && echo -e "${BLUE}产品配置:${NC} $product_config"
        
        # 询问是否立即测试
        echo -e "\n${CYAN}是否立即测试该URL的监控? [Y/n] ${NC}"
        read -r test_choice
        if [[ ! "$test_choice" =~ ^[Nn]$ ]]; then
            test_single_url "$product_url"
        fi
    else
        log_error "添加失败，请检查数据格式"
        [[ -f "$URLS_FILE.tmp" ]] && rm -f "$URLS_FILE.tmp"
        return 1
    fi
}

# 测试单个URL
test_single_url() {
    local url="$1"
    
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        log_error "虚拟环境未初始化"
        return 1
    fi
    
    echo -e "${CYAN}正在测试URL: $url${NC}"
    
    # 创建临时测试脚本
    cat > test_url.py << 'EOF'
import sys
import asyncio
import cloudscraper
import urllib.parse
import random

async def test_url(url):
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print("正在获取页面...")
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            content_length = len(response.text)
            print(f"✅ 页面获取成功")
            print(f"📊 状态码: {response.status_code}")
            print(f"📄 内容长度: {content_length} 字符")
            
            # 简单的库存状态检测
            content = response.text.lower()
            out_of_stock = any(keyword in content for keyword in [
                'sold out', 'out of stock', '缺货', '售罄', 'unavailable'
            ])
            in_stock = any(keyword in content for keyword in [
                'add to cart', 'buy now', '立即购买', 'in stock', 'available'
            ])
            
            if out_of_stock:
                print("📦 初步判断: 可能无货")
            elif in_stock:
                print("📦 初步判断: 可能有货")
            else:
                print("📦 初步判断: 无法确定库存状态")
                
        else:
            print(f"❌ 页面获取失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(test_url(sys.argv[1]))
EOF
    
    # 运行测试
    source "$VENV_DIR/bin/activate"
    python3 test_url.py "$url"
    rm -f test_url.py
}

# 增强的删除URL函数
delete_url() {
    if [[ ! -s "$URLS_FILE" ]]; then
        log_warn "监控列表为空"
        return 0
    fi
    
    local url_count
    url_count=$(jq 'length' "$URLS_FILE" 2>/dev/null || echo "0")
    
    if [[ "$url_count" -eq 0 ]]; then
        log_warn "监控列表为空"
        return 0
    fi
    
    echo -e "\n${YELLOW}当前监控列表：${NC}"
    show_urls_with_numbers
    
    echo -e "\n${YELLOW}请输入要删除的序号 (1-$url_count): ${NC}"
    read -r choice
    
    # 验证输入
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt "$url_count" ]]; then
        log_error "无效的序号"
        return 1
    fi
    
    # 获取对应的ID
    local target_id
    target_id=$(jq -r "to_entries | sort_by(.value.created_at // \"0\") | .[$((choice-1))].key" "$URLS_FILE")
    
    if [[ -z "$target_id" ]] || [[ "$target_id" == "null" ]]; then
        log_error "未找到对应的监控项"
        return 1
    fi
    
    # 显示要删除的项目信息
    local name url config
    name=$(jq -r ".\"$target_id\".名称" "$URLS_FILE")
    url=$(jq -r ".\"$target_id\".URL" "$URLS_FILE")
    config=$(jq -r ".\"$target_id\".配置" "$URLS_FILE")
    
    echo -e "\n${RED}确认删除以下监控项：${NC}"
    echo -e "${BLUE}产品：${NC}$name"
    echo -e "${BLUE}网址：${NC}$url"
    [[ "$config" != "null" && -n "$config" ]] && echo -e "${BLUE}配置：${NC}$config"
    
    echo -e "\n${YELLOW}确认删除? [y/N] ${NC}"
    read -r confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        # 删除指定ID的数据
        if jq "del(.\"$target_id\")" "$URLS_FILE" > "$URLS_FILE.tmp"; then
            mv "$URLS_FILE.tmp" "$URLS_FILE"
            log_info "删除成功"
        else
            log_error "删除失败"
            [[ -f "$URLS_FILE.tmp" ]] && rm -f "$URLS_FILE.tmp"
            return 1
        fi
    else
        log_info "已取消删除"
    fi
}

# 显示带编号的URL列表
show_urls_with_numbers() {
    if [[ ! -s "$URLS_FILE" ]] || [[ "$(jq 'length' "$URLS_FILE" 2>/dev/null || echo 0)" == "0" ]]; then
        log_warn "监控列表为空"
        return 0
    fi
    
    local counter=1
    jq -r 'to_entries | sort_by(.value.created_at // "0") | .[] | @base64' "$URLS_FILE" | while read -r item; do
        local decoded
        decoded=$(echo "$item" | base64 -d)
        local name url config status created
        
        name=$(echo "$decoded" | jq -r '.value.名称')
        url=$(echo "$decoded" | jq -r '.value.URL')
        config=$(echo "$decoded" | jq -r '.value.配置 // ""')
        status=$(echo "$decoded" | jq -r '.value.status // null')
        created=$(echo "$decoded" | jq -r '.value.created_at // ""')
        
        echo -e "\n${CYAN}[$counter]${NC}"
        echo -e "${BLUE}  产品：${NC}$name"
        echo -e "${BLUE}  链接：${NC}$url"
        [[ -n "$config" && "$config" != "null" ]] && echo -e "${BLUE}  配置：${NC}$config"
        
        # 显示状态
        case "$status" in
            "true") echo -e "${BLUE}  状态：${GREEN}有货${NC}" ;;
            "false") echo -e "${BLUE}  状态：${RED}无货${NC}" ;;
            *) echo -e "${BLUE}  状态：${YELLOW}未检查${NC}" ;;
        esac
        
        # 显示创建时间
        if [[ -n "$created" && "$created" != "null" ]]; then
            local formatted_time
            formatted_time=$(date -d "$created" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "$created")
            echo -e "${BLUE}  创建：${NC}$formatted_time"
        fi
        
        echo -e "${GRAY}  ----------------------------------------${NC}"
        ((counter++))
    done
}

# 显示所有URL（保持原有格式兼容性）
show_urls() {
    if [[ ! -s "$URLS_FILE" ]] || [[ "$(jq 'length' "$URLS_FILE" 2>/dev/null || echo 0)" == "0" ]]; then
        log_warn "监控列表为空"
        return 0
    fi
    
    echo -e "\n${YELLOW}当前监控列表：${NC}"
    jq -r 'to_entries[] | "\n\(.key):\n📦 产品：\(.value.名称)\n🔗 链接：\(.value.URL)\(if .value.配置 and .value.配置 != "" then "\n⚙️ 配置：\(.value.配置)" else "" end)\n----------------------------------------"' "$URLS_FILE"
}

# 增强的配置Telegram函数
configure_telegram() {
    echo -e "\n${YELLOW}=== 配置Telegram信息 ===${NC}"
    
    # 显示帮助信息
    echo -e "${CYAN}ℹ️  获取Bot Token和Chat ID的方法：${NC}"
    echo -e "   1. 创建Bot：向 @BotFather 发送 /newbot"
    echo -e "   2. 获取Chat ID：向 @userinfobot 发送 /start"
    echo -e "   3. 测试Bot：向你的Bot发送任意消息激活对话\n"
    
    local bot_token chat_id interval
    
    # 输入Bot Token
    while true; do
        echo -e "${YELLOW}请输入Telegram Bot Token: ${NC}"
        read -r bot_token
        if [[ -n "$bot_token" ]] && [[ "$bot_token" =~ ^[0-9]+:.+ ]]; then
            break
        else
            log_error "无效的Bot Token格式，请重新输入"
        fi
    done
    
    # 输入Chat ID
    while true; do
        echo -e "${YELLOW}请输入Telegram Chat ID: ${NC}"
        read -r chat_id
        if [[ -n "$chat_id" ]] && [[ "$chat_id" =~ ^-?[0-9]+$ ]]; then
            break
        else
            log_error "无效的Chat ID格式，请输入数字"
        fi
    done
    
    # 输入检查间隔
    while true; do
        echo -e "${YELLOW}请输入检查间隔(秒，默认300，建议不少于60): ${NC}"
        read -r interval
        interval=${interval:-300}
        if [[ "$interval" =~ ^[0-9]+$ ]] && [[ "$interval" -ge 60 ]]; then
            break
        else
            log_error "检查间隔必须是大于等于60的数字"
        fi
    done
    
    # 测试配置
    echo -e "\n${CYAN}是否测试Telegram配置? [Y/n] ${NC}"
    read -r test_choice
    if [[ ! "$test_choice" =~ ^[Nn]$ ]]; then
        echo -e "${CYAN}正在测试Telegram连接...${NC}"
        local test_result
        test_result=$(curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" \
            -d "chat_id=$chat_id" \
            -d "text=🧪 测试消息：VPS监控机器人配置成功！")
        
        if echo "$test_result" | jq -e '.ok' &>/dev/null; then
            log_info "Telegram测试成功！"
        else
            log_error "Telegram测试失败，请检查Token和Chat ID"
            echo -e "${YELLOW}错误信息：${NC}$(echo "$test_result" | jq -r '.description // "未知错误"')"
            
            echo -e "\n${YELLOW}是否仍要保存配置? [y/N] ${NC}"
            read -r save_choice
            if [[ ! "$save_choice" =~ ^[Yy]$ ]]; then
                log_info "已取消保存配置"
                return 1
            fi
        fi
    fi
    
    # 保存配置
    local config_json
    config_json=$(jq -n \
        --arg token "$bot_token" \
        --arg chat "$chat_id" \
        --argjson interval "$interval" \
        '{
            "bot_token": $token,
            "chat_id": $chat,
            "check_interval": $interval,
            "max_notifications": 3,
            "request_timeout": 30
        }')
    
    if echo "$config_json" > "$CONFIG_FILE"; then
        log_info "配置已保存"
        
        # 显示配置摘要
        echo -e "\n${BLUE}=== 配置摘要 ===${NC}"
        printf "%-15s %s\n" "Bot Token:" "${bot_token:0:10}...${bot_token: -10}"
        printf "%-15s %s\n" "Chat ID:" "$chat_id"
        printf "%-15s %s秒\n" "检查间隔:" "$interval"
    else
        log_error "配置保存失败"
        return 1
    fi
}

# 查看日志的增强函数
view_log() {
    if [[ ! -f "$MONITOR_LOG" ]]; then
        log_warn "日志文件不存在"
        return 0
    fi
    
    local log_size
    log_size=$(stat -f%z "$MONITOR_LOG" 2>/dev/null || stat -c%s "$MONITOR_LOG" 2>/dev/null || echo "0")
    
    echo -e "\n${BLUE}=== 监控日志信息 ===${NC}"
    printf "%-15s %s\n" "日志文件:" "$MONITOR_LOG"
    printf "%-15s %s\n" "文件大小:" "$(numfmt --to=iec "$log_size" 2>/dev/null || echo "${log_size} bytes")"
    printf "%-15s %s\n" "最后修改:" "$(date -r "$MONITOR_LOG" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "未知")"
    
    echo -e "\n${YELLOW}选择查看方式：${NC}"
    echo "1) 查看最后50行"
    echo "2) 查看最后100行"
    echo "3) 实时查看(tail -f)"
    echo "4) 搜索关键词"
    echo "5) 返回主菜单"
    
    echo -e "\n${YELLOW}请选择 (1-5): ${NC}"
    read -r log_choice
    
    case $log_choice in
        1)
            echo -e "\n${BLUE}=== 最后50行日志 ===${NC}"
            tail -n 50 "$MONITOR_LOG" | sed 's/^/  /'
            ;;
        2)
            echo -e "\n${BLUE}=== 最后100行日志 ===${NC}"
            tail -n 100 "$MONITOR_LOG" | sed 's/^/  /'
            ;;
        3)
            echo -e "\n${BLUE}=== 实时日志 (按Ctrl+C退出) ===${NC}"
            tail -f "$MONITOR_LOG"
            ;;
        4)
            echo -e "${YELLOW}请输入搜索关键词: ${NC}"
            read -r keyword
            if [[ -n "$keyword" ]]; then
                echo -e "\n${BLUE}=== 搜索结果: '$keyword' ===${NC}"
                grep -i --color=auto "$keyword" "$MONITOR_LOG" | tail -n 20 | sed 's/^/  /'
            fi
            ;;
        5|*)
            return 0
            ;;
    esac
}

# 虚拟环境管理的增强函数
setup_python_environment() {
    log_info "正在设置Python环境..."
    
    # 检查Python版本
    local python_version
    if command -v python3 &> /dev/null; then
        python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        log_info "检测到Python版本: $python_version"
        
        # 检查Python版本是否满足要求
        if [[ $(echo "$python_version 3.7" | awk '{print ($1 >= $2)}') -eq 0 ]]; then
            log_warn "Python版本过低，建议使用3.7+版本"
        fi
    else
        log_error "未找到Python3，正在安装..."
        check_system_tools
    fi
    
    # 创建虚拟环境
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "创建Python虚拟环境..."
        
        if python3 -m venv "$VENV_DIR"; then
            log_info "虚拟环境创建成功"
        else
            log_error "虚拟环境创建失败，尝试安装python3-venv..."
            install_packages python3-venv
            python3 -m venv "$VENV_DIR" || {
                log_error "虚拟环境创建失败"
                return 1
            }
        fi
    fi
    
    # 激活虚拟环境并升级pip
    source "$VENV_DIR/bin/activate"
    log_info "升级pip..."
    python3 -m pip install --upgrade pip -q
    
    # 安装依赖
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        log_info "安装Python依赖包..."
        pip install -r "$REQUIREMENTS_FILE" -q
        
        # 验证关键包是否安装成功
        local key_packages=("telegram" "cloudscraper" "aiofiles")
        for package in "${key_packages[@]}"; do
            if python3 -c "import $package" 2>/dev/null; then
                log_debug "✓ $package 安装成功"
            else
                log_warn "✗ $package 安装可能失败"
            fi
        done
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
    
    log_info "Python环境设置完成"
}

# 系统状态检查
check_system_status() {
    echo -e "\n${BLUE}=== 系统状态检查 ===${NC}"
    
    # 基本信息
    printf "%-20s %s\n" "操作系统:" "$(detect_os)"
    printf "%-20s %s\n" "当前用户:" "$(whoami)"
    printf "%-20s %s\n" "工作目录:" "$PWD"
    printf "%-20s %s\n" "系统时间:" "$(date '+%Y-%m-%d %H:%M:%S')"
    
    # 磁盘空间
    local disk_usage
    disk_usage=$(df -h "$PWD" | awk 'NR==2 {print $5}' | tr -d '%')
    printf "%-20s %s%%\n" "磁盘使用率:" "$disk_usage"
    if [[ "$disk_usage" -gt 90 ]]; then
        log_warn "磁盘空间不足"
    fi
    
    # 内存使用
    if command -v free &> /dev/null; then
        local mem_usage
        mem_usage=$(free | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
        printf "%-20s %s\n" "内存使用率:" "$mem_usage"
    fi
    
    # 网络连接
    echo -e "\n${BLUE}=== 网络连接测试 ===${NC}"
    if curl -s --max-time 5 https://api.telegram.org &>/dev/null; then
        echo -e "Telegram API: ${GREEN}✓ 可访问${NC}"
    else
        echo -e "Telegram API: ${RED}✗ 无法访问${NC}"
    fi
    
    # 文件状态
    echo -e "\n${BLUE}=== 文件状态 ===${NC}"
    local files=("$CONFIG_FILE" "$URLS_FILE" "$MONITOR_SCRIPT" "$REQUIREMENTS_FILE")
    for file in "${files[@]}"; do
        if [[ -f "$file" ]]; then
            local size
            size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
            printf "%-20s ${GREEN}✓${NC} (%s bytes)\n" "$file:" "$size"
        else
            printf "%-20s ${RED}✗${NC}\n" "$file:"
        fi
    done
    
    # Python环境
    echo -e "\n${BLUE}=== Python环境 ===${NC}"
    if [[ -d "$VENV_DIR" ]]; then
        echo -e "虚拟环境: ${GREEN}✓ 已创建${NC}"
        if [[ -f "$VENV_DIR/bin/activate" ]]; then
            source "$VENV_DIR/bin/activate"
            printf "%-20s %s\n" "Python版本:" "$(python3 --version 2>/dev/null | cut -d' ' -f2)"
            printf "%-20s %s\n" "Pip版本:" "$(pip --version 2>/dev/null | cut -d' ' -f2)"
        fi
    else
        echo -e "虚拟环境: ${RED}✗ 未创建${NC}"
    fi
}

# 初始化函数的优化
initialize() {
    if [[ -f "$INIT_MARK" ]]; then
        # 已初始化，只需激活环境
        [[ -f "$VENV_DIR/bin/activate" ]] && source "$VENV_DIR/bin/activate"
        return 0
    fi
    
    log_info "首次运行，正在初始化环境..."
    
    # 检查系统工具
    check_system_tools
    
    # 设置Python环境
    setup_python_environment
    
    # 首次配置
    echo -e "\n${YELLOW}首次运行需要配置Telegram信息${NC}"
    if ! configure_telegram; then
        log_error "Telegram配置失败，无法继续"
        return 1
    fi
    
    # 询问是否添加监控商品
    echo -e "\n${YELLOW}是否现在添加监控商品? [Y/n] ${NC}"
    read -r choice
    if [[ ! "$choice" =~ ^[Nn]$ ]]; then
        add_url
    fi
    
    # 询问是否启动监控
    if [[ -f "$CONFIG_FILE" ]] && [[ -s "$URLS_FILE" ]]; then
        echo -e "\n${YELLOW}是否立即启动监控? [Y/n] ${NC}"
        read -r start_choice
        if [[ ! "$start_choice" =~ ^[Nn]$ ]]; then
            start_monitor
        fi
    fi
    
    # 创建初始化标记
    touch "$INIT_MARK"
    log_info "环境初始化完成"
    
    echo -e "\n${GREEN}🎉 初始化完成！${NC}"
    echo -e "${CYAN}提示：可以随时运行 $0 来管理监控程序${NC}"
    
    echo -e "\n${YELLOW}按回车键继续...${NC}"
    read -r
}

# 显示菜单的优化
show_menu() {
    clear
    
    # 标题
    echo -e "${PURPLE}=========================================${NC}"
    echo -e "${PURPLE} VPS库存监控系统 ${YELLOW}v2.1${NC}"
    echo -e "${PURPLE}=========================================${NC}"
    echo -e " 作者: ${CYAN}jinqian${NC}"
    echo -e " 网站: ${CYAN}https://kure29.com${NC}"
    echo -e "${PURPLE}=========================================${NC}"
    
    # 状态信息
    echo -n "监控状态: "
    if check_monitor_status >/dev/null 2>&1; then
        check_monitor_status
        
        # 显示统计信息
        if [[ -f "$URLS_FILE" ]] && command -v jq &> /dev/null; then
            local url_count
            url_count=$(jq 'length' "$URLS_FILE" 2>/dev/null || echo "0")
            echo -e "监控商品: ${BLUE}$url_count${NC} 个"
        fi
        
        # 显示最后检查时间
        if [[ -s "$MONITOR_LOG" ]]; then
            local last_check
            last_check=$(tail -n 1 "$MONITOR_LOG" 2>/dev/null | cut -d' ' -f1-2 || echo "未知")
            echo -e "最后检查: ${CYAN}$last_check${NC}"
        fi
    else
        check_monitor_status
    fi
    
    echo -e "${PURPLE}=========================================${NC}"
    
    # 菜单选项
    echo -e "${YELLOW}============== 功能菜单 ==============${NC}"
    echo -e "${GREEN}1.${NC} 添加监控商品"
    echo -e "${GREEN}2.${NC} 删除监控商品"
    echo -e "${GREEN}3.${NC} 显示所有监控商品"
    echo -e "${GREEN}4.${NC} 配置Telegram信息"
    echo -e "${GREEN}5.${NC} 启动监控"
    echo -e "${GREEN}6.${NC} 停止监控"
    echo -e "${GREEN}7.${NC} 查看监控状态"
    echo -e "${GREEN}8.${NC} 查看监控日志"
    echo -e "${GREEN}9.${NC} 系统状态检查"
    echo -e "${RED}0.${NC} 退出"
    echo -e "${PURPLE}=========================================${NC}"
}

# 主函数的优化
main() {
    # 设置信号处理
    trap 'echo -e "\n${YELLOW}程序被中断${NC}"; exit 130' INT
    trap 'echo -e "\n${YELLOW}程序被终止${NC}"; exit 143' TERM
    
    initialize
    
    while true; do
        show_menu
        echo -e "\n${YELLOW}请选择操作 (0-9): ${NC}"
        read -r choice
        
        case $choice in
            1)
                add_url
                ;;
            2)
                delete_url
                ;;
            3)
                show_urls
                ;;
            4)
                configure_telegram
                ;;
            5)
                start_monitor
                ;;
            6)
                stop_monitor
                ;;
            7)
                show_monitor_details
                ;;
            8)
                view_log
                ;;
            9)
                check_system_status
                ;;
            0)
                echo -e "${GREEN}退出程序${NC}"
                if pgrep -f "python3.*$MONITOR_SCRIPT" &> /dev/null; then
                    echo -e "${CYAN}监控进程继续在后台运行...${NC}"
                fi
                exit 0
                ;;
            *)
                log_error "无效的选择，请输入 0-9"
                ;;
        esac
        
        echo -e "\n${YELLOW}按回车键继续...${NC}"
        read -r
    done
}

# 运行主程序
main "$@"
