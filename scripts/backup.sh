#!/bin/bash
# VPS监控系统 v1.0 - 备份脚本
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
readonly BACKUP_DIR="backup"
readonly RETENTION_DAYS=30
readonly COMPRESS=true

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
    echo -e "${PURPLE}VPS监控系统 v${VERSION} 备份工具${NC}"
    echo ""
}

# 显示帮助信息
show_help() {
    cat << EOF
VPS监控系统备份工具

用法: $0 [选项] [操作]

操作:
    backup      创建备份 (默认)
    restore     恢复备份
    list        列出备份
    clean       清理旧备份
    verify      验证备份

选项:
    -h, --help          显示此帮助信息
    -v, --version       显示版本信息
    -d, --dir <目录>    备份目录 (默认: $BACKUP_DIR)
    -r, --retention <天数>  保留天数 (默认: $RETENTION_DAYS)
    -c, --compress      压缩备份 (默认启用)
    --no-compress       不压缩备份
    -f, --file <文件>   指定备份文件 (用于恢复)
    --include <模式>    包含文件模式
    --exclude <模式>    排除文件模式
    --remote <URL>      远程备份位置
    --encrypt           加密备份
    --password <密码>   加密密码

示例:
    $0                                  # 创建备份
    $0 backup                           # 创建备份
    $0 restore -f backup_20240101.tar.gz  # 恢复指定备份
    $0 list                             # 列出所有备份
    $0 clean                            # 清理旧备份
    $0 backup --remote ftp://backup.com  # 远程备份

EOF
}

# 创建备份目录
create_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
        log_info "创建备份目录: $BACKUP_DIR"
    fi
}

# 生成备份文件名
generate_backup_name() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local hostname=$(hostname -s)
    echo "vps-monitor_${hostname}_${timestamp}"
}

