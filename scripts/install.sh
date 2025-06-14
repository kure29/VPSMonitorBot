#!/bin/bash
# VPS监控系统 v3.0 - 一键安装脚本（多用户智能监控版）
# 作者: kure29
# 网站: https://kure29.com

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置变量
readonly VERSION="3.0.0"
readonly AUTHOR="kure29"
readonly WEBSITE="https://kure29.com"
readonly GITHUB_REPO="https://github.com/kure29/VPSMonitorBot"
readonly INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"

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

# 改进的用户确认函数
ask_confirmation() {
    local prompt="$1"
    local default="${2:-N}"
    local timeout="${3:-30}"
    
    while true; do
        echo -e "${YELLOW}${prompt}${NC}"
        echo -n "请输入选择 [y/N] (默认: $default, ${timeout}秒后自动选择): "
        
        # 使用read的超时功能
        if read -t "$timeout" -r response; then
            # 用户有输入
            response=${response:-$default}
            case "$response" in
                [Yy]|[Yy][Ee][Ss])
                    return 0
                    ;;
                [Nn]|[Nn][Oo]|"")
                    return 1
                    ;;
                *)
                    echo -e "${RED}无效输入，请输入 y 或 n${NC}"
                    continue
                    ;;
            esac
        else
            # 超时，使用默认值
            echo -e "\n${YELLOW}超时，使用默认选择: $default${NC}"
            case "$default" in
                [Yy])
                    return 0
                    ;;
                *)
                    return 1
                    ;;
            esac
        fi
    done
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
    echo -e "${PURPLE}VPS库存监控系统 v${VERSION} 安装程序 - 多用户智能监控版${NC}"
    echo -e "${CYAN}作者: ${AUTHOR} | 网站: ${WEBSITE}${NC}"
    echo ""
    echo -e "${GREEN}🆕 v3.0 新功能：${NC}"
    echo "• 🧠 智能组合监控算法（DOM+API+指纹+关键词）"
    echo "• 🎯 多重检测方法交叉验证"
    echo "• 📊 置信度评分系统"
    echo "• 👥 多用户支持，所有人可添加监控"
    echo "• 🧩 管理员权限控制"
    echo "• 📈 用户行为统计和分析"
    echo "• 🛡️ 主流VPS商家专用适配"
    echo "• 🔍 专业调试工具"
    echo "• 📤 数据导出和备份功能"
    echo ""
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统 v${VERSION} 安装脚本 - 多用户智能监控版

用法: $0 [选项]

选项:
    -h, --help          显示此帮助信息
    -v, --version       显示版本信息
    --dir <目录>        指定安装目录 (默认: 当前目录)
    --mode <模式>       安装模式: local|docker|systemd (默认: local)
    --skip-deps         跳过系统依赖安装
    --no-download       不下载项目代码 (使用现有代码)
    --migrate           从v1.0/v2.0自动迁移数据
    --init-db           只初始化数据库
    --check-db          检查数据库状态
    --force             强制覆盖现有安装
    --auto-yes          自动确认所有提示 (用于自动化安装)
    --configure         交互式配置Telegram信息

v3.0 新功能:
    --migrate           从旧版本迁移到多用户数据库
    --init-db           初始化多用户SQLite数据库
    --check-db          检查数据库完整性
    --configure         配置Telegram Bot和管理员信息
    --install-selenium  安装Selenium和ChromeDriver

多用户版本特性:
    • 所有用户都可以添加监控项目
    • 库存变化通知推送给管理员
    • 用户行为统计和管理
    • 智能防刷机制
    • 管理员权限控制

示例:
    $0                              # 默认安装到当前目录
    $0 --dir /opt/vps-monitor       # 安装到指定目录
    $0 --mode docker                # 使用Docker模式安装
    $0 --migrate                    # 安装并迁移旧版本数据
    $0 --configure                  # 安装并配置Telegram信息
    $0 --force --auto-yes           # 强制安装，自动确认
    $0 --install-selenium           # 安装包含Selenium的完整版

EOF
}

# 检查系统类型 - 修复版本
detect_os() {
    if [[ -f /etc/os-release ]]; then
        # 使用grep而不是source来避免变量冲突
        OS=$(grep '^ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
        OS_VERSION=$(grep '^VERSION_ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
    elif [[ -f /etc/redhat-release ]]; then
        OS="centos"
        OS_VERSION=$(cat /etc/redhat-release | grep -oE '[0-9]+\.[0-9]+' | head -1)
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
        OS_VERSION=$(cat /etc/debian_version)
    else
        OS="unknown"
        OS_VERSION="unknown"
    fi
    
    # 处理一些特殊情况
    case $OS in
        "ubuntu")
            ;;
        "debian")
            ;;
        "centos"|"rhel")
            ;;
        "rocky"|"almalinux")
            ;;
        "arch")
            ;;
        *)
            # 如果ID为空，尝试从PRETTY_NAME获取
            if [[ -z "$OS" && -f /etc/os-release ]]; then
                PRETTY_NAME=$(grep '^PRETTY_NAME=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
                case $PRETTY_NAME in
                    *"Ubuntu"*)
                        OS="ubuntu"
                        ;;
                    *"Debian"*)
                        OS="debian"
                        ;;
                    *"CentOS"*)
                        OS="centos"
                        ;;
                    *"Rocky"*)
                        OS="rocky"
                        ;;
                    *)
                        OS="unknown"
                        ;;
                esac
            fi
            ;;
    esac
    
    log_debug "检测到操作系统: $OS $OS_VERSION"
}

