#!/bin/bash

# =========================================
# VPS监控系统 - 快速安装脚本
# 作者: kure29
# 版本: v1.0
# 描述: 一键安装VPS库存监控系统
# =========================================

set -euo pipefail

# 颜色定义
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# 配置变量
readonly REPO_URL="https://github.com/kure29s/VPSMonitorBot.git"
readonly INSTALL_DIR="/opt/vps-monitor"
readonly SERVICE_USER="vpsmonitor"
readonly VERSION="v2.1.0"

# 全局变量
INSTALL_MODE="local"
SKIP_DEPS=false
USE_DOCKER=false
QUIET_MODE=false

# 日志函数
log_info() {
    [[ "$QUIET_MODE" == true ]] && return
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    [[ "$QUIET_MODE" == true ]] && return
    echo -e "\n${PURPLE}=== $1 ===${NC}"
}

# 错误处理
error_exit() {
    log_error "$1"
    echo -e "${RED}安装失败，请检查上述错误信息${NC}"
    exit 1
}

# 检查系统要求
check_system_requirements() {
    log_step "检查系统要求"
    
    # 检查操作系统
    if ! uname -s | grep -E "Linux|Darwin" >/dev/null; then
        error_exit "不支持的操作系统，只支持Linux和macOS"
    fi
    
    # 检查Python版本
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        local min_version="3.7"
        
        # 修复版本比较逻辑
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
            log_info "Python版本检查通过: $python_version"
        else
            log_warn "Python版本过低，需要3.7或更高版本，当前版本: $python_version"
            return 1
        fi
    else
        log_warn "未找到Python3，将在依赖安装阶段安装"
        return 1
    fi
    
    # 检查curl
    if ! command -v curl >/dev/null 2>&1; then
        log_warn "未找到curl，将在依赖安装阶段安装"
    fi
    
    # 检查git
    if ! command -v git >/dev/null 2>&1; then
        log_warn "未找到git，将在依赖安装阶段安装"
    fi
    
    # 检查磁盘空间
    local available_space=$(df . | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 1048576 ]]; then  # 1GB in KB
        log_warn "可用磁盘空间不足1GB，可能影响安装"
    fi
    
    log_info "系统要求检查完成"
}

# 检测操作系统
detect_os() {
    if [[ -f "/etc/debian_version" ]]; then
        echo "debian"
    elif [[ -f "/etc/redhat-release" ]]; then
        echo "redhat"
    elif [[ -f "/etc/arch-release" ]]; then
        echo "arch"
    elif [[ "$(uname)" == "Darwin" ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# 安装系统依赖
install_system_dependencies() {
    if [[ "$SKIP_DEPS" == true ]]; then
        log_info "跳过系统依赖安装"
        return 0
    fi
    
    log_step "安装系统依赖"
    
    local os_type
    os_type=$(detect_os)
    
    case $os_type in
        debian)
            log_info "检测到Debian/Ubuntu系统"
            apt-get update -qq
            apt-get install -y python3 python3-pip python3-venv git curl jq wget
            ;;
        redhat)
            log_info "检测到RedHat/CentOS系统"
            yum update -y -q
            yum install -y python3 python3-pip git curl jq wget
            ;;
        arch)
            log_info "检测到Arch Linux系统"
            pacman -Syu --noconfirm
            pacman -S --noconfirm python python-pip git curl jq wget
            ;;
        macos)
            log_info "检测到macOS系统"
            if command -v brew >/dev/null 2>&1; then
                brew install python3 git curl jq wget
            else
                error_exit "macOS系统需要先安装Homebrew: https://brew.sh/"
            fi
            ;;
        *)
            error_exit "不支持的操作系统类型"
            ;;
    esac
    
    log_info "系统依赖安装完成"
}

