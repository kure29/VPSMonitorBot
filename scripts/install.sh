#!/bin/bash
# VPS监控系统 v2.0 - 一键安装脚本（数据库优化版）
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
readonly VERSION="2.0.0"
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
    echo -e "${PURPLE}VPS库存监控系统 v${VERSION} 安装程序 - 数据库优化版${NC}"
    echo -e "${CYAN}作者: ${AUTHOR} | 网站: ${WEBSITE}${NC}"
    echo ""
    echo -e "${GREEN}🆕 v2.0 新功能：${NC}"
    echo "• 📊 SQLite数据库存储，更稳定可靠"
    echo "• 📈 详细统计分析功能"
    echo "• 📄 分页显示监控列表"
    echo "• 📤 数据导出和备份功能"
    echo "• 🔄 从v1.0 JSON格式自动迁移"
    echo ""
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统 v${VERSION} 安装脚本 - 数据库优化版

用法: $0 [选项]

选项:
    -h, --help          显示此帮助信息
    -v, --version       显示版本信息
    --dir <目录>        指定安装目录 (默认: 当前目录)
    --mode <模式>       安装模式: local|docker|systemd (默认: local)
    --skip-deps         跳过系统依赖安装
    --no-download       不下载项目代码 (使用现有代码)
    --migrate           从v1.0自动迁移数据
    --init-db           只初始化数据库
    --check-db          检查数据库状态

v2.0 新功能:
    --migrate           从JSON格式迁移到数据库
    --init-db           初始化SQLite数据库
    --check-db          检查数据库完整性

示例:
    $0                              # 默认安装到当前目录
    $0 --dir /opt/vps-monitor       # 安装到指定目录
    $0 --mode docker                # 使用Docker模式安装
    $0 --migrate                    # 安装并迁移v1.0数据
    $0 --init-db                    # 只初始化数据库
    $0 --check-db                   # 检查数据库状态

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

# 检查SQLite版本
check_sqlite_version() {
    if command -v sqlite3 >/dev/null 2>&1; then
        local sqlite_version=$(sqlite3 --version | cut -d' ' -f1)
        log_info "SQLite版本: $sqlite_version"
        return 0
    else
        log_warn "未找到SQLite3，将在依赖安装阶段安装"
        return 1
    fi
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖（包含数据库支持）"
    
    case $OS in
        ubuntu|debian)
            log_info "检测到Debian/Ubuntu系统"
            export DEBIAN_FRONTEND=noninteractive
            apt update
            apt install -y python3 python3-pip python3-venv git curl jq wget sqlite3
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
            ;;
        arch)
            log_info "检测到Arch Linux系统"
            pacman -Syu --noconfirm
            pacman -S --noconfirm python python-pip git curl jq wget sqlite
            ;;
        *)
            log_warn "未识别的系统类型: $OS"
            log_info "请手动安装以下依赖: python3 python3-pip python3-venv git curl jq wget sqlite3"
            ;;
    esac
    
    log_info "系统依赖安装完成"
}

# 下载项目代码
download_project() {
    log_info "下载项目代码"
    
    local target_dir="$1"
    
    if [[ -d "$target_dir" ]]; then
        log_warn "目录已存在: $target_dir"
        echo -n "是否删除现有目录并重新下载? [y/N] "
        read -r confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            rm -rf "$target_dir"
        else
            log_info "使用现有目录"
            return 0
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
    log_info "设置Python环境"
    
    local work_dir="$1"
    cd "$work_dir"
    
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
        log_info "安装Python依赖..."
        pip install -r requirements.txt
        log_info "依赖安装完成"
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
    
    # 检查关键依赖
    log_info "验证关键依赖..."
    python3 -c "
import sqlite3
import aiosqlite
import telegram
import cloudscraper
print('✅ 所有关键依赖验证通过')
" || {
        log_error "关键依赖验证失败"
        return 1
    }
}

# 初始化数据库
init_database() {
    log_info "初始化SQLite数据库"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 检查数据库管理器是否存在
    if [[ ! -f "database_manager.py" ]]; then
        log_error "未找到database_manager.py文件"
        return 1
    fi
    
    # 初始化数据库
    log_info "创建数据库表结构..."
    python3 -c "
import asyncio
import sys
from database_manager import DatabaseManager

async def init_db():
    try:
        db = DatabaseManager('vps_monitor.db')
        await db.initialize()
        print('✅ 数据库初始化成功')
        return True
    except Exception as e:
        print(f'❌ 数据库初始化失败: {e}')
        return False

result = asyncio.run(init_db())
sys.exit(0 if result else 1)
" || {
        log_error "数据库初始化失败"
        return 1
    }
    
    # 检查数据库文件
    if [[ -f "vps_monitor.db" ]]; then
        local db_size=$(du -h vps_monitor.db | cut -f1)
        log_info "数据库文件创建成功，大小: $db_size"
    else
        log_error "数据库文件创建失败"
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
    source venv/bin/activate
    
    # 检查数据库结构
    python3 -c "