# 检查Python版本
check_python_version() {
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
            log_info "Python版本检查通过: $python_version"
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

# 检查Chrome/Chromium
check_chrome() {
    if command -v google-chrome >/dev/null 2>&1; then
        local chrome_version=$(google-chrome --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        log_info "Chrome版本: $chrome_version"
        return 0
    elif command -v chromium-browser >/dev/null 2>&1; then
        local chromium_version=$(chromium-browser --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        log_info "Chromium版本: $chromium_version"
        return 0
    else
        log_warn "未找到Chrome/Chromium，智能DOM监控将无法使用"
        return 1
    fi
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖（包含多用户数据库和智能监控支持）"
    
    case $OS in
        ubuntu|debian)
            log_info "检测到Debian/Ubuntu系统"
            export DEBIAN_FRONTEND=noninteractive
            apt update
            apt install -y python3 python3-pip python3-venv git curl jq wget sqlite3
            
            # 安装Chrome (可选)
            if ask_confirmation "是否安装Chrome以支持智能DOM监控？" "Y" 15; then
                wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
                echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
                apt update
                apt install -y google-chrome-stable || {
                    log_warn "Chrome安装失败，但程序仍可正常运行"
                }
            fi
            ;;
        centos|rhel|rocky|alma)
            log_info "检测到CentOS/RHEL系统"
            yum update -y
            yum install -y python3 python3-pip git curl jq wget sqlite
            if command -v dnf >/dev/null 2>&1; then
                dnf install -y python3-venv
            else
                pip3 install virtualenv
            fi
            
            # 安装Chrome (可选)
            if ask_confirmation "是否安装Chrome以支持智能DOM监控？" "Y" 15; then
                cat > /etc/yum.repos.d/google-chrome.repo << 'EOF'
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/$basearch
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF
                yum install -y google-chrome-stable || {
                    log_warn "Chrome安装失败，但程序仍可正常运行"
                }
            fi
            ;;
        arch)
            log_info "检测到Arch Linux系统"
            pacman -Syu --noconfirm
            pacman -S --noconfirm python python-pip git curl jq wget sqlite
            
            if ask_confirmation "是否安装Chrome以支持智能DOM监控？" "Y" 15; then
                pacman -S --noconfirm google-chrome || {
                    log_warn "Chrome安装失败，但程序仍可正常运行"
                }
            fi
            ;;
        *)
            log_warn "未识别的系统类型: $OS"
            log_info "请手动安装以下依赖: python3 python3-pip python3-venv git curl jq wget sqlite3"
            log_info "可选依赖（智能监控）: google-chrome 或 chromium-browser"
            ;;
    esac
    
    log_info "系统依赖安装完成"
}

# 安装Selenium支持
install_selenium_support() {
    log_info "安装Selenium和ChromeDriver支持"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 激活虚拟环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi
    
    # 安装Selenium相关包
    pip install selenium webdriver-manager
    
    # 测试Selenium安装
    python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

try:
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://www.google.com')
    driver.quit()
    print('✅ Selenium和ChromeDriver安装成功')
except Exception as e:
    print(f'❌ Selenium测试失败: {e}')
    print('💡 程序仍可运行，但智能DOM监控功能将无法使用')
" || {
        log_warn "Selenium测试失败，但不影响基础功能"
    }
}

# 改进的下载项目代码函数
download_project() {
    log_info "下载项目代码"
    
    local target_dir="$1"
    local force_download="$2"
    local auto_yes="$3"
    
    if [[ -d "$target_dir" ]]; then
        log_warn "目录已存在: $target_dir"
        
        # 检查目录是否包含项目文件
        local has_project_files=false
        if [[ -f "$target_dir/src/monitor.py" ]] || [[ -f "$target_dir/requirements.txt" ]]; then
            has_project_files=true
            log_info "检测到现有项目文件"
        fi
        
        if [[ "$force_download" == true ]]; then
            log_info "强制模式：删除现有目录"
            rm -rf "$target_dir"
        elif [[ "$auto_yes" == true ]]; then
            log_info "自动模式：使用现有目录"
            return 0
        elif [[ "$has_project_files" == true ]]; then
            if ask_confirmation "发现现有项目文件，是否删除并重新下载？" "N" 30; then
                log_info "删除现有目录并重新下载"
                rm -rf "$target_dir"
            else
                log_info "使用现有目录"
                return 0
            fi
        else
            if ask_confirmation "目录不为空，是否清空并重新下载？" "N" 30; then
                log_info "清空目录并重新下载"
                rm -rf "$target_dir"
            else
                log_info "使用现有目录"
                return 0
            fi
        fi
    fi
    
    log_info "从GitHub克隆项目..."
    if git clone -b v${VERSION} "$GITHUB_REPO" "$target_dir" 2>/dev/null; then
        log_info "项目下载完成"
    else
        log_warn "Git克隆失败，尝试下载压缩包..."
        mkdir -p "$target_dir"
        if curl -L "${GITHUB_REPO}/archive/v${VERSION}.tar.gz" | tar -xz -C "$target_dir" --strip-components=1; then
            log_info "压缩包下载完成"
        else
            log_error "下载失败，请检查网络连接或手动下载项目"
            return 1
        fi
    fi
}

