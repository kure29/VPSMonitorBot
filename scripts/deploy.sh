#!/bin/bash

# =========================================
# VPS监控机器人 - 自动化部署脚本
# 作者: kure29
# 版本: v1.0
# 描述: 一键部署VPS库存监控系统
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
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly APP_NAME="vps-monitor"
readonly APP_USER="vpsmonitor"
readonly INSTALL_DIR="/opt/vps-monitor"
readonly SERVICE_NAME="vps-monitor.service"
readonly REPO_URL="https://github.com/kure29/VPSMonitorBot.git"

# 全局变量
DEPLOY_MODE=""
SKIP_DEPS=false
USE_DOCKER=false
USE_SYSTEMD=false
FORCE_REINSTALL=false

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

log_step() {
    echo -e "\n${PURPLE}=== $1 ===${NC}"
}

# 错误处理
error_exit() {
    log_error "$1"
    exit 1
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        return 0
    else
        return 1
    fi
}

# 检测操作系统
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

# 安装系统依赖
install_system_dependencies() {
    log_step "安装系统依赖"
    
    local os_type
    os_type=$(detect_os)
    
    case $os_type in
        debian)
            apt-get update -q
            apt-get install -y \
                python3 python3-pip python3-venv python3-dev \
                git curl wget jq unzip \
                build-essential libssl-dev libffi-dev \
                supervisor nginx certbot \
                sqlite3 redis-server
            ;;
        redhat)
            yum update -y
            yum groupinstall -y "Development Tools"
            yum install -y \
                python3 python3-pip python3-devel \
                git curl wget jq unzip \
                openssl-devel libffi-devel \
                supervisor nginx certbot \
                sqlite redis
            ;;
        arch)
            pacman -Syu --noconfirm
            pacman -S --noconfirm \
                python python-pip \
                git curl wget jq unzip \
                base-devel openssl libffi \
                supervisor nginx certbot \
                sqlite redis
            ;;
        *)
            error_exit "不支持的操作系统"
            ;;
    esac
    
    log_info "系统依赖安装完成"
}

# 创建应用用户
create_app_user() {
    if ! id "$APP_USER" &>/dev/null; then
        log_step "创建应用用户"
        
        if check_root; then
            useradd -r -s /bin/false -d "$INSTALL_DIR" "$APP_USER"
            log_info "用户 $APP_USER 创建成功"
        else
            log_warn "非root用户，跳过用户创建"
        fi
    else
        log_info "用户 $APP_USER 已存在"
    fi
}

# 创建目录结构
create_directories() {
    log_step "创建目录结构"
    
    local directories=(
        "$INSTALL_DIR"
        "$INSTALL_DIR/data"
        "$INSTALL_DIR/logs"
        "$INSTALL_DIR/backup"
        "$INSTALL_DIR/config"
        "/var/log/vps-monitor"
    )
    
    for dir in "${directories[@]}"; do
        if check_root; then
            mkdir -p "$dir"
            chown "$APP_USER:$APP_USER" "$dir"
        else
            mkdir -p "$dir"
        fi
        log_info "创建目录: $dir"
    done
}

# 下载/复制应用代码
deploy_application() {
    log_step "部署应用代码"
    
    if [[ -d "$SCRIPT_DIR/.git" ]]; then
        # 从本地复制
        log_info "从本地目录复制代码"
        cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    else
        # 从Git仓库克隆
        log_info "从Git仓库克隆代码"
        if [[ -d "$INSTALL_DIR/.git" ]]; then
            cd "$INSTALL_DIR"
            git pull origin main
        else
            git clone "$REPO_URL" "$INSTALL_DIR"
        fi
    fi
    
    # 设置权限
    if check_root; then
        chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
    fi
    
    chmod +x "$INSTALL_DIR/menu.sh"
    log_info "应用代码部署完成"
}

# 设置Python环境
setup_python_environment() {
    log_step "设置Python环境"
    
    cd "$INSTALL_DIR"
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        log_info "创建Python虚拟环境"
        if check_root; then
            sudo -u "$APP_USER" python3 -m venv venv
        else
            python3 -m venv venv
        fi
    fi
    
    # 激活虚拟环境并安装依赖
    log_info "安装Python依赖"
    if check_root; then
        sudo -u "$APP_USER" bash -c "
            source venv/bin/activate
            pip install --upgrade pip
            pip install -r requirements.txt
        "
    else
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    
    log_info "Python环境设置完成"
}

