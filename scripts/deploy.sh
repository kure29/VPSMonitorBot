#!/bin/bash
# VPS监控系统 v1.0 - 部署脚本
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

# 配置变量
readonly VERSION="1.0.0"
readonly AUTHOR="kure29"
readonly WEBSITE="https://kure29.com"
readonly SERVICE_NAME="vps-monitor"
readonly SERVICE_USER="vpsmonitor"
readonly INSTALL_DIR="/opt/vps-monitor"

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
    echo -e "${PURPLE}VPS库存监控系统 v${VERSION} 部署脚本${NC}"
    echo -e "${CYAN}作者: ${AUTHOR} | 网站: ${WEBSITE}${NC}"
    echo ""
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统 v${VERSION} 部署脚本

用法: $0 [选项]

选项:
    -h, --help          显示此帮助信息
    -v, --version       显示版本信息
    --mode <模式>       部署模式: systemd|docker|local (默认: systemd)
    --user <用户>       运行用户 (默认: ${SERVICE_USER})
    --dir <目录>        安装目录 (默认: ${INSTALL_DIR})
    --port <端口>       Web端口 (默认: 8000)
    --domain <域名>     配置域名 (用于Nginx)
    --ssl               启用SSL (需要域名)
    --backup            部署前备份现有配置
    --update            更新现有安装
    --uninstall         卸载服务

部署模式:
    systemd     作为系统服务部署 (推荐生产环境)
    docker      使用Docker容器部署
    local       本地用户模式部署

示例:
    $0                                  # 默认systemd部署
    $0 --mode docker                    # Docker部署
    $0 --mode systemd --user monitor    # 指定用户
    $0 --domain monitor.example.com --ssl  # 配置域名和SSL
    $0 --backup --update                # 备份并更新
    $0 --uninstall                      # 卸载

EOF
}

# 检查权限
check_permissions() {
    if [[ $EUID -ne 0 ]] && [[ "$DEPLOY_MODE" == "systemd" ]]; then
        log_error "系统服务模式需要root权限，请使用sudo运行"
        exit 1
    fi
}

# 检查系统要求
check_requirements() {
    log_info "检查系统要求"
    
    # 检查Python
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "未找到Python3，请先安装"
        exit 1
    fi
    
    # 检查Git
    if ! command -v git >/dev/null 2>&1; then
        log_warn "未找到Git，某些功能可能受限"
    fi
    
    # 检查systemctl (用于systemd模式)
    if [[ "$DEPLOY_MODE" == "systemd" ]] && ! command -v systemctl >/dev/null 2>&1; then
        log_error "systemd模式需要systemctl支持"
        exit 1
    fi
    
    # 检查Docker (用于docker模式)
    if [[ "$DEPLOY_MODE" == "docker" ]] && ! command -v docker >/dev/null 2>&1; then
        log_error "Docker模式需要Docker支持"
        exit 1
    fi
    
    log_info "系统要求检查完成"
}

# 创建用户
create_user() {
    if [[ "$DEPLOY_MODE" == "systemd" ]] && [[ "$SERVICE_USER" != "root" ]]; then
        if ! id "$SERVICE_USER" &>/dev/null; then
            log_info "创建用户: $SERVICE_USER"
            useradd --system --shell /bin/bash --home-dir "$INSTALL_DIR" \
                    --create-home "$SERVICE_USER"
        else
            log_info "用户已存在: $SERVICE_USER"
        fi
    fi
}

# 备份现有配置
backup_config() {
    if [[ "$BACKUP_CONFIG" == true ]] && [[ -d "$INSTALL_DIR" ]]; then
        local backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "备份现有配置到: $backup_dir"
        
        # 备份重要文件
        mkdir -p "$backup_dir"
        for file in config.json urls.json monitor.log; do
            if [[ -f "$INSTALL_DIR/$file" ]]; then
                cp "$INSTALL_DIR/$file" "$backup_dir/"
                log_debug "备份文件: $file"
            fi
        done
        
        # 备份目录
        for dir in data logs backup; do
            if [[ -d "$INSTALL_DIR/$dir" ]]; then
                cp -r "$INSTALL_DIR/$dir" "$backup_dir/"
                log_debug "备份目录: $dir"
            fi
        done
        
        log_info "配置备份完成"
    fi
}

