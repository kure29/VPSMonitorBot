#!/bin/bash

# =========================================
# VPS监控系统 - 数据备份脚本
# 作者: kure29
# 版本: v1.0
# 描述: 自动备份监控数据和配置
# =========================================

set -euo pipefail

# 颜色定义
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# 配置变量
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
readonly BACKUP_DIR="${PROJECT_DIR}/backup"
readonly DATE=$(date +%Y%m%d_%H%M%S)
readonly BACKUP_FILE="${BACKUP_DIR}/vps_monitor_${DATE}.tar.gz"
readonly LOG_FILE="${PROJECT_DIR}/logs/backup.log"

# 创建备份目录
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# 日志函数
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log_message "INFO" "$1"
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    log_message "WARN" "$1"
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log_message "ERROR" "$1"
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必需文件
check_files() {
    log_info "检查备份文件..."
    
    local required_files=(
        "$PROJECT_DIR/config.json"
        "$PROJECT_DIR/urls.json"
    )
    
    local missing_files=()
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        log_warn "以下文件不存在，将跳过: ${missing_files[*]}"
    fi
}

# 备份数据库
backup_database() {
    log_info "备份数据库..."
    
    local db_file="$PROJECT_DIR/vps_monitor.db"
    local db_backup="$BACKUP_DIR/database_${DATE}.db"
    
    if [[ -f "$db_file" ]]; then
        cp "$db_file" "$db_backup"
        log_info "数据库备份完成: $db_backup"
    else
        log_warn "数据库文件不存在: $db_file"
    fi
}

# 导出JSON数据
export_json_data() {
    log_info "导出JSON数据..."
    
    local json_backup="$BACKUP_DIR/data_export_${DATE}.json"
    
    # 检查是否有Python环境
    if [[ -f "$PROJECT_DIR/venv/bin/activate" ]]; then
        source "$PROJECT_DIR/venv/bin/activate"
        
        # 尝试使用数据库管理器导出数据
        if python3 -c "import sys; sys.path.append('$PROJECT_DIR/src'); from database_manager import DatabaseManager" 2>/dev/null; then
            python3 << EOF
import sys
import asyncio
sys.path.append('$PROJECT_DIR/src')
from database_manager import DatabaseManager

async def export_data():
    db = DatabaseManager('$PROJECT_DIR/vps_monitor.db')
    if await db.export_to_json('$json_backup'):
        print("JSON数据导出成功")
    else:
        print("JSON数据导出失败")

if __name__ == "__main__":
    asyncio.run(export_data())
EOF
            log_info "JSON数据导出完成: $json_backup"
        else
            log_warn "无法导出JSON数据，跳过"
        fi
    else
        log_warn "Python环境未找到，跳过JSON导出"
    fi
}

# 创建完整备份
create_backup() {
    log_info "创建完整备份..."
    
    cd "$PROJECT_DIR"
    
    # 创建临时文件列表
    local temp_list=$(mktemp)
    
    # 添加需要备份的文件和目录
    {
        # 配置文件
        [[ -f "config.json" ]] && echo "config.json"
        [[ -f "urls.json" ]] && echo "urls.json"
        
        # 数据目录
        [[ -d "data" ]] && echo "data/"
        
        # 数据库文件
        [[ -f "vps_monitor.db" ]] && echo "vps_monitor.db"
        
        # 日志文件（最近的）
        if [[ -d "logs" ]]; then
            find logs -name "*.log" -mtime -7 -type f | head -10
        fi
        
        # 脚本文件
        [[ -d "scripts" ]] && echo "scripts/"
        
        # 源代码（可选）
        [[ -d "src" ]] && echo "src/"
        
        # Web文件（可选）
        [[ -d "web" ]] && echo "web/"
    } > "$temp_list"
    
    # 创建压缩包
    if tar -czf "$BACKUP_FILE" -T "$temp_list" 2>/dev/null; then
        log_info "备份创建成功: $BACKUP_FILE"
        
        # 显示备份文件大小
        local size=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "备份文件大小: $size"
    else
        log_error "备份创建失败"
        rm -f "$temp_list"
        return 1
    fi
    
    rm -f "$temp_list"
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理旧备份文件..."
    
    local retention_days=${BACKUP_RETENTION_DAYS:-30}
    local deleted_count=0
    
    # 删除超过保留期的备份文件
    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "vps_monitor_*.tar.gz" -mtime +"$retention_days" -print0 2>/dev/null)
    
    if [[ $deleted_count -gt 0 ]]; then
        log_info "清理了 $deleted_count 个旧备份文件"
    else
        log_info "没有需要清理的旧备份文件"
    fi
    
    # 显示当前备份文件数量
    local current_count=$(find "$BACKUP_DIR" -name "vps_monitor_*.tar.gz" | wc -l)
    log_info "当前保留备份文件数量: $current_count"
}