# 设置Python环境
setup_python_env() {
    log_info "设置Python环境（多用户版）"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 删除现有虚拟环境（如果存在且有问题）
    if [[ -d "venv" ]]; then
        log_info "发现现有虚拟环境，正在验证..."
        if ! source venv/bin/activate 2>/dev/null; then
            log_warn "虚拟环境损坏，重新创建..."
            rm -rf venv
        else
            # 检查关键依赖是否存在
            if ! python3 -c "import aiosqlite, telegram" 2>/dev/null; then
                log_warn "关键依赖缺失，重新创建虚拟环境..."
                rm -rf venv
            else
                log_info "虚拟环境正常，跳过创建"
                return 0
            fi
        fi
    fi
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    log_info "升级pip..."
    pip install --upgrade pip
    
    # 安装依赖
    if [[ -f "requirements.txt" ]]; then
        log_info "安装Python依赖（多用户版）..."
        pip install -r requirements.txt
        
        # 手动确保关键依赖安装成功
        log_info "确保关键依赖安装..."
        pip install aiosqlite python-telegram-bot cloudscraper requests aiohttp selenium webdriver-manager
        
        log_info "依赖安装完成"
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
    
    # 验证关键依赖
    log_info "验证关键依赖..."
    python3 -c "
import sys
missing_deps = []

try:
    import aiosqlite
    print('✅ aiosqlite')
except ImportError:
    missing_deps.append('aiosqlite')
    print('❌ aiosqlite')

try:
    import telegram
    print('✅ python-telegram-bot')
except ImportError:
    missing_deps.append('python-telegram-bot')
    print('❌ python-telegram-bot')

try:
    import cloudscraper
    print('✅ cloudscraper')
except ImportError:
    missing_deps.append('cloudscraper')
    print('❌ cloudscraper')

try:
    import sqlite3
    print('✅ sqlite3 (内置)')
except ImportError:
    missing_deps.append('sqlite3')
    print('❌ sqlite3')

try:
    import selenium
    from webdriver_manager.chrome import ChromeDriverManager
    print('✅ selenium + webdriver-manager')
except ImportError:
    print('⚠️ selenium (可选，智能DOM监控功能将不可用)')

if missing_deps:
    print(f'\\n❌ 缺少必需依赖: {missing_deps}')
    sys.exit(1)
else:
    print('\\n✅ 所有必需依赖验证通过')
" || {
        log_error "关键依赖验证失败，尝试手动安装..."
        pip install --force-reinstall aiosqlite python-telegram-bot cloudscraper
        
        # 再次验证
        python3 -c "import aiosqlite, telegram, cloudscraper; print('✅ 手动安装成功')" || {
            log_error "手动安装也失败了，请检查系统环境"
            return 1
        }
    }
}

# 初始化多用户数据库 - 添加缺失的函数
init_multiuser_database() {
    log_info "初始化多用户数据库"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 激活虚拟环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi
    
    # 创建简单的初始化脚本
    cat > init_db.py << 'EOF'
#!/usr/bin/env python3
"""初始化多用户数据库"""
import asyncio
import sys
from pathlib import Path

# 添加源代码目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from database_manager import DatabaseManager
    
    async def init():
        db = DatabaseManager("vps_monitor.db")
        await db.initialize()
        print("✅ 多用户数据库初始化成功")
        return True

    if __name__ == "__main__":
        result = asyncio.run(init())
        sys.exit(0 if result else 1)
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")
    sys.exit(1)
EOF
    
    chmod +x init_db.py
    
    # 运行初始化脚本
    if python3 init_db.py; then
        log_info "✅ 多用户数据库初始化成功"
        rm -f init_db.py
        return 0
    else
        log_error "❌ 多用户数据库初始化失败"
        rm -f init_db.py
        return 1
    fi
}

# 检查数据库状态
check_database_status() {
    log_info "检查数据库状态"
    
    local work_dir="$1"
    cd "$work_dir"
    
    if [[ ! -f "vps_monitor.db" ]]; then
        log_warn "数据库文件不存在"
        return 1
    fi
    
    # 激活虚拟环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi
    
    python3 -c "
import sqlite3
import sys

try:
    conn = sqlite3.connect('vps_monitor.db')
    cursor = conn.cursor()
    
    # 检查表结构
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
    tables = [row[0] for row in cursor.fetchall()]
    
    print('📊 数据库表:')
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'  - {table}: {count} 条记录')
    
    conn.close()
    print('\\n✅ 数据库状态正常')