# 部署文件
deploy_files() {
    log_info "部署文件到: $INSTALL_DIR"
    
    # 创建安装目录
    mkdir -p "$INSTALL_DIR"
    
    # 复制文件
    if [[ "$UPDATE_MODE" == true ]] && [[ -d "$INSTALL_DIR" ]]; then
        # 更新模式：只复制核心文件
        log_info "更新模式：保留现有配置"
        
        # 备份配置文件
        local temp_config="/tmp/vps-monitor-config.json"
        local temp_urls="/tmp/vps-monitor-urls.json"
        
        [[ -f "$INSTALL_DIR/config.json" ]] && cp "$INSTALL_DIR/config.json" "$temp_config"
        [[ -f "$INSTALL_DIR/urls.json" ]] && cp "$INSTALL_DIR/urls.json" "$temp_urls"
        
        # 复制新文件
        cp -r src scripts requirements.txt setup.py "$INSTALL_DIR/"
        
        # 恢复配置文件
        [[ -f "$temp_config" ]] && cp "$temp_config" "$INSTALL_DIR/config.json"
        [[ -f "$temp_urls" ]] && cp "$temp_urls" "$INSTALL_DIR/urls.json"
        
        # 清理临时文件
        rm -f "$temp_config" "$temp_urls"
    else
        # 全新安装
        log_info "全新安装模式"
        cp -r * "$INSTALL_DIR/" 2>/dev/null || true
    fi
    
    # 创建必要目录
    mkdir -p "$INSTALL_DIR"/{data,logs,backup}
    
    # 设置权限
    if [[ "$SERVICE_USER" != "root" ]]; then
        chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    fi
    
    chmod +x "$INSTALL_DIR/scripts"/*.sh
    
    log_info "文件部署完成"
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖"
    
    cd "$INSTALL_DIR"
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        if [[ "$SERVICE_USER" == "root" ]]; then
            python3 -m venv venv
        else
            sudo -u "$SERVICE_USER" python3 -m venv venv
        fi
    fi
    
    # 激活虚拟环境并安装依赖
    local install_cmd="source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
    
    if [[ "$SERVICE_USER" == "root" ]]; then
        bash -c "$install_cmd"
    else
        sudo -u "$SERVICE_USER" bash -c "$install_cmd"
    fi
    
    log_info "依赖安装完成"
}

# 配置systemd服务
setup_systemd_service() {
    log_info "配置systemd服务"
    
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=VPS Monitor v${VERSION}
Documentation=${WEBSITE}
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/monitor.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR
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
    systemctl enable "$SERVICE_NAME"
    
    log_info "systemd服务配置完成"
}

# 配置Docker
setup_docker() {
    log_info "配置Docker环境"
    
    cd "$INSTALL_DIR"
    
    # 构建镜像
    docker build -t "vps-monitor:v${VERSION}" .
    
    # 创建docker-compose override文件
    if [[ -n "$WEB_PORT" ]]; then
        cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  vps-monitor:
    ports:
      - "${WEB_PORT}:8000"
EOF
    fi
    
    log_info "Docker配置完成"
}

# 配置Nginx (可选)
setup_nginx() {
    if [[ -n "$DOMAIN" ]]; then
        log_info "配置Nginx"
        
        local nginx_config="/etc/nginx/sites-available/$SERVICE_NAME"
        local ssl_config=""
        
        if [[ "$ENABLE_SSL" == true ]]; then
            ssl_config="
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    add_header Strict-Transport-Security \"max-age=63072000\" always;"
        fi
        
        cat > "$nginx_config" << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    
    $ssl_config
    
    location / {
        proxy_pass http://127.0.0.1:${WEB_PORT:-8000};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias $INSTALL_DIR/web/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
        
        # 启用站点
        ln -sf "$nginx_config" "/etc/nginx/sites-enabled/"
        
        # 测试Nginx配置
        if nginx -t 2>/dev/null; then
            systemctl reload nginx
            log_info "Nginx配置完成"
        else
            log_error "Nginx配置测试失败"
        fi
    fi
}

# 生成配置文件
generate_config() {
    log_info "生成配置文件"
    
    cd "$INSTALL_DIR"
    
    if [[ ! -f "config.json" ]]; then
        if [[ -f "config/config.json.example" ]]; then
            cp config/config.json.example config.json
        else
            cat > config.json << 'EOF'
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "check_interval": 300,
    "max_notifications": 3,
    "request_timeout": 30,
    "retry_delay": 60
}
EOF
        fi
        
        # 设置权限
        if [[ "$SERVICE_USER" != "root" ]]; then
            chown "$SERVICE_USER:$SERVICE_USER" config.json
        fi
        chmod 600 config.json
        
        log_warn "请编辑 $INSTALL_DIR/config.json 配置Telegram信息"
    else
        log_info "配置文件已存在，跳过生成"
    fi
}

# 启动服务
start_service() {
    log_info "启动服务"
    
    case $DEPLOY_MODE in
        systemd)
            systemctl start "$SERVICE_NAME"
            if systemctl is-active --quiet "$SERVICE_NAME"; then
                log_info "systemd服务启动成功"
            else
                log_error "systemd服务启动失败"
                systemctl status "$SERVICE_NAME"
                return 1
            fi
            ;;
        docker)
            cd "$INSTALL_DIR"
            docker-compose up -d
            if docker-compose ps | grep -q "Up"; then
                log_info "Docker服务启动成功"
            else
                log_error "Docker服务启动失败"
                docker-compose logs
                return 1
            fi
            ;;
        local)
            log_info "本地模式，请手动启动服务"
            log_info "启动命令: cd $INSTALL_DIR && ./scripts/menu.sh"
            ;;
    esac
}

# 卸载服务
uninstall_service() {
    log_info "卸载VPS监控服务"
    
    # 停止服务
    case $DEPLOY_MODE in
        systemd)
            if systemctl is-active --quiet "$SERVICE_NAME"; then
                systemctl stop "$SERVICE_NAME"
            fi
            systemctl disable "$SERVICE_NAME" 2>/dev/null || true
            rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
            systemctl daemon-reload
            ;;
        docker)
            if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
                cd "$INSTALL_DIR"
                docker-compose down
                docker rmi "vps-monitor:v${VERSION}" 2>/dev/null || true
            fi
            ;;
    esac
    
    # 询问是否删除文件
    echo -n "是否删除安装目录 $INSTALL_DIR ? [y/N] "
    read -r confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        log_info "安装目录已删除"
    fi
    
    # 询问是否删除用户
    if [[ "$SERVICE_USER" != "root" ]] && id "$SERVICE_USER" &>/dev/null; then
        echo -n "是否删除用户 $SERVICE_USER ? [y/N] "
        read -r confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            userdel "$SERVICE_USER" 2>/dev/null || true
            log_info "用户已删除"
        fi
    fi
    
    log_info "卸载完成"
}

# 显示部署后信息
show_post_deploy_info() {
    echo ""
    log_info "部署完成！"
    echo ""
    echo "📁 安装目录: $INSTALL_DIR"
    echo "👤 运行用户: $SERVICE_USER"
    echo "📄 配置文件: $INSTALL_DIR/config.json"
    echo "📋 日志文件: $INSTALL_DIR/monitor.log"
    echo ""
    
    case $DEPLOY_MODE in
        systemd)
            echo "🚀 服务管理:"
            echo "   启动: systemctl start $SERVICE_NAME"
            echo "   停止: systemctl stop $SERVICE_NAME"
            echo "   重启: systemctl restart $SERVICE_NAME"
            echo "   状态: systemctl status $SERVICE_NAME"
            echo "   日志: journalctl -u $SERVICE_NAME -f"
            ;;
        docker)
            echo "🚀 Docker管理:"
            echo "   启动: cd $INSTALL_DIR && docker-compose up -d"
            echo "   停止: cd $INSTALL_DIR && docker-compose down"
            echo "   重启: cd $INSTALL_DIR && docker-compose restart"
            echo "   日志: cd $INSTALL_DIR && docker-compose logs -f"
            ;;
        local)
            echo "🚀 本地管理:"
            echo "   启动: cd $INSTALL_DIR && ./scripts/menu.sh"
            echo "   配置: cd $INSTALL_DIR && ./scripts/menu.sh"
            ;;
    esac
    
    if [[ -n "$DOMAIN" ]]; then
        echo ""
        echo "🌐 Web访问:"
        if [[ "$ENABLE_SSL" == true ]]; then
            echo "   HTTPS: https://$DOMAIN"
        else
            echo "   HTTP:  http://$DOMAIN"
        fi
    fi
    
    echo ""
    echo "📝 下一步:"
    echo "1. 编辑配置文件设置Telegram信息"
    echo "   nano $INSTALL_DIR/config.json"
    echo "2. 重启服务使配置生效"
    echo "3. 使用Telegram Bot添加监控商品"
    echo ""
    echo "❓ 获取帮助:"
    echo "   作者: $AUTHOR"
    echo "   网站: $WEBSITE"
}

# 主部署函数
main_deploy() {
    local DEPLOY_MODE="systemd"
    local BACKUP_CONFIG=false
    local UPDATE_MODE=false
    local UNINSTALL_MODE=false
    local WEB_PORT=""
    local DOMAIN=""
    local ENABLE_SSL=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "VPS监控系统部署脚本 v${VERSION}"
                exit 0
                ;;
            --mode)
                DEPLOY_MODE="$2"
                shift 2
                ;;
            --user)
                SERVICE_USER="$2"
                shift 2
                ;;
            --dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --port)
                WEB_PORT="$2"
                shift 2
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --ssl)
                ENABLE_SSL=true
                shift
                ;;
            --backup)
                BACKUP_CONFIG=true
                shift
                ;;
            --update)
                UPDATE_MODE=true
                shift
                ;;
            --uninstall)
                UNINSTALL_MODE=true
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
    
    # 卸载模式
    if [[ "$UNINSTALL_MODE" == true ]]; then
        uninstall_service
        exit 0
    fi
    
    log_info "开始部署 VPS监控系统 v${VERSION}"
    log_info "部署模式: $DEPLOY_MODE"
    log_info "安装目录: $INSTALL_DIR"
    log_info "运行用户: $SERVICE_USER"
    
    # 检查权限和要求
    check_permissions
    check_requirements
    
    # 备份配置
    backup_config
    
    # 创建用户
    create_user
    
    # 部署文件
    deploy_files
    
    # 安装依赖
    install_dependencies
    
    # 生成配置
    generate_config
    
    # 根据模式进行配置
    case $DEPLOY_MODE in
        systemd)
            setup_systemd_service
            ;;
        docker)
            setup_docker
            ;;
        local)
            log_info "本地模式，跳过服务配置"
            ;;
        *)
            log_error "未知部署模式: $DEPLOY_MODE"
            exit 1
            ;;
    esac
    
    # 配置Nginx (如果指定了域名)
    setup_nginx
    
    # 启动服务
    start_service
    
    # 显示部署后信息
    show_post_deploy_info
}

# 错误处理
error_handler() {
    local line_number=$1
    log_error "部署过程中发生错误 (行号: $line_number)"
    log_error "请检查错误信息并重试"
    exit 1
}

# 设置错误处理
trap 'error_handler $LINENO' ERR

# 主函数
main() {
    main_deploy "$@"
}

# 运行主函数
main "$@"