# 生成配置文件
generate_config() {
    log_step "生成配置文件"
    
    local config_file="$INSTALL_DIR/config.json"
    
    if [[ ! -f "$config_file" ]]; then
        log_info "创建配置文件模板"
        cat > "$config_file" << 'EOF'
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "check_interval": 300,
    "max_notifications": 3,
    "request_timeout": 30,
    "retry_delay": 60,
    "enable_debug_logs": false,
    "max_log_file_size": 10485760,
    "backup_data_file": true
}
EOF
        
        if check_root; then
            chown "$APP_USER:$APP_USER" "$config_file"
        fi
        
        log_warn "请编辑 $config_file 配置Telegram信息"
    else
        log_info "配置文件已存在，跳过创建"
    fi
}

# 设置systemd服务
setup_systemd_service() {
    if ! check_root; then
        log_warn "非root用户，跳过systemd服务设置"
        return 0
    fi
    
    log_step "设置systemd服务"
    
    local service_file="/etc/systemd/system/$SERVICE_NAME"
    
    cat > "$service_file" << EOF
[Unit]
Description=VPS库存监控机器人
Documentation=https://github.com/kure29/VPSMonitorBot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/monitor.py
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
ReadWritePaths=$INSTALL_DIR/data $INSTALL_DIR/logs /var/log/vps-monitor

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd并启用服务
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    
    log_info "systemd服务设置完成"
}

# 设置Docker环境
setup_docker_environment() {
    log_step "设置Docker环境"
    
    # 检查Docker是否安装
    if ! command -v docker &> /dev/null; then
        log_info "安装Docker"
        curl -fsSL https://get.docker.com | sh
        
        if check_root; then
            usermod -aG docker "$APP_USER"
        fi
    fi
    
    # 检查Docker Compose是否安装
    if ! command -v docker-compose &> /dev/null; then
        log_info "安装Docker Compose"
        local compose_version="2.21.0"
        curl -L "https://github.com/docker/compose/releases/download/v${compose_version}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # 构建Docker镜像
    cd "$INSTALL_DIR"
    log_info "构建Docker镜像"
    docker build -t vps-monitor:latest .
    
    log_info "Docker环境设置完成"
}

# 设置Nginx反向代理（可选）
setup_nginx() {
    if ! check_root; then
        log_warn "非root用户，跳过Nginx设置"
        return 0
    fi
    
    log_step "设置Nginx反向代理"
    
    local nginx_config="/etc/nginx/sites-available/vps-monitor"
    
    cat > "$nginx_config" << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /opt/vps-monitor/web/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    
    # 启用站点
    ln -sf "$nginx_config" "/etc/nginx/sites-enabled/"
    nginx -t && systemctl reload nginx
    
    log_info "Nginx配置完成"
    log_warn "请修改 $nginx_config 中的域名配置"
}

# 设置备份任务
setup_backup_cron() {
    if ! check_root; then
        log_warn "非root用户，跳过备份任务设置"
        return 0
    fi
    
    log_step "设置自动备份任务"
    
    local backup_script="$INSTALL_DIR/backup.sh"
    
    cat > "$backup_script" << EOF
#!/bin/bash
# VPS监控数据自动备份脚本

BACKUP_DIR="$INSTALL_DIR/backup"
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\$BACKUP_DIR/vps_monitor_\$DATE.tar.gz"

# 创建备份
cd "$INSTALL_DIR"
tar -czf "\$BACKUP_FILE" \\
    --exclude='venv' \\
    --exclude='__pycache__' \\
    --exclude='*.pyc' \\
    --exclude='logs/*.log' \\
    data/ config.json urls.json

# 清理30天前的备份
find "\$BACKUP_DIR" -name "vps_monitor_*.tar.gz" -mtime +30 -delete

echo "备份完成: \$BACKUP_FILE"
EOF
    
    chmod +x "$backup_script"
    chown "$APP_USER:$APP_USER" "$backup_script"
    
    # 添加到crontab（每天凌晨2点备份）
    (crontab -u "$APP_USER" -l 2>/dev/null; echo "0 2 * * * $backup_script") | crontab -u "$APP_USER" -
    
    log_info "自动备份任务设置完成"
}

# 配置防火墙
setup_firewall() {
    if ! check_root; then
        log_warn "非root用户，跳过防火墙设置"
        return 0
    fi
    
    log_step "配置防火墙"
    
    if command -v ufw &> /dev/null; then
        # Ubuntu/Debian UFW
        ufw allow ssh
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        log_info "UFW防火墙配置完成"
    elif command -v firewall-cmd &> /dev/null; then
        # CentOS/RHEL firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        log_info "firewalld防火墙配置完成"
    else
        log_warn "未检测到支持的防火墙，请手动配置"
    fi
}