except Exception as e:
    print(f'❌ 数据库检查失败: {e}')
    sys.exit(1)
"
}

# 测试多用户数据库功能
test_multiuser_database() {
    log_info "测试多用户数据库功能"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 激活虚拟环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        log_debug "虚拟环境已激活"
    fi
    
    # 运行测试脚本
    if [[ -f "test_database.py" ]]; then
        log_info "运行数据库测试..."
        if python3 test_database.py; then
            log_info "✅ 多用户数据库功能测试通过"
            return 0
        else
            log_error "❌ 多用户数据库功能测试失败"
            return 1
        fi
    else
        log_warn "测试脚本不存在，跳过测试"
        return 0
    fi
}

# 交互式配置Telegram信息（多用户版）
configure_telegram_multiuser() {
    log_info "配置Telegram信息（多用户版）"
    
    local work_dir="$1"
    cd "$work_dir"
    
    echo ""
    echo "============================================"
    echo "        配置Telegram机器人信息（多用户版）"
    echo "============================================"
    echo ""
    
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
    
    echo -n "请输入主Chat ID（用于接收系统通知）: "
    read -r chat_id
    
    if [[ -z "$chat_id" ]]; then
        log_error "Chat ID不能为空"
        return 1
    fi
    
    echo ""
    echo "管理员配置（重要！）："
    echo "管理员将接收所有用户的库存变化通知"
    echo "请输入管理员ID（多个ID用逗号分隔）"
    echo -n "管理员ID列表: "
    read -r admin_ids
    
    if [[ -z "$admin_ids" ]]; then
        log_warn "未设置管理员，将使用主Chat ID作为管理员"
        admin_ids="$chat_id"
    fi
    
    # 可选配置
    echo ""
    echo "可选配置（留空使用默认值）："
    echo -n "频道ID（用于发送通知，留空则发送到私聊）: "
    read -r channel_id
    
    echo -n "检查间隔（秒，默认180）: "
    read -r check_interval
    check_interval=${check_interval:-180}
    
    echo -n "每日添加限制（默认50）: "
    read -r daily_add_limit
    daily_add_limit=${daily_add_limit:-50}
    
    echo -n "置信度阈值（0.1-1.0，默认0.6）: "
    read -r confidence_threshold
    confidence_threshold=${confidence_threshold:-0.6}
    
    # 智能监控配置
    echo ""
    echo "智能监控配置："
    echo -n "启用Selenium DOM检测？[Y/n]: "
    read -r enable_selenium
    enable_selenium=${enable_selenium:-Y}
    
    echo -n "启用API自动发现？[Y/n]: "
    read -r enable_api
    enable_api=${enable_api:-Y}
    
    # 创建配置文件
    cat > config.json << EOF
{
    "bot_token": "$bot_token",
    "chat_id": "$chat_id",
    "channel_id": "$channel_id",
    "admin_ids": [$(echo "$admin_ids" | sed 's/,/", "/g' | sed 's/.*/\"&\"/' | sed 's/\"\"//g')],
    "check_interval": $check_interval,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600,
    "request_timeout": 30,
    "retry_delay": 60,
    "items_per_page": 10,
    "daily_add_limit": $daily_add_limit,
    "enable_selenium": $([ "${enable_selenium,,}" = "n" ] && echo "false" || echo "true"),
    "enable_api_discovery": $([ "${enable_api,,}" = "n" ] && echo "false" || echo "true"),
    "enable_visual_comparison": false,
    "confidence_threshold": $confidence_threshold,
    "chromium_path": null,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "debug": false,
    "log_level": "INFO"
}
EOF
    
    log_info "多用户配置文件已保存到 config.json"
    
    # 测试配置
    echo ""
    echo -n "是否测试Telegram连接? (y/N): "
    read -r test_conn
    
    if [[ "$test_conn" == "y" || "$test_conn" == "Y" ]]; then
        test_telegram_connection_multiuser "$work_dir"
    fi
}