# 创建备份
create_backup() {
    local backup_name="$1"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    log_info "开始创建备份: $backup_name"
    
    # 要备份的文件和目录
    local backup_items=(
        "config.json"
        "urls.json"
        "data"
        "logs"
    )
    
    # 检查要备份的项目
    local existing_items=()
    for item in "${backup_items[@]}"; do
        if [[ -e "$item" ]]; then
            existing_items+=("$item")
        else
            log_warn "备份项目不存在，跳过: $item"
        fi
    done
    
    if [[ ${#existing_items[@]} -eq 0 ]]; then
        log_error "没有找到可备份的项目"
        return 1
    fi
    
    # 创建备份信息文件
    local info_file="/tmp/backup_info.txt"
    cat > "$info_file" << EOF
VPS监控系统备份信息
===================
备份时间: $(date)
备份版本: v${VERSION}
主机名: $(hostname)
用户: $(whoami)
工作目录: $(pwd)
备份项目: ${existing_items[*]}

系统信息:
---------
操作系统: $(uname -s)
内核版本: $(uname -r)
架构: $(uname -m)

Python信息:
-----------
$(python3 --version 2>/dev/null || echo "Python未找到")

磁盘使用:
---------
$(df -h . 2>/dev/null || echo "磁盘信息获取失败")
EOF
    
    # 创建备份
    if [[ "$COMPRESS" == true ]]; then
        log_info "创建压缩备份..."
        tar -czf "${backup_path}.tar.gz" "${existing_items[@]}" -C /tmp backup_info.txt \
            --transform 's|^backup_info.txt|backup_info.txt|' 2>/dev/null || {
            log_error "创建压缩备份失败"
            rm -f "$info_file"
            return 1
        }
        backup_path="${backup_path}.tar.gz"
    else
        log_info "创建非压缩备份..."
        tar -cf "${backup_path}.tar" "${existing_items[@]}" -C /tmp backup_info.txt \
            --transform 's|^backup_info.txt|backup_info.txt|' 2>/dev/null || {
            log_error "创建备份失败"
            rm -f "$info_file"
            return 1
        }
        backup_path="${backup_path}.tar"
    fi
    
    # 清理临时文件
    rm -f "$info_file"
    
    # 验证备份
    if [[ -f "$backup_path" ]]; then
        local backup_size=$(du -h "$backup_path" | cut -f1)
        log_info "备份创建成功: $backup_path ($backup_size)"
        
        # 计算校验和
        if command -v sha256sum >/dev/null 2>&1; then
            local checksum=$(sha256sum "$backup_path" | cut -d' ' -f1)
            echo "$checksum" > "${backup_path}.sha256"
            log_debug "校验和: $checksum"
        fi
        
        # 加密备份 (如果启用)
        if [[ "$ENCRYPT_BACKUP" == true ]]; then
            encrypt_backup "$backup_path"
        fi
        
        # 上传到远程 (如果配置)
        if [[ -n "$REMOTE_URL" ]]; then
            upload_backup "$backup_path"
        fi
        
        return 0
    else
        log_error "备份文件创建失败"
        return 1
    fi
}

# 加密备份
encrypt_backup() {
    local backup_file="$1"
    
    if ! command -v gpg >/dev/null 2>&1; then
        log_error "未找到gpg，无法加密备份"
        return 1
    fi
    
    log_info "加密备份文件..."
    
    if [[ -n "$BACKUP_PASSWORD" ]]; then
        # 使用密码加密
        gpg --batch --yes --passphrase "$BACKUP_PASSWORD" \
            --symmetric --cipher-algo AES256 \
            --output "${backup_file}.gpg" "$backup_file"
        
        if [[ -f "${backup_file}.gpg" ]]; then
            rm -f "$backup_file"
            log_info "备份已加密: ${backup_file}.gpg"
        else
            log_error "备份加密失败"
            return 1
        fi
    else
        log_error "未设置加密密码"
        return 1
    fi
}

# 上传备份到远程
upload_backup() {
    local backup_file="$1"
    
    log_info "上传备份到远程: $REMOTE_URL"
    
    case "$REMOTE_URL" in
        ftp://*)
            if command -v curl >/dev/null 2>&1; then
                curl -T "$backup_file" "$REMOTE_URL/$(basename "$backup_file")" || {
                    log_error "FTP上传失败"
                    return 1
                }
            else
                log_error "未找到curl，无法上传"
                return 1
            fi
            ;;
        sftp://*)
            if command -v sftp >/dev/null 2>&1; then
                echo "put $backup_file" | sftp "$REMOTE_URL" || {
                    log_error "SFTP上传失败"
                    return 1
                }
            else
                log_error "未找到sftp，无法上传"
                return 1
            fi
            ;;
        *)
            log_error "不支持的远程URL格式: $REMOTE_URL"
            return 1
            ;;
    esac
    
    log_info "远程上传完成"
}

# 列出备份
list_backups() {
    log_info "备份列表"
    echo "============"
    
    if [[ ! -d "$BACKUP_DIR" ]] || [[ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]]; then
        log_warn "没有找到备份文件"
        return 1
    fi
    
    echo "备份目录: $BACKUP_DIR"
    echo ""
    
    # 列出备份文件
    local count=0
    for backup_file in "$BACKUP_DIR"/*.tar.gz "$BACKUP_DIR"/*.tar "$BACKUP_DIR"/*.gpg; do
        if [[ -f "$backup_file" ]]; then
            count=$((count + 1))
            local size=$(du -h "$backup_file" | cut -f1)
            local date=$(stat -c %y "$backup_file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
            
            echo "[$count] $(basename "$backup_file")"
            echo "    大小: $size"
            echo "    时间: $date"
            
            # 显示校验和 (如果存在)
            local checksum_file="${backup_file}.sha256"
            if [[ -f "$checksum_file" ]]; then
                local checksum=$(cat "$checksum_file")
                echo "    校验: ${checksum:0:16}..."
            fi
            echo ""
        fi
    done
    
    if [[ $count -eq 0 ]]; then
        log_warn "没有找到有效的备份文件"
        return 1
    fi
    
    echo "总计: $count 个备份文件"
}

# 恢复备份
restore_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        log_error "请指定要恢复的备份文件"
        return 1
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        # 尝试在备份目录中查找
        if [[ -f "$BACKUP_DIR/$backup_file" ]]; then
            backup_file="$BACKUP_DIR/$backup_file"
        else
            log_error "备份文件不存在: $backup_file"
            return 1
        fi
    fi
    
    log_info "恢复备份: $backup_file"
    
    # 验证校验和 (如果存在)
    local checksum_file="${backup_file}.sha256"
    if [[ -f "$checksum_file" ]] && command -v sha256sum >/dev/null 2>&1; then
        log_info "验证备份完整性..."
        if sha256sum -c "$checksum_file" >/dev/null 2>&1; then
            log_info "备份完整性验证通过"
        else
            log_error "备份完整性验证失败"
            echo -n "是否继续恢复? [y/N] "
            read -r confirm
            if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
                return 1
            fi
        fi
    fi
    
    # 解密备份 (如果需要)
    local actual_backup_file="$backup_file"
    if [[ "$backup_file" == *.gpg ]]; then
        log_info "解密备份文件..."
        if [[ -n "$BACKUP_PASSWORD" ]]; then
            local decrypted_file="${backup_file%.gpg}"
            gpg --batch --yes --passphrase "$BACKUP_PASSWORD" \
                --decrypt --output "$decrypted_file" "$backup_file" || {
                log_error "备份解密失败"
                return 1
            }
            actual_backup_file="$decrypted_file"
        else
            log_error "需要密码来解密备份"
            return 1
        fi
    fi
    
    # 备份当前配置 (如果存在)
    local current_backup_dir="backup_before_restore_$(date +%Y%m%d_%H%M%S)"
    if [[ -f "config.json" ]] || [[ -f "urls.json" ]] || [[ -d "data" ]]; then
        log_info "备份当前配置到: $current_backup_dir"
        mkdir -p "$current_backup_dir"
        
        for item in config.json urls.json data logs; do
            if [[ -e "$item" ]]; then
                cp -r "$item" "$current_backup_dir/"
            fi
        done
    fi
    
    # 停止监控服务
    log_info "停止监控服务..."
    local service_was_running=false
    if pgrep -f "python3.*monitor.py" >/dev/null; then
        service_was_running=true
        pkill -f "python3.*monitor.py" || true
        sleep 2
    fi
    
    # 恢复备份
    log_info "恢复备份文件..."
    if [[ "$actual_backup_file" == *.tar.gz ]]; then
        tar -xzf "$actual_backup_file" || {
            log_error "解压备份失败"
            return 1
        }
    elif [[ "$actual_backup_file" == *.tar ]]; then
        tar -xf "$actual_backup_file" || {
            log_error "解压备份失败"
            return 1
        }
    else
        log_error "不支持的备份格式"
        return 1
    fi
    
    # 清理解密的临时文件
    if [[ "$backup_file" == *.gpg ]] && [[ "$actual_backup_file" != "$backup_file" ]]; then
        rm -f "$actual_backup_file"
    fi
    
    # 设置正确的权限
    chmod 600 config.json 2>/dev/null || true
    
    log_info "备份恢复完成"
    
    # 重新启动服务 (如果之前在运行)
    if [[ "$service_was_running" == true ]]; then
        log_info "重新启动监控服务..."
        nohup python3 src/monitor.py > monitor.log 2>&1 &
        log_info "监控服务已重新启动"
    fi
    
    # 显示恢复信息
    if [[ -f "backup_info.txt" ]]; then
        echo ""
        log_info "备份信息:"
        cat backup_info.txt
        rm -f backup_info.txt
    fi
}

# 验证备份
verify_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        log_error "请指定要验证的备份文件"
        return 1
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        if [[ -f "$BACKUP_DIR/$backup_file" ]]; then
            backup_file="$BACKUP_DIR/$backup_file"
        else
            log_error "备份文件不存在: $backup_file"
            return 1
        fi
    fi
    
    log_info "验证备份: $backup_file"
    
    # 验证文件完整性
    if [[ "$backup_file" == *.tar.gz ]]; then
        if tar -tzf "$backup_file" >/dev/null 2>&1; then
            log_info "✓ 压缩格式验证通过"
        else
            log_error "✗ 压缩格式验证失败"
            return 1
        fi
    elif [[ "$backup_file" == *.tar ]]; then
        if tar -tf "$backup_file" >/dev/null 2>&1; then
            log_info "✓ 格式验证通过"
        else
            log_error "✗ 格式验证失败"
            return 1
        fi
    fi
    
    # 验证校验和
    local checksum_file="${backup_file}.sha256"
    if [[ -f "$checksum_file" ]] && command -v sha256sum >/dev/null 2>&1; then
        if sha256sum -c "$checksum_file" >/dev/null 2>&1; then
            log_info "✓ 校验和验证通过"
        else
            log_error "✗ 校验和验证失败"
            return 1
        fi
    else
        log_warn "! 没有校验和文件，跳过完整性验证"
    fi
    
    # 列出备份内容
    log_info "备份内容:"
    if [[ "$backup_file" == *.tar.gz ]]; then
        tar -tzf "$backup_file" | head -20
    elif [[ "$backup_file" == *.tar ]]; then
        tar -tf "$backup_file" | head -20
    fi
    
    local file_count
    if [[ "$backup_file" == *.tar.gz ]]; then
        file_count=$(tar -tzf "$backup_file" | wc -l)
    elif [[ "$backup_file" == *.tar ]]; then
        file_count=$(tar -tf "$backup_file" | wc -l)
    fi
    
    log_info "总计 $file_count 个文件/目录"
    log_info "备份验证完成"
}

# 清理旧备份
clean_old_backups() {
    local retention_days="$1"
    retention_days=${retention_days:-$RETENTION_DAYS}
    
    log_info "清理 $retention_days 天前的备份"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_warn "备份目录不存在: $BACKUP_DIR"
        return 0
    fi
    
    local count=0
    local total_size=0
    
    # 查找并删除旧备份
    while IFS= read -r -d '' backup_file; do
        if [[ -f "$backup_file" ]]; then
            local file_age=$(( ($(date +%s) - $(stat -c %Y "$backup_file")) / 86400 ))
            if [[ $file_age -gt $retention_days ]]; then
                local size=$(stat -c %s "$backup_file" 2>/dev/null || echo 0)
                total_size=$((total_size + size))
                count=$((count + 1))
                
                log_debug "删除旧备份: $(basename "$backup_file") (${file_age}天前)"
                rm -f "$backup_file"
                rm -f "${backup_file}.sha256"  # 同时删除校验和文件
            fi
        fi
    done < <(find "$BACKUP_DIR" -name "*.tar.gz" -o -name "*.tar" -o -name "*.gpg" -print0 2>/dev/null)
    
    if [[ $count -gt 0 ]]; then
        local size_mb=$((total_size / 1024 / 1024))
        log_info "清理完成: 删除了 $count 个备份文件，释放 ${size_mb}MB 空间"
    else
        log_info "没有找到需要清理的旧备份"
    fi
}

# 主函数
main() {
    local operation="backup"
    local backup_file=""
    local retention_days="$RETENTION_DAYS"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "VPS监控系统备份工具 v${VERSION}"
                exit 0
                ;;
            -d|--dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            -r|--retention)
                retention_days="$2"
                shift 2
                ;;
            -c|--compress)
                COMPRESS=true
                shift
                ;;
            --no-compress)
                COMPRESS=false
                shift
                ;;
            -f|--file)
                backup_file="$2"
                shift 2
                ;;
            --remote)
                REMOTE_URL="$2"
                shift 2
                ;;
            --encrypt)
                ENCRYPT_BACKUP=true
                shift
                ;;
            --password)
                BACKUP_PASSWORD="$2"
                shift 2
                ;;
            backup|restore|list|clean|verify)
                operation="$1"
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
    
    log_info "执行操作: $operation"
    
    case $operation in
        backup)
            create_backup_dir
            local backup_name=$(generate_backup_name)
            create_backup "$backup_name"
            ;;
        restore)
            restore_backup "$backup_file"
            ;;
        list)
            list_backups
            ;;
        clean)
            clean_old_backups "$retention_days"
            ;;
        verify)
            verify_backup "$backup_file"
            ;;
        *)
            log_error "未知操作: $operation"
            show_help
            exit 1
            ;;
    esac
}

# 错误处理
error_handler() {
    local line_number=$1
    log_error "备份操作失败 (行号: $line_number)"
    exit 1
}

# 设置错误处理
trap 'error_handler $LINENO' ERR

# 运行主函数
main "$@"
