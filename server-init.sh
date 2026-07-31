#!/bin/bash
#=============================================================
# 服务器初始化脚本 - 配置 GitHub SSH 免密访问
# 用法：在服务器上执行，配置好后可正常部署
#=============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

EMAIL="${1:-2573522468@qq.com}"

echo ""
echo "========================================"
echo "  GitHub SSH 密钥配置"
echo "  邮箱: $EMAIL"
echo "========================================"
echo ""

# 1. 检查是否已存在 SSH key
if [ -f ~/.ssh/id_ed25519 ]; then
    log_warn "已存在 SSH 密钥: ~/.ssh/id_ed25519"
    read -p "是否重新生成？(y/N) " regen
    if [ "$regen" != "y" ] && [ "$regen" != "Y" ]; then
        log_info "跳过生成，使用现有密钥"
    else
        rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
        log_step "生成新的 SSH 密钥..."
        ssh-keygen -t ed25519 -C "$EMAIL" -f ~/.ssh/id_ed25519 -N ""
        log_info "密钥已生成"
    fi
else
    log_step "生成 SSH 密钥..."
    ssh-keygen -t ed25519 -C "$EMAIL" -f ~/.ssh/id_ed25519 -N ""
    log_info "密钥已生成"
fi

# 2. 启动 ssh-agent
log_step "启动 ssh-agent..."
eval "$(ssh-agent -s)" 2>/dev/null

# 3. 添加密钥到 ssh-agent
ssh-add ~/.ssh/id_ed25519 2>/dev/null || true
log_info "密钥已添加到 ssh-agent"

# 4. 配置 SSH 自动添加 known_hosts（避免首次连接确认）
if ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
    log_step "添加 GitHub 到 known_hosts..."
    ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true
fi

# 5. 显示公钥
echo ""
echo "========================================"
echo "  请将以下公钥添加到 GitHub"
echo "========================================"
echo ""
echo -e "${CYAN}公钥内容（复制下面整行）:${NC}"
echo ""
cat ~/.ssh/id_ed25519.pub
echo ""
echo -e "${YELLOW}操作步骤:${NC}"
echo "  1. 打开 https://github.com/settings/keys"
echo "  2. 点击 New SSH key"
echo "  3. Title 填: server-$(hostname)"
echo "  4. Key 粘贴上面的公钥"
echo "  5. 点击 Add SSH key"
echo ""
read -p "添加完成后按回车继续..."

# 6. 测试 SSH 连接
echo ""
log_step "测试 GitHub SSH 连接..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    log_info "SSH 连接成功！"
else
    log_warn "连接测试未通过，可能公钥还没添加，稍后再试"
    log_warn "手动测试: ssh -T git@github.com"
fi

# 7. 配置 git
log_step "配置 Git 用户信息..."
git config --global user.email "$EMAIL"
git config --global user.name "zhangkangjia"
git config --global init.defaultBranch main
log_info "Git 配置完成"

# 8. 克隆项目（如果目录不存在）
PROJECT_DIR="/data/workspace/smart-invoice"
if [ ! -d "$PROJECT_DIR" ]; then
    log_step "克隆项目..."
    mkdir -p /data/workspace
    cd /data/workspace
    git clone git@github.com:zhangkangjia/smart-invoice.git
    log_info "项目已克隆到 $PROJECT_DIR"
else
    log_info "项目目录已存在: $PROJECT_DIR"
    cd "$PROJECT_DIR"
    # 切换为 SSH 协议（如果之前是 HTTPS）
    current_url=$(git remote get-url origin)
    if echo "$current_url" | grep -q "^https://"; then
        log_step "切换远程协议为 SSH..."
        git remote set-url origin git@github.com:zhangkangjia/smart-invoice.git
        log_info "已切换为 SSH"
    fi
    log_step "拉取最新代码..."
    git fetch origin
    git reset --hard origin/main
    log_info "代码已更新"
fi

# 9. 检查 Docker
echo ""
log_step "检查 Docker..."
if command -v docker &> /dev/null; then
    log_info "Docker 已安装: $(docker --version)"
else
    log_error "Docker 未安装！"
    echo -e "${YELLOW}请先安装 Docker:${NC}"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  systemctl enable docker && systemctl start docker"
    exit 1
fi

if docker compose version &> /dev/null 2>&1; then
    log_info "Docker Compose 已安装"
elif command -v docker-compose &> /dev/null; then
    log_info "docker-compose 已安装"
else
    log_warn "Docker Compose 未安装，正在安装..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_info "docker-compose 安装完成"
fi

# 10. 启动服务
echo ""
log_step "启动服务..."
cd "$PROJECT_DIR"
chmod +x deploy.sh
./deploy.sh

echo ""
log_info "========================================"
log_info "  初始化完成！"
log_info "========================================"