# 测试Telegram连接（多用户版）
test_telegram_connection_multiuser() {
    log_info "测试Telegram连接（多用户版）..."
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 激活虚拟环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi
    
    python3 -c "
import requests
import json
import sys

try:
    config = json.load(open('config.json'))
    
    print('🔍 测试Bot Token...')
    resp = requests.get(f'https://api.telegram.org/bot{config[\"bot_token\"]}/getMe', timeout=10)
    
    if resp.json().get('ok'):
        bot_info = resp.json()['result']
        print(f'✅ Bot连接成功: @{bot_info[\"username\"]}')
        
        print('🔍 测试主Chat ID...')
        test_resp = requests.post(
            f'https://api.telegram.org/bot{config[\"bot_token\"]}/sendMessage', 
            json={
                'chat_id': config['chat_id'], 
                'text': '🤖 VPS监控系统 v3.0 (多用户版) 安装完成！\\n\\n这是一条测试消息，说明配置正确。\\n\\n🧩 多用户特性：\\n• 所有用户都可添加监控\\n• 库存变化推送给管理员\\n• 智能组合监控算法\\n\\n请使用 /start 命令开始使用。'
            }, 
            timeout=10
        )
        
        if test_resp.json().get('ok'):
            print('✅ 主Chat测试消息发送成功')
        else:
            error_msg = test_resp.json().get('description', '未知错误')
            print(f'❌ 主Chat测试失败: {error_msg}')
            
        # 测试管理员通知
        admin_ids = config.get('admin_ids', [])
        if admin_ids:
            print(f'🔍 测试管理员通知 ({len(admin_ids)} 个管理员)...')
            for admin_id in admin_ids:
                admin_resp = requests.post(
                    f'https://api.telegram.org/bot{config[\"bot_token\"]}/sendMessage',
                    json={
                        'chat_id': admin_id,
                        'text': '🧩 管理员通知测试\\n\\n您已被设置为VPS监控系统管理员。\\n\\n您将接收：\\n• 所有用户的库存变化通知\\n• 系统状态更新\\n• 管理功能权限\\n\\n使用 /admin 访问管理面板。'
                    },
                    timeout=10
                )
                
                if admin_resp.json().get('ok'):
                    print(f'✅ 管理员 {admin_id} 通知发送成功')
                else:
                    print(f'❌ 管理员 {admin_id} 通知发送失败')
        
        return True
    else:
        error_msg = resp.json().get('description', '未知错误')
        print(f'❌ Bot连接失败: {error_msg}')
        print('💡 请检查Bot Token是否正确')
        return False
        
except requests.exceptions.RequestException as e:
    print(f'❌ 网络请求失败: {e}')
    return False
except json.JSONDecodeError as e:
    print(f'❌ 配置文件格式错误: {e}')
    return False
except Exception as e:
    print(f'❌ 测试失败: {e}')
    return False
    
" && {
        log_info "Telegram连接测试通过"
        return 0
    } || {
        log_warn "Telegram连接测试失败，请检查配置"
        return 1
    }
}

# 从旧版本迁移数据
migrate_from_old_version() {
    log_info "从旧版本迁移数据到多用户版本"
    
    local work_dir="$1"
    cd "$work_dir"
    
    local has_old_data=false
    
    # 检查是否有旧版本数据
    if [[ -f "urls.json" ]]; then
        has_old_data=true
        log_info "发现v1.0版本的urls.json文件"
    fi
    
    if [[ -f "vps_monitor.db" ]]; then
        # 检查是否是旧版本数据库结构
        if sqlite3 vps_monitor.db "SELECT name FROM sqlite_master WHERE type='table' AND name='users';" | grep -q users; then
            log_info "检测到v3.0多用户数据库结构，无需迁移"
        else
            has_old_data=true
            log_info "发现v2.0版本的数据库文件"
        fi
    fi
    
    if [[ "$has_old_data" == false ]]; then
        log_info "未发现需要迁移的旧版本数据"
        return 0
    fi
    
    # 备份旧数据
    local backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    if [[ -f "urls.json" ]]; then
        cp urls.json "$backup_dir/"
        log_info "已备份urls.json到 $backup_dir/"
    fi
    
    if [[ -f "vps_monitor.db" ]]; then
        cp vps_monitor.db "$backup_dir/vps_monitor_old.db"
        log_info "已备份旧数据库到 $backup_dir/"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 执行迁移
    log_info "开始数据迁移到多用户版本..."
    python3 -c "
import json
import asyncio
import sys
import sqlite3
import os
from pathlib import Path

# 添加源代码目录到Python路径
sys.path.insert(0, str(Path.cwd() / 'src'))

from database_manager import DatabaseManager

async def migrate():
    try:
        # 初始化新的多用户数据库
        db = DatabaseManager('vps_monitor.db')
        await db.initialize()
        
        migrated_count = 0
        
        # 迁移v1.0 JSON数据
        if os.path.exists('urls.json'):
            print('📄 迁移v1.0 JSON数据...')
            with open('urls.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            for item_id, item_data in old_data.items():
                name = item_data.get('名称', f'商品{item_id}')
                url = item_data.get('URL', '')
                config = item_data.get('配置', '')
                
                if not url:
                    continue
                
                # 迁移为系统全局项目
                item_id_new, success = await db.add_monitor_item(
                    user_id='system',
                    name=name,
                    url=url,
                    config=config,
                    is_global=True
                )
                
                if success:
                    print(f'✅ 已迁移: {name}')
                    migrated_count += 1
        
        # 迁移v2.0数据库数据（如果存在旧结构）
        backup_db_path = None
        for file in os.listdir('.'):
            if file.startswith('backup_') and file.endswith('vps_monitor_old.db'):
                backup_db_path = file
                break
        
        if backup_db_path and os.path.exists(backup_db_path):
            print('📊 迁移v2.0数据库数据...')
            old_conn = sqlite3.connect(backup_db_path)
            old_cursor = old_conn.cursor()
            
            try:
                old_cursor.execute('SELECT * FROM monitor_items')
                old_items = old_cursor.fetchall()
                
                for item in old_items:
                    # 旧版本字段顺序可能不同，需要适配
                    try:
                        name = item[1] if len(item) > 1 else f'迁移项目{item[0]}'
                        url = item[2] if len(item) > 2 else ''
                        config = item[3] if len(item) > 3 else ''
                        
                        if url:
                            item_id_new, success = await db.add_monitor_item(
                                user_id='system',
                                name=name,
                                url=url,
                                config=config,
                                is_global=True
                            )
                            
                            if success:
                                print(f'✅ 已迁移数据库项目: {name}')
                                migrated_count += 1
                    except Exception as e:
                        print(f'⚠️ 跳过有问题的数据项: {e}')
                        
            except Exception as e:
                print(f'⚠️ 读取旧数据库时出错: {e}')
            finally:
                old_conn.close()
        
        print(f'\\n📊 迁移完成')
        print(f'✅ 成功迁移: {migrated_count} 个监控项')
        print(f'🌐 所有迁移的项目都设置为全局项目，所有用户可见')
        
        return migrated_count > 0
    except Exception as e:
        print(f'❌ 迁移失败: {e}')
        return False

import os
result = asyncio.run(migrate())
sys.exit(0 if result else 1)
" && {
        log_info "数据迁移成功"
        return 0
    } || {
        log_error "数据迁移失败"
        return 1
    }
}

