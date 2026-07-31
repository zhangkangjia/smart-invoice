#!/bin/bash
#=============================================================
# 智能开票平台 - 一键部署脚本
# 用法:
#   ./deploy.sh          - 全流程：停止→拉代码→启动（日常更新用）
#   ./deploy.sh restart  - 仅重启容器（不拉代码，最快）
#   ./deploy.sh rebuild  - 清除依赖缓存重新安装（改了requirements.txt用）
#   ./deploy.sh stop     - 停止所有服务
#   ./deploy.sh logs     - 查看日志（可指定服务名）
#   ./deploy.sh status   - 查看状态
#=============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}[ERROR]${NC} 未找到 docker-compose，请先安装"; exit 1
fi

stop_services() {
    log_step "停止所有服务..."
    $COMPOSE_CMD down --remove-orphans
    log_info "服务已停止"
}

pull_code() {
    log_step "拉取最新代码..."
    local branch=$(git rev-parse --abbrev-ref HEAD)
    log_info "当前分支: $branch"

    # 设置 git 超时（10秒内没数据就放弃）
    export GIT_HTTP_LOW_SPEED_LIMIT=1000
    export GIT_HTTP_LOW_SPEED_TIME=10
    export GIT_SSH_COMMAND="ssh -o ConnectTimeout=10 -o ServerAliveInterval=5"

    local max_retry=3 retry=0

    while [ $retry -lt $max_retry ]; do
        retry=$((retry + 1))
        log_info "拉取代码中... (第 $retry/$max_retry 次, 超时30秒)"

        # 用 timeout 命令确保不会卡死
        if timeout 30 git fetch origin 2>/dev/null; then
            git reset --hard origin/"$branch"
            log_info "代码已更新"
            git log --oneline -3
            return 0
        fi

        log_warn "拉取失败或超时"

        # 检测 GITEE 镜像（优先用 Gitee，国内最稳定）
        local remote_url=$(git remote get-url origin)
        if echo "$remote_url" | grep -q "github.com"; then
            log_warn "GitHub 不稳定，尝试切换到 Gitee 镜像..."
            local repo_path=$(echo "$remote_url" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
            local gitee_url="https://gitee.com/${repo_path}.git"
            log_info "尝试: $gitee_url"
            if timeout 20 git ls-remote "$gitee_url" HEAD >/dev/null 2>&1; then
                git remote set-url origin "$gitee_url"
                log_info "已切换为 Gitee: $gitee_url"
                retry=0
                continue
            else
                log_warn "Gitee 镜像不可用或未配置"
            fi
        fi

        sleep 2
    done

    log_error "拉取代码失败（GitHub不稳定）"
    log_error ""
    log_error "解决方案："
    log_error "  1. 用 Gitee 镜像（推荐）："
    log_error "     a. 在 https://gitee.com/projects/import/url 导入 GitHub 仓库"
    log_error "     b. 手动切换: git remote set-url origin https://gitee.com/你的用户名/smart-invoice.git"
    log_error "     c. 重新执行: ./deploy.sh"
    log_error ""
    log_error "  2. 手动拉取（直接 Ctrl+C 后操作）:"
    log_error "     git fetch origin && git reset --hard origin/main"
    log_error ""
    log_error "  3. 跳过代码更新，直接启动已有代码:"
    log_error "     ./deploy.sh restart"
    exit 1
}

start_services() {
    log_step "启动服务..."
    $COMPOSE_CMD up -d
    log_info "服务已启动"
}

wait_for_ready() {
    log_step "等待服务启动..."
    local max_wait=180 waited=0
    while [ $waited -lt $max_wait ]; do
        local containers=$($COMPOSE_CMD ps -q 2>/dev/null | wc -l)
        local running=$($COMPOSE_CMD ps --filter "status=running" -q 2>/dev/null | wc -l)
        if [ "$containers" -gt 0 ] && [ "$containers" -eq "$running" ]; then
            sleep 3
            log_info "所有服务已就绪"
            return 0
        fi
        sleep 3; waited=$((waited + 3)); printf "."
    done
    echo ""
    log_warn "部分服务可能还在启动中，请稍后检查状态"
}

show_status() {
    echo ""
    log_step "服务状态:"
    $COMPOSE_CMD ps
    echo ""
    log_step "访问地址:"
    echo -e "  ${CYAN}前端${NC}:       http://localhost:3000"
    echo -e "  ${CYAN}后端API${NC}:    http://localhost:8000/docs"
    echo -e "  ${CYAN}RabbitMQ${NC}:   http://localhost:15672  (smartinvoice/smartinvoice123)"
    echo -e "  ${CYAN}MinIO${NC}:      http://localhost:9001      (smartinvoice/smartinvoice123)"
}

#====================== 主流程 ======================#
ACTION=${1:-pull}

echo ""
echo "========================================"
echo "  智能开票平台 - 部署工具"
echo "  操作: $ACTION"
echo "========================================"
echo ""

case $ACTION in
    pull|"")
        # 先拉代码，成功后再停服务（避免停了服务但代码拉不下来）
        pull_code
        stop_services
        start_services
        wait_for_ready
        show_status
        ;;
    restart)
        $COMPOSE_CMD restart
        wait_for_ready
        show_status
        ;;
    rebuild)
        stop_services
        pull_code
        log_step "清除后端依赖缓存..."
        docker volume rm smart-invoice_si-backend-venv 2>/dev/null || true
        log_step "重新构建前端镜像..."
        $COMPOSE_CMD build --no-cache frontend
        start_services
        wait_for_ready
        show_status
        log_warn "首次启动需安装依赖，请耐心等待1-2分钟"
        ;;
    stop)
        stop_services
        ;;
    logs)
        $COMPOSE_CMD logs -f --tail=100 ${2:-}
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 [pull|restart|rebuild|stop|logs [service]|status]"
        echo ""
        echo "  pull    - 停止→拉代码→启动（日常更新，秒级）"
        echo "  restart - 仅重启容器（不拉代码，最快）"
        echo "  rebuild - 清除依赖缓存重新安装（改了requirements.txt用）"
        echo "  stop    - 停止所有服务"
        echo "  logs    - 查看日志"
        echo "  status  = 查看状态"
        exit 1
        ;;
esac

echo ""
log_info "完成！"