# 下载项目代码
download_project() {
    log_step "下载项目代码"
    
    local target_dir="${1:-./VPSMonitorBot}"
    
    if [[ -d "$target_dir" ]]; then
        log_warn "目录已存在: $target_dir"
        echo -e "${YELLOW}是否删除现有目录并重新下载? [y/N] ${NC}"
        read -r confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            rm -rf "$target_dir"
        else
            log_info "使用现有目录"
            return 0
        fi
    fi
    
    log_info "从GitHub克隆项目..."
    if git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$target_dir"; then
        log_info "项目下载完成: $target_dir"
    else
        log_warn "Git克隆失败，尝试下载压缩包..."
        
        local archive_url="https://github.com/kure29s/VPSMonitorBot/archive/refs/tags/${VERSION}.tar.gz"
        local temp_file=$(mktemp)
        
        if curl -L "$archive_url" -o "$temp_file"; then
            mkdir -p "$target_dir"
            tar -xzf "$temp_file" -C "$target_dir" --strip-components=1
            rm -f "$temp_file"
            log_info "项目下载完成: $target_dir"
        else
            error_exit "无法下载项目代码"
        fi
    fi
}

# 设置Python环境
setup_python_environment() {
    log_step "设置Python环境"
    
    local project_dir="$1"
    cd "$project_dir"
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境并安装依赖
    log_info "安装Python依赖包..."
    source venv/bin/activate
    
    # 升级pip
    python3 -m pip install --upgrade pip -q
    
    # 安装依赖
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt -q
    else
        error_exit "未找到requirements.txt文件"
    fi
    
    log_info "Python环境设置完成"
}