import sqlite3
import asyncio
from database_manager import DatabaseManager

async def check_db():
    try:
        db = DatabaseManager('vps_monitor.db')
        
        # 检查表结构
        async with aiosqlite.connect('vps_monitor.db') as conn:
            cursor = await conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
            tables = await cursor.fetchall()
            
            print(f'📊 数据库表: {len(tables)} 个')
            for table in tables:
                cursor = await conn.execute(f'SELECT COUNT(*) FROM {table[0]}')
                count = await cursor.fetchone()
                print(f'  - {table[0]}: {count[0]} 条记录')
        
        print('✅ 数据库状态正常')
        return True
    except Exception as e:
        print(f'❌ 数据库检查失败: {e}')
        return False

import aiosqlite
result = asyncio.run(check_db())
" || {
        log_error "数据库状态检查失败"
        return 1
    }
}

# 从v1.0迁移数据
migrate_from_v1() {
    log_info "从v1.0 JSON格式迁移数据"
    
    local work_dir="$1"
    cd "$work_dir"
    
    if [[ ! -f "urls.json" ]]; then
        log_warn "未找到urls.json文件，跳过迁移"
        return 0
    fi
    
    # 备份原文件
    cp urls.json urls.json.backup.$(date +%Y%m%d_%H%M%S)
    log_info "已备份原始urls.json文件"
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 执行迁移
    log_info "开始数据迁移..."
    python3 -c "
import json
import asyncio
import sys
from database_manager import DatabaseManager

async def migrate():
    try:
        # 读取旧数据
        with open('urls.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        print(f'📄 发现 {len(old_data)} 个监控项')
        
        # 初始化数据库
        db = DatabaseManager('vps_monitor.db')
        await db.initialize()
        
        # 迁移数据
        migrated = 0
        skipped = 0
        
        for item_id, item_data in old_data.items():
            name = item_data.get('名称', f'商品{item_id}')
            url = item_data.get('URL', '')
            config = item_data.get('配置', '')
            
            if not url:
                print(f'⏭️  跳过无效URL: {name}')
                skipped += 1
                continue
            
            # 检查是否已存在
            existing = await db.get_monitor_item_by_url(url)
            if existing:
                print(f'⏭️  跳过已存在: {name}')
                skipped += 1
                continue
            
            # 添加到数据库
            try:
                await db.add_monitor_item(name, url, config)
                print(f'✅ 已迁移: {name}')
                migrated += 1
            except Exception as e:
                print(f'❌ 迁移失败 {name}: {e}')
                skipped += 1
        
        print(f'\\n📊 迁移完成')
        print(f'✅ 成功迁移: {migrated} 个')
        print(f'⏭️  跳过项目: {skipped} 个')
        
        return migrated > 0
    except Exception as e:
        print(f'❌ 迁移失败: {e}')
        return False

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

# 配置系统服务
setup_systemd_service() {
    log_info "配置系统服务"
    
    local work_dir="$1"
    local service_file="/etc/systemd/system/vps-monitor.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=VPS Monitor v${VERSION} - Database Edition
Documentation=${WEBSITE}
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory=$work_dir
Environment=PATH=$work_dir/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$work_dir
ExecStart=$work_dir/venv/bin/python $work_dir/src/monitor.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vps-monitor

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$work_dir
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd
    systemctl daemon-reload
    systemctl enable vps-monitor
    
    log_info "系统服务配置完成"
    log_info "使用以下命令管理服务:"
    log_info "  启动: systemctl start vps-monitor"
    log_info "  停止: systemctl stop vps-monitor"
    log_info "  状态: systemctl status vps-monitor"
    log_info "  日志: journalctl -u vps-monitor -f"
}

# 配置Docker环境
setup_docker() {
    log_info "配置Docker环境"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 检查Docker是否安装
    if ! command -v docker >/dev/null 2>&1; then
        log_info "安装Docker..."
        case $OS in
            ubuntu|debian)
                curl -fsSL https://get.docker.com | sh
                ;;
            centos|rhel|rocky|alma)
                yum install -y docker
                systemctl start docker
                systemctl enable docker
                ;;
            *)
                log_error "请手动安装Docker"
                return 1
                ;;
        esac
    fi
    
    # 检查docker-compose是否安装
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_info "安装docker-compose..."
        curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # 创建Docker配置
    if [[ ! -f "Dockerfile" ]]; then
        log_info "创建Dockerfile..."
        cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data logs backup

# 暴露端口（如果需要）
EXPOSE 8000