# 安全加固
security_hardening() {
    if ! check_root; then
        log_warn "非root用户，跳过安全加固"
        return 0
    fi
    
    log_step "系统安全加固"
    
    # 设置文件权限
    chmod 700 "$INSTALL_DIR/config"
    chmod 600 "$INSTALL_DIR/config.json"
    
    # 禁用不必要的服务
    local services_to_disable=("telnet" "rsh" "rlogin")
    for service in "${services_to_disable[@]}"; do
        if systemctl is-enabled "$service" &>/dev/null; then
            systemctl disable "$service"
            log_info "禁用服务: $service"
        fi
    done
    
    # 设置登录失败锁定
    if [[ -f "/etc/pam.d/common-auth" ]]; then
        if ! grep -q "pam_tally2" /etc/pam.d/common-auth; then
            echo "auth required pam_tally2.so deny=5 unlock_time=1800" >> /etc/pam.d/common-auth
            log_info "设置登录失败锁定"
        fi
    fi
    
    log_info "安全加固完成"
}

# 验证部署
verify_deployment() {
    log_step "验证部署"
    
    local checks_passed=0
    local total_checks=0
    
    # 检查文件
    local required_files=(
        "$INSTALL_DIR/monitor.py"
        "$INSTALL_DIR/requirements.txt"
        "$INSTALL_DIR/venv/bin/activate"
        "$INSTALL_DIR/config.json"
    )
    
    for file in "${required_files[@]}"; do
        ((total_checks++))
        if [[ -f "$file" ]]; then
            log_info "✓ 文件存在: $file"
            ((checks_passed++))
        else
            log_error "✗ 文件缺失: $file"
        fi
    done
    
    # 检查Python依赖
    ((total_checks++))
    if cd "$INSTALL_DIR" && source venv/bin/activate && python3 -c "import telegram, cloudscraper" 2>/dev/null; then
        log_info "✓ Python依赖检查通过"
        ((checks_passed++))
    else
        log_error "✗ Python依赖检查失败"
    fi
    
    # 检查systemd服务（如果适用）
    if check_root && [[ "$USE_SYSTEMD" == true ]]; then
        ((total_checks++))
        if systemctl is-enabled "$SERVICE_NAME" &>/dev/null; then
            log_info "✓ systemd服务已启用"
            ((checks_passed++))
        else
            log_error "✗ systemd服务未启用"
        fi
    fi
    
    echo -e "\n${PURPLE}验证结果: $checks_passed/$total_checks 项检查通过${NC}"
    
    if [[ $checks_passed -eq $total_checks ]]; then
        log_info "部署验证成功！"
        return 0
    else
        log_error "部署验证失败，请检查上述错误"
        return 1
    fi
}