# 显示安装后说明
show_post_install_info() {
    local work_dir="$1"
    local mode="$2"
    local configured="$3"
    
    echo ""
    log_info "🎉 VPS监控系统 v${VERSION} (多用户版) 安装完成！"
    echo ""
    echo "📁 安装目录: $work_dir"
    echo "📄 配置文件: $work_dir/config.json"
    echo "📊 数据库文件: $work_dir/vps_monitor.db"
    echo "📋 日志文件: $work_dir/monitor.log"
    echo ""
    
    case $mode in
        local)
            echo "🚀 启动方法:"
            echo "   cd $work_dir"
            echo "   ./scripts/menu.sh"
            echo ""
            echo "🔧 手动启动:"
            echo "   cd $work_dir"
            echo "   source venv/bin/activate"
            echo "   python3 src/monitor.py"
            ;;
        systemd)
            echo "🚀 服务管理:"
            echo "   启动: systemctl start vps-monitor"
            echo "   停止: systemctl stop vps-monitor"
            echo "   状态: systemctl status vps-monitor"
            echo "   日志: journalctl -u vps-monitor -f"
            ;;
        docker)
            echo "🚀 Docker管理:"
            echo "   cd $work_dir"
            echo "   启动: docker-compose up -d"
            echo "   停止: docker-compose down"
            echo "   日志: docker-compose logs -f"
            ;;
    esac
    
    echo ""
    echo "🆕 v3.0 多用户版新特性:"
    echo "• 🧠 智能组合监控算法（DOM+API+关键词+指纹）"
    echo "• 🎯 多重检测方法交叉验证"
    echo "• 📊 置信度评分系统"
    echo "• 👥 多用户支持，所有人可添加监控"
    echo "• 🧩 管理员权限控制"
    echo "• 📈 用户行为统计和分析"
    echo "• 🛡️ 主流VPS商家专用适配"
    echo "• 🔍 专业调试工具和详细日志"
    echo ""
    
    if [[ "$configured" == "true" ]]; then
        echo "✅ Telegram已配置完成，可以直接启动使用"
        echo ""
        echo "👥 多用户使用说明:"
        echo "• 所有用户都可以通过Bot添加监控项目"
        echo "• 库存变化通知会推送给config.json中的管理员"
        echo "• 管理员可使用 /admin 命令管理系统"
        echo "• 用户每日有添加限制，防止滥用"
        echo ""
        echo "📝 快速启动:"
        echo "1. 运行管理菜单: ./scripts/menu.sh"
        echo "2. 选择 '2. 启动监控'"
        echo "3. 用户通过Telegram Bot使用 /start 开始"
        echo "4. 管理员使用 /admin 访问管理功能"
    else
        echo "📝 下一步:"
        echo "1. 配置Telegram信息:"
        echo "   cd $work_dir"
        echo "   ./scripts/menu.sh  # 选择 '1. 配置Telegram信息'"
        echo "   # 或者手动编辑: nano config.json"
        echo ""
        echo "2. 重要：设置管理员ID"
        echo "   在config.json中配置admin_ids数组"
        echo "   管理员将接收所有库存变化通知"
        echo ""
        echo "3. 启动监控程序"
        if [[ -f "$work_dir/backup_"*"/urls.json" ]] || [[ -f "$work_dir/backup_"*"/vps_monitor_old.db" ]]; then
            echo "4. 🔄 已自动迁移旧版本数据"
        fi
        echo "5. 所有用户都可通过Bot添加监控"
    fi
    
    echo ""
    echo "💾 多用户数据库管理:"
    echo "• 数据库文件: vps_monitor.db"
    echo "• 用户表: users (用户信息和统计)"
    echo "• 监控表: monitor_items (支持用户归属)"
    echo "• 历史表: check_history (详细检查记录)"
    echo "• 通知表: notification_history (通知记录)"
    echo "• 备份命令: cp vps_monitor.db backup/vps_monitor_backup_\$(date +%Y%m%d).db"
    echo ""
    echo "🧩 管理员功能:"
    echo "• 查看所有用户的监控项目"
    echo "• 管理用户权限（封禁/解封）"
    echo "• 查看系统统计和用户行为"
    echo "• 添加全局监控项（所有用户可见）"
    echo "• 系统维护和数据清理"
    echo ""
    echo "❓ 获取帮助:"
    echo "   作者: $AUTHOR"
    echo "   网站: $WEBSITE"
    echo "   项目: $GITHUB_REPO"
    echo "   版本: v$VERSION (多用户智能监控版)"
}