# 配置应用
configure_application() {
    log_step "配置应用"
    
    local project_dir="$1"
    cd "$project_dir"
    
    # 创建配置文件
    if [[ ! -f "config.json" ]]; then
        if [[ -f "config/config.json.example" ]]; then
            cp config/config.json.example config.json
            log_info "已创建配置文件: config.json"
        else
            log_warn "未找到配置文件模板"
        fi
    fi
    
    # 创建数据目录
    mkdir -p data logs backup
    
    # 设置脚本权限
    if [[ -f "scripts/menu.sh" ]]; then
        chmod +x scripts/menu.sh
        chmod +x scripts/*.sh
        log_info "脚本权限设置完成"
    fi
    
    log_info "应用配置完成"
}

# Docker安装
install_with_docker() {
    log_step "Docker安装模式"
    
    # 检查Docker
    if ! command -v docker >/dev/null 2>&1; then
        log_info "安装Docker..."
        curl -fsSL https://get.docker.com | sh
        
        # 添加当前用户到docker组
        if [[ -n "${SUDO_USER:-}" ]]; then
            usermod -aG docker "$SUDO_USER"
        fi
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_info "安装Docker Compose..."
        local compose_version="2.21.0"
        curl -L "https://github.com/docker/compose/releases/download/v${compose_version}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    log_info "Docker环境准备完成"
}

# 测试安装
test_installation() {
    log_step "测试安装"
    
    local project_dir="$1"
    cd "$project_dir"
    
    # 测试Python环境
    if source venv/bin/activate && python3 -c "import telegram, cloudscraper; print('依赖检查通过')" 2>/dev/null; then
        log_info "✓ Python依赖测试通过"
    else
        log_error "✗ Python依赖测试失败"
        return 1
    fi
    
    # 测试配置文件
    if [[ -f "config.json" ]] && python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
        log_info "✓ 配置文件格式正确"
    else
        log_warn "✗ 配置文件可能有问题"
    fi
    
    # 测试脚本
    if [[ -x "scripts/menu.sh" ]]; then
        log_info "✓ 管理脚本可执行"
    else
        log_warn "✗ 管理脚本权限问题"
    fi
    
    log_info "安装测试完成"
}

# 显示安装后信息
show_post_install_info() {
    local project_dir="$1"
    
    echo -e "\n${GREEN}🎉 安装完成！${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE} VPS监控系统 ${VERSION} 安装成功${NC}"
    echo -e "${BLUE}=========================================${NC}"
    
    echo -e "\n${YELLOW}📁 安装目录: ${NC}$project_dir"
    
    echo -e "\n${YELLOW}🔧 下一步操作：${NC}"
    echo -e "1. 编辑配置文件:"
    echo -e "   ${CYAN}nano $project_dir/config.json${NC}"
    echo -e "2. 配置Telegram Bot Token和Chat ID"
    echo -e "3. 启动管理界面:"
    echo -e "   ${CYAN}cd $project_dir && ./scripts/menu.sh${NC}"
    
    if [[ "$USE_DOCKER" == true ]]; then
        echo -e "4. 或使用Docker启动:"
        echo -e "   ${CYAN}cd $project_dir && docker-compose up -d${NC}"
    fi
    
    echo -e "\n${YELLOW}📖 快速指南：${NC}"
    echo -e "• 获取Bot Token: 向 @BotFather 发送 /newbot"
    echo -e "• 获取Chat ID: 向 @userinfobot 发送 /start"
    echo -e "• 文档地址: https://github.com/kure29s/VPSMonitorBot"
    echo -e "• 演示Bot: @JQ_VPSMonitorBot"
    
    echo -e "\n${GREEN}安装日志已保存到: $project_dir/install.log${NC}"
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统安装脚本 ${VERSION}

用法: $0 [选项]

选项:
  -h, --help          显示此帮助信息
  -m, --mode MODE     安装模式 (local|docker|system)
  -d, --dir DIR       安装目录 (默认: ./VPSMonitorBot)
  -s, --skip-deps     跳过系统依赖安装
  -q, --quiet         静默安装模式
  --docker            使用Docker安装

安装模式:
  local      本地安装 (默认)
  docker     Docker容器安装
  system     系统服务安装 (需要root权限)

示例:
  $0                           # 本地安装
  $0 --mode docker             # Docker安装
  $0 --dir /opt/vps-monitor    # 指定安装目录
  $0 --quiet                   # 静默安装

注意:
  • local模式: 安装到指定目录，手动管理
  • docker模式: 使用Docker容器运行
  • system模式: 安装为系统服务，开机自启

EOF
}

# 解析命令行参数
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -m|--mode)
                INSTALL_MODE="$2"
                shift 2
                ;;
            -d|--dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            -s|--skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            --docker)
                USE_DOCKER=true
                INSTALL_MODE="docker"
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 验证安装模式
    case $INSTALL_MODE in
        local|docker|system)
            ;;
        *)
            error_exit "无效的安装模式: $INSTALL_MODE"
            ;;
    esac
}

# 主安装函数
main() {
    # 显示欢迎信息
    if [[ "$QUIET_MODE" != true ]]; then
        echo -e "${PURPLE}"
        cat << 'EOF'
 ██╗   ██╗██████╗ ███████╗    ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ 
 ██║   ██║██╔══██╗██╔════╝    ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗
 ██║   ██║██████╔╝███████╗    ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝
 ╚██╗ ██╔╝██╔═══╝ ╚════██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗
  ╚████╔╝ ██║     ███████║    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║
   ╚═══╝  ╚═╝     ╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
EOF
        echo -e "${NC}"
        echo -e "${BLUE}VPS库存监控系统 ${VERSION} 安装程序${NC}"
        echo -e "${BLUE}作者: kure29 | 网站: https://kure29s.com${NC}\n"
    fi
    
    log_info "开始安装 VPS监控系统 ${VERSION}"
    log_info "安装模式: $INSTALL_MODE"
    
    # 设置日志文件
    local log_file="${INSTALL_DIR}/install.log"
    mkdir -p "$(dirname "$log_file")" 2>/dev/null || true
    
    # 重定向输出到日志文件
    exec > >(tee -a "$log_file")
    exec 2>&1
    
    # 执行安装步骤
    check_system_requirements
    
    if [[ "$INSTALL_MODE" == "docker" ]]; then
        install_with_docker
    else
        install_system_dependencies
    fi
    
    download_project "$INSTALL_DIR"
    setup_python_environment "$INSTALL_DIR"
    configure_application "$INSTALL_DIR"
    
    # 测试安装
    if test_installation "$INSTALL_DIR"; then
        show_post_install_info "$INSTALL_DIR"
    else
        error_exit "安装测试失败"
    fi
}

# 错误处理
trap 'log_error "安装过程被中断"; exit 130' INT TERM

# 解析参数并运行
parse_arguments "$@"
main