# 显示部署后信息
show_post_deploy_info() {
    log_step "部署完成"
    
    echo -e "${GREEN}🎉 VPS监控系统部署成功！${NC}\n"
    
    echo -e "${BLUE}下一步操作：${NC}"
    echo -e "1. 编辑配置文件: ${YELLOW}$INSTALL_DIR/config.json${NC}"
    echo -e "2. 配置Telegram Bot Token和Chat ID"
    echo -e "3. 启动服务:"
    
    if [[ "$USE_DOCKER" == true ]]; then
        echo -e "   ${CYAN}cd $INSTALL_DIR && docker-compose up -d${NC}"
    elif [[ "$USE_SYSTEMD" == true ]] && check_root; then
        echo -e "   ${CYAN}systemctl start $SERVICE_NAME${NC}"
        echo -e "   ${CYAN}systemctl status $SERVICE_NAME${NC}"
    else
        echo -e "   ${CYAN}cd $INSTALL_DIR && ./menu.sh${NC}"
    fi
    
    echo -e "\n${BLUE}管理命令：${NC}"
    echo -e "• 查看日志: ${CYAN}tail -f $INSTALL_DIR/logs/monitor.log${NC}"
    echo -e "• 管理界面: ${CYAN}cd $INSTALL_DIR && ./menu.sh${NC}"
    echo -e "• 备份数据: ${CYAN}$INSTALL_DIR/backup.sh${NC}"
    
    if check_root; then
        echo -e "• 系统服务: ${CYAN}systemctl {start|stop|restart|status} $SERVICE_NAME${NC}"
    fi
    
    echo -e "\n${YELLOW}重要提醒：${NC}"
    echo -e "• 请确保配置文件中的敏感信息安全"
    echo -e "• 建议启用自动备份功能"
    echo -e "• 定期更新系统和应用依赖"
    
    echo -e "\n${CYAN}文档链接：${NC}"
    echo -e "• GitHub: https://github.com/kure29/VPSMonitorBot"
    echo -e "• 演示Bot: @JQ_VPSMonitorBot"
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统部署脚本 v2.1.0

用法: $0 [选项]

选项:
  -h, --help              显示此帮助信息
  -m, --mode MODE         部署模式 (local|systemd|docker)
  -u, --user USER         应用用户名 (默认: vpsmonitor)
  -d, --dir DIR           安装目录 (默认: /opt/vps-monitor)
  -s, --skip-deps         跳过系统依赖安装
  -f, --force             强制重新安装
  --no-backup             不设置自动备份
  --no-firewall           不配置防火墙
  --no-nginx              不设置Nginx

部署模式:
  local       本地部署 (默认)
  systemd     使用systemd服务
  docker      使用Docker容器
  
示例:
  $0 --mode systemd              # 使用systemd服务部署
  $0 --mode docker --skip-deps   # 使用Docker部署，跳过依赖安装
  $0 --force                     # 强制重新安装

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
                DEPLOY_MODE="$2"
                shift 2
                ;;
            -u|--user)
                APP_USER="$2"
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
            -f|--force)
                FORCE_REINSTALL=true
                shift
                ;;
            --no-backup)
                SETUP_BACKUP=false
                shift
                ;;
            --no-firewall)
                SETUP_FIREWALL=false
                shift
                ;;
            --no-nginx)
                SETUP_NGINX=false
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 设置默认值
    DEPLOY_MODE=${DEPLOY_MODE:-"local"}
    SETUP_BACKUP=${SETUP_BACKUP:-true}
    SETUP_FIREWALL=${SETUP_FIREWALL:-true}
    SETUP_NGINX=${SETUP_NGINX:-false}
    
    # 根据部署模式设置标志
    case $DEPLOY_MODE in
        systemd)
            USE_SYSTEMD=true
            ;;
        docker)
            USE_DOCKER=true
            ;;
        local)
            # 默认模式
            ;;
        *)
            error_exit "无效的部署模式: $DEPLOY_MODE"
            ;;
    esac
}

# 主部署函数
main_deploy() {
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
    
    log_info "开始部署 VPS监控系统 v2.1.0"
    log_info "部署模式: $DEPLOY_MODE"
    log_info "安装目录: $INSTALL_DIR"
    log_info "应用用户: $APP_USER"
    
    # 检查系统权限
    if [[ "$USE_SYSTEMD" == true ]] || [[ "$SETUP_FIREWALL" == true ]] || [[ "$SETUP_NGINX" == true ]]; then
        if ! check_root; then
            error_exit "部分功能需要root权限，请使用sudo运行"
        fi
    fi
    
    # 检查现有安装
    if [[ -d "$INSTALL_DIR" ]] && [[ "$FORCE_REINSTALL" != true ]]; then
        echo -e "${YELLOW}检测到现有安装，是否继续? [y/N] ${NC}"
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_info "部署已取消"
            exit 0
        fi
    fi
    
    # 执行部署步骤
    [[ "$SKIP_DEPS" != true ]] && install_system_dependencies
    create_app_user
    create_directories
    deploy_application
    setup_python_environment
    generate_config
    
    # 根据部署模式执行特定步骤
    if [[ "$USE_DOCKER" == true ]]; then
        setup_docker_environment
    elif [[ "$USE_SYSTEMD" == true ]]; then
        setup_systemd_service
    fi
    
    # 可选功能
    [[ "$SETUP_NGINX" == true ]] && setup_nginx
    [[ "$SETUP_BACKUP" == true ]] && setup_backup_cron
    [[ "$SETUP_FIREWALL" == true ]] && setup_firewall
    
    # 安全加固
    security_hardening
    
    # 验证部署
    if verify_deployment; then
        show_post_deploy_info
    else
        error_exit "部署验证失败"
    fi
}

# 主函数
main() {
    # 设置错误处理
    trap 'log_error "部署过程中发生错误，行号: $LINENO"; exit 1' ERR
    
    # 解析参数
    parse_arguments "$@"
    
    # 开始部署
    main_deploy
}

# 运行主函数
main "$@"