# 设置权限
setup_permissions() {
    log_info "设置文件权限"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 设置脚本执行权限
    find scripts -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    
    # 创建必要目录
    mkdir -p data logs backup export reports
    
    # 设置数据库文件权限
    if [[ -f "vps_monitor.db" ]]; then
        chmod 644 vps_monitor.db
    fi
    
    # 设置配置文件权限
    if [[ -f "config.json" ]]; then
        chmod 600 config.json
    fi
    
    log_info "权限设置完成"
}

# 验证安装
verify_installation() {
    log_info "验证安装"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 检查必要文件
    local required_files=("src/monitor.py" "src/database_manager.py" "requirements.txt" "config.json")
    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            log_debug "✓ $file"
        else
            log_error "✗ $file (缺失)"
            return 1
        fi
    done
    
    # 检查Python环境
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        if python3 -c "
import sys
sys.path.insert(0, 'src')
import telegram
import cloudscraper
import aiosqlite
from database_manager import DatabaseManager
print('✅ Python依赖检查通过')
" 2>/dev/null; then
            log_info "✓ Python依赖检查通过"
        else
            log_error "✗ Python依赖检查失败"
            return 1
        fi
    else
        log_error "✗ Python虚拟环境不存在"
        return 1
    fi
    
    # 检查数据库
    if [[ -f "vps_monitor.db" ]]; then
        log_info "✓ 数据库文件存在"
    else
        log_warn "? 数据库文件不存在（将在首次运行时创建）"
    fi
    
    log_info "安装验证通过"
}

# 配置systemd服务（如果需要）
setup_systemd_service() {
    log_info "配置systemd服务"
    
    local work_dir="$1"
    
    # 创建服务文件
    cat > /etc/systemd/system/vps-monitor.service << EOF
[Unit]
Description=VPS Monitor Bot v3.0
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$work_dir
Environment="PATH=$work_dir/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$work_dir/venv/bin/python3 $work_dir/src/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable vps-monitor
    
    log_info "systemd服务配置完成"
}

# 配置Docker（如果需要）
setup_docker() {
    log_info "配置Docker环境"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 创建Dockerfile
    cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY src/ ./src/
COPY config.json .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 运行监控器
CMD ["python3", "src/monitor.py"]
EOF

    # 创建docker-compose.yml
    cat > docker-compose.yml << EOF
version: '3.8'

services:
  vps-monitor:
    build: .
    restart: unless-stopped
    volumes:
      - ./config.json:/app/config.json
      - ./vps_monitor.db:/app/vps_monitor.db
      - ./logs:/app/logs
    environment:
      - TZ=Asia/Shanghai
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
EOF

    log_info "Docker配置完成"
}

