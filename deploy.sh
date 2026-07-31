#!/bin/bash
#=============================================================
# 智能开票平台 - 一键部署脚本
# 用法:
#   ./deploy.sh          - 全流程：停止→拉代码→构建→启动→健康检查
#   ./deploy.sh pull     - 同上（默认）
#   ./deploy.sh restart  - 仅重启
#   ./deploy.sh stop     - 停止所有服务
#   ./deploy.sh logs     - 查看日志
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
    git fetch origin
    git reset --hard origin/"$branch"
    log_info "代码已更新"
    git log --oneline -3
}

build_and_start() {
    log_step "构建镜像并启动服务..."
    $COMPOSE_CMD up -d --build
    log_info "服务已启动"
}

wait_for_healthy() {
    log_step "等待服务启动..."
    local max_wait=120 waited=0
    while [ $waited -lt $max_wait ]; do
        local unhealthy=$($COMPOSE_CMD ps 2>/dev/null | grep -c "unhealthy" || true)
        local starting=$($COMPOSE_CMD ps 2>/dev/null | grep -cE "(starting|created)" || true)
        if [ "$unhealthy" -eq 0 ] && [ "$starting" -eq 0 ]; then
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

show_logs() {
    $COMPOSE_CMD logs -f --tail=100 ${2:-}
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
        stop_services
        pull_code
        build_and_start
        wait_for_healthy
        show_status
        ;;
    restart)
        $COMPOSE_CMD restart
        wait_for_healthy
        show_status
        ;;
    stop)
        stop_services
        ;;
    logs)
        show_logs "$@"
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 [pull|restart|stop|logs [service]|status]"
        echo "  不带参数 = 全流程：停止→拉代码→构建→启动"
        exit 1
        ;;
esac

echo ""
log_info "完成！"