# 启动命令
CMD ["python", "src/monitor.py"]
EOF
    fi
    
    # 创建docker-compose文件
    if [[ ! -f "docker-compose.yml" ]]; then
        log_info "创建docker-compose.yml..."
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  vps-monitor:
    build: .
    container_name: vps-monitor-v2
    restart: unless-stopped
    volumes:
      - ./vps_monitor.db:/app/vps_monitor.db
      - ./config.json:/app/config.json
      - ./logs:/app/logs
      - ./backup:/app/backup
    environment:
      - TZ=Asia/Shanghai
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF
    fi
    
    log_info "Docker环境配置完成"
    log_info "使用以下命令管理服务:"
    log_info "  启动: docker-compose up -d"
    log_info "  停止: docker-compose down"
    log_info "  日志: docker-compose logs -f"
}

# 生成配置文件
generate_config() {
    log_info "生成配置文件"
    
    local work_dir="$1"
    cd "$work_dir"
    
    if [[ ! -f "config.json" ]]; then
        if [[ -f "config/config.json.example" ]]; then
            cp config/config.json.example config.json
            log_info "已从示例创建配置文件"
        else
            cat > config.json << 'EOF'
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "channel_id": "",
    "admin_ids": [],
    "check_interval": 180,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600,
    "request_timeout": 30,
    "retry_delay": 60,
    "items_per_page": 10,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "debug": false,
    "log_level": "INFO"
}
EOF
            log_info "已创建默认配置文件"
        fi
        
        log_warn "请编辑 config.json 文件配置您的Telegram信息"
    else
        log_info "配置文件已存在"
    fi
}

# 设置权限
setup_permissions() {
    log_info "设置文件权限"
    
    local work_dir="$1"
    cd "$work_dir"
    
    # 设置脚本执行权限
    find scripts -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    
    # 创建必要目录
    mkdir -p data logs backup export
    
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
    local required_files=("src/monitor.py" "database_manager.py" "requirements.txt" "config.json")
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
        if check_database_status "$work_dir" >/dev/null 2>&1; then
            log_info "✓ 数据库状态正常"
        else
            log_error "✗ 数据库状态异常"
            return 1
        fi
    else
        log_warn "? 数据库文件不存在（将在首次运行时创建）"
    fi
    
    log_info "安装验证通过"
}

# 显示安装后说明
show_post_install_info() {
    local work_dir="$1"
    local mode="$2"
    
    echo ""
    log_info "🎉 VPS监控系统 v${VERSION} 安装完成！"
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
    echo "🆕 v2.0 新功能:"
    echo "• 📊 SQLite数据库存储，支持历史数据分析"
    echo "• 📈 详细的统计信息和趋势分析"
    echo "• 📄 分页显示监控列表，支持大量商品"
    echo "• 📤 数据导出和备份功能"
    echo "• 🔄 从v1.0 JSON格式自动迁移"
    echo ""
    echo "📝 下一步:"
    echo "1. 编辑配置文件设置Telegram信息"
    echo "   nano $work_dir/config.json"
    echo "2. 启动监控程序"
    if [[ -f "$work_dir/urls.json" ]]; then
        echo "3. 🔄 运行数据迁移（检测到v1.0数据）"
        echo "   cd $work_dir && python3 -c \"import asyncio; from database_manager import *; ...\""
    fi
    echo "4. 使用Telegram Bot添加监控商品"
    echo ""
    echo "💾 数据库管理:"
    echo "• 数据库文件: vps_monitor.db"
    echo "• 备份命令: cp vps_monitor.db backup/vps_monitor_backup_\$(date +%Y%m%d).db"
    echo "• 查看数据: sqlite3 vps_monitor.db '.tables'"
    echo ""
    echo "❓ 获取帮助:"
    echo "   作者: $AUTHOR"
    echo "   网站: $WEBSITE"
    echo "   项目: $GITHUB_REPO"
}

# 主安装函数
main_install() {
    local install_mode="local"
    local skip_deps=false
    local no_download=false
    local migrate_data=false
    local init_db_only=false
    local check_db_only=false
    local target_dir="$INSTALL_DIR"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "VPS监控系统 v${VERSION} - 数据库优化版"
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
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    show_banner
    
    # 只检查数据库
    if [[ "$check_db_only" == true ]]; then
        log_info "检查数据库状态模式"
        check_database_status "$target_dir"
        exit $?
    fi
    
    # 只初始化数据库
    if [[ "$init_db_only" == true ]]; then
        log_info "仅初始化数据库模式"
        cd "$target_dir"
        init_database "$target_dir"
        exit $?
    fi
    
    log_info "开始安装 VPS监控系统 v${VERSION} - 数据库优化版"
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
    
    check_sqlite_version || true
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
        download_project "$target_dir"
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
    
    # 初始化数据库
    echo ""
    echo "=== 初始化数据库 ==="
    init_database "$target_dir"
    
    # 数据迁移（如果需要）
    if [[ "$migrate_data" == true ]] || [[ -f "$target_dir/urls.json" ]]; then
        echo ""
        echo "=== 数据迁移 ==="
        migrate_from_v1 "$target_dir"
    fi
    
    # 生成配置文件
    echo ""
    echo "=== 生成配置文件 ==="
    generate_config "$target_dir"
    
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
    show_post_install_info "$target_dir" "$install_mode"
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