# 主安装函数
main_install() {
    local install_mode="local"
    local skip_deps=false
    local no_download=false
    local migrate_data=false
    local init_db_only=false
    local check_db_only=false
    local install_selenium_only=false
    local force_download=false
    local auto_yes=false
    local configure_tg=false
    local target_dir="$INSTALL_DIR"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "VPS监控系统 v${VERSION} - 多用户智能监控版"
                exit 0
                ;;
            --dir)
                target_dir="$2"
                shift 2
                ;;
            --mode)
                install_mode="$2"
                shift 2
                ;;
            --skip-deps)
                skip_deps=true
                shift
                ;;
            --no-download)
                no_download=true
                shift
                ;;
            --migrate)
                migrate_data=true
                shift
                ;;
            --init-db)
                init_db_only=true
                shift
                ;;
            --check-db)
                check_db_only=true
                shift
                ;;
            --install-selenium)
                install_selenium_only=true
                shift
                ;;
            --force)
                force_download=true
                shift
                ;;
            --auto-yes)
                auto_yes=true
                shift
                ;;
            --configure)
                configure_tg=true
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    show_banner
    
    # 只安装Selenium
    if [[ "$install_selenium_only" == true ]]; then
        log_info "仅安装Selenium支持"
        install_selenium_support "$target_dir"
        exit $?
    fi
    
    # 只检查数据库
    if [[ "$check_db_only" == true ]]; then
        log_info "检查多用户数据库状态"
        check_database_status "$target_dir"
        exit $?
    fi
    
    # 只初始化数据库
    if [[ "$init_db_only" == true ]]; then
        log_info "仅初始化多用户数据库"
        cd "$target_dir"
        init_multiuser_database "$target_dir"
        exit $?
    fi
    
    log_info "开始安装 VPS监控系统 v${VERSION} - 多用户智能监控版"
    log_info "安装模式: $install_mode"
    
    # 检测系统
    echo ""
    echo "=== 检查系统要求 ==="
    detect_os
    
    if ! check_python_version; then
        if [[ "$skip_deps" == false ]]; then
            log_info "将在依赖安装阶段安装Python"
        else
            log_error "Python环境不满足要求且跳过了依赖安装"
            exit 1
        fi
    fi
    
    check_chrome || log_info "Chrome未安装，智能DOM监控将不可用"
    log_info "系统要求检查完成"
    
    # 安装系统依赖
    if [[ "$skip_deps" == false ]]; then
        echo ""
        echo "=== 安装系统依赖 ==="
        install_system_deps
    else
        log_info "跳过系统依赖安装"
    fi
    
    # 下载项目代码
    if [[ "$no_download" == false ]]; then
        echo ""
        echo "=== 下载项目代码 ==="
        download_project "$target_dir" "$force_download" "$auto_yes"
    else
        log_info "跳过项目代码下载"
        if [[ ! -d "$target_dir" ]]; then
            log_error "目标目录不存在: $target_dir"
            exit 1
        fi
    fi
    
    # 设置Python环境
    echo ""
    echo "=== 设置Python环境 ==="
    setup_python_env "$target_dir"
    
    # 测试多用户数据库功能
    echo ""
    echo "=== 测试多用户数据库功能 ==="
    test_multiuser_database "$target_dir"
    
    # 初始化多用户数据库
    echo ""
    echo "=== 初始化多用户数据库 ==="
    init_multiuser_database "$target_dir"
    
    # 数据迁移（如果需要）
    if [[ "$migrate_data" == true ]] || [[ -f "$target_dir/urls.json" ]] || [[ -f "$target_dir/vps_monitor.db" ]]; then
        echo ""
        echo "=== 数据迁移 ==="
        migrate_from_old_version "$target_dir"
    fi
    
    # 生成配置文件
    echo ""
    echo "=== 生成配置文件 ==="
    if [[ ! -f "$target_dir/config.json" ]]; then
        if [[ -f "$target_dir/config.json.example" ]]; then
            cp "$target_dir/config.json.example" "$target_dir/config.json"
            log_info "已从示例创建配置文件"
        else
            # 创建基础配置文件
            cat > "$target_dir/config.json" << 'EOF'
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "admin_ids": ["YOUR_ADMIN_ID"],
    "check_interval": 180,
    "daily_add_limit": 50,
    "confidence_threshold": 0.6,
    "enable_selenium": true,
    "enable_api_discovery": true
}
EOF
            log_info "已创建基础配置文件"
        fi
        log_warn "请编辑 config.json 文件配置您的Telegram信息"
    else
        log_info "配置文件已存在"
    fi
    
    # 配置Telegram（如果需要）
    local tg_configured=false
    if [[ "$configure_tg" == true ]] && [[ "$auto_yes" == false ]]; then
        echo ""
        echo "=== 配置Telegram信息 ==="
        if configure_telegram_multiuser "$target_dir"; then
            tg_configured=true
        fi
    fi
    
    # 安装Selenium支持（可选）
    if ask_confirmation "是否安装Selenium支持以启用智能DOM监控？" "Y" 15; then
        echo ""
        echo "=== 安装Selenium支持 ==="
        install_selenium_support "$target_dir"
    fi
    
    # 设置权限
    echo ""
    echo "=== 设置权限 ==="
    setup_permissions "$target_dir"
    
    # 根据模式进行特殊配置
    case $install_mode in
        systemd)
            echo ""
            echo "=== 配置系统服务 ==="
            setup_systemd_service "$target_dir"
            ;;
        docker)
            echo ""
            echo "=== 配置Docker环境 ==="
            setup_docker "$target_dir"
            ;;
        local)
            log_info "本地模式，无需额外配置"
            ;;
        *)
            log_error "未知安装模式: $install_mode"
            exit 1
            ;;
    esac
    
    # 验证安装
    echo ""
    echo "=== 验证安装 ==="
    verify_installation "$target_dir"
    
    # 显示安装后信息
    show_post_install_info "$target_dir" "$install_mode" "$tg_configured"
}

# 错误处理
error_handler() {
    local line_number=$1
    log_error "安装过程中发生错误 (行号: $line_number)"
    log_error "请检查错误信息并重试"
    exit 1
}

# 设置错误处理
trap 'error_handler $LINENO' ERR

# 主函数
main() {
    # 检查运行权限
    if [[ $EUID -ne 0 ]] && [[ "$1" == "--mode" && "$2" == "systemd" ]]; then
        log_error "系统服务模式需要root权限，请使用sudo运行"
        exit 1
    fi
    
    main_install "$@"
}

# 运行主函数
main "$@"