# 验证备份
verify_backup() {
    log_info "验证备份文件..."
    
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "备份文件不存在: $BACKUP_FILE"
        return 1
    fi
    
    # 检查压缩包完整性
    if tar -tzf "$BACKUP_FILE" >/dev/null 2>&1; then
        log_info "备份文件验证成功"
        
        # 显示备份内容
        log_info "备份内容："
        tar -tzf "$BACKUP_FILE" | head -20 | sed 's/^/  /'
        
        local file_count=$(tar -tzf "$BACKUP_FILE" | wc -l)
        if [[ $file_count -gt 20 ]]; then
            log_info "  ... 还有 $((file_count - 20)) 个文件"
        fi
    else
        log_error "备份文件验证失败"
        return 1
    fi
}

# 发送备份通知（如果配置了Telegram）
send_notification() {
    log_info "发送备份通知..."
    
    local config_file="$PROJECT_DIR/config.json"
    if [[ -f "$config_file" ]] && command -v jq >/dev/null 2>&1; then
        local bot_token=$(jq -r '.bot_token // empty' "$config_file")
        local chat_id=$(jq -r '.chat_id // empty' "$config_file")
        
        if [[ -n "$bot_token" && -n "$chat_id" ]]; then
            local backup_size=$(du -h "$BACKUP_FILE" | cut -f1)
            local message="🗄️ 数据备份完成

📅 时间: $(date '+%Y-%m-%d %H:%M:%S')
📦 文件: $(basename "$BACKUP_FILE")
💾 大小: $backup_size
📍 位置: $BACKUP_DIR

✅ 备份验证通过"
            
            if curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" \
                -d "chat_id=$chat_id" \
                -d "text=$message" >/dev/null 2>&1; then
                log_info "备份通知发送成功"
            else
                log_warn "备份通知发送失败"
            fi
        else
            log_warn "Telegram配置不完整，跳过通知"
        fi
    else
        log_warn "配置文件不存在或jq未安装，跳过通知"
    fi
}

# 显示使用帮助
show_help() {
    cat << EOF
VPS监控系统数据备份脚本 v2.1.0

用法: $0 [选项]

选项:
  -h, --help          显示此帮助信息
  -q, --quiet         静默模式，只输出错误
  -v, --verbose       详细模式，显示更多信息
  -n, --no-cleanup    不清理旧备份文件
  -t, --test          测试模式，不实际创建备份
  --retention DAYS    备份保留天数 (默认: 30)

示例:
  $0                  # 执行完整备份
  $0 --quiet          # 静默备份
  $0 --retention 7    # 只保留7天的备份

环境变量:
  BACKUP_RETENTION_DAYS    备份保留天数
  BACKUP_DIR              备份目录路径

EOF
}

# 主函数
main() {
    local quiet_mode=false
    local verbose_mode=false
    local no_cleanup=false
    local test_mode=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -q|--quiet)
                quiet_mode=true
                shift
                ;;
            -v|--verbose)
                verbose_mode=true
                shift
                ;;
            -n|--no-cleanup)
                no_cleanup=true
                shift
                ;;
            -t|--test)
                test_mode=true
                shift
                ;;
            --retention)
                export BACKUP_RETENTION_DAYS="$2"
                shift 2
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 设置日志级别
    if [[ "$quiet_mode" == true ]]; then
        exec > /dev/null
    fi
    
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE} VPS监控系统 - 数据备份${NC}"
    echo -e "${BLUE}=========================================${NC}"
    
    log_info "开始备份过程..."
    
    if [[ "$test_mode" == true ]]; then
        log_info "测试模式：不会创建实际备份"
        check_files
        return 0
    fi
    
    # 执行备份流程
    check_files
    backup_database
    export_json_data
    create_backup
    
    if verify_backup; then
        if [[ "$no_cleanup" != true ]]; then
            cleanup_old_backups
        fi
        send_notification
        
        echo -e "\n${GREEN}🎉 备份完成！${NC}"
        echo -e "${BLUE}备份文件: ${NC}$BACKUP_FILE"
        echo -e "${BLUE}备份目录: ${NC}$BACKUP_DIR"
        
        log_info "备份过程完成"
    else
        log_error "备份验证失败，请检查"
        exit 1
    fi
}

# 信号处理
trap 'log_error "备份过程被中断"; exit 130' INT TERM

# 运行主函数
main "$@"
