#!/bin/bash

# GPS位置管理系统自动部署脚本
# 支持从GitHub直接下载部署
# 适用于Ubuntu 18.04 with Docker

set -e

echo "🚀 开始部署GPS位置管理系统..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
GITHUB_REPO="https://github.com/qyjqio/nissanlot"
APP_DIR="/opt/gps-system"
BRANCH="main"

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
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    log_error "请使用root用户运行此脚本"
    exit 1
fi

# 显示系统信息
log_step "检查系统信息..."
echo "操作系统: $(lsb_release -d | cut -f2)"
echo "内核版本: $(uname -r)"
echo "内存信息: $(free -h | grep Mem | awk '{print $2}')"
echo "磁盘空间: $(df -h / | awk 'NR==2 {print $4}') 可用"

# 更新系统
log_step "更新系统包..."
apt-get update -y
apt-get upgrade -y

# 安装必要的工具
log_step "安装必要工具..."
apt-get install -y curl wget git vim htop unzip openssl

# 检查Docker是否已安装
log_step "检查Docker环境..."
if ! command -v docker &> /dev/null; then
    log_warn "Docker未安装，正在安装..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
    rm get-docker.sh
    log_info "Docker安装完成"
else
    log_info "Docker已安装: $(docker --version)"
fi

# 检查Docker Compose是否已安装
if ! command -v docker-compose &> /dev/null; then
    log_warn "Docker Compose未安装，正在安装..."
    curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_info "Docker Compose安装完成"
else
    log_info "Docker Compose已安装: $(docker-compose --version)"
fi

# 停止现有服务（如果存在）
if [ -d "$APP_DIR" ]; then
    log_warn "检测到现有安装，正在停止服务..."
    cd $APP_DIR
    docker-compose down 2>/dev/null || true
    cd /
fi

# 创建应用目录
log_step "准备应用目录..."
rm -rf $APP_DIR
mkdir -p $APP_DIR
cd $APP_DIR

# 从GitHub下载代码
log_step "从GitHub下载代码..."
if command -v git &> /dev/null; then
    # 使用git克隆
    git clone $GITHUB_REPO.git temp_repo
    mv temp_repo/* .
    mv temp_repo/.* . 2>/dev/null || true
    rm -rf temp_repo
else
    # 使用wget下载zip包
    wget -O nissanlot.zip $GITHUB_REPO/archive/refs/heads/$BRANCH.zip
    unzip nissanlot.zip
    mv nissanlot-$BRANCH/* .
    rm -rf nissanlot-$BRANCH nissanlot.zip
fi

log_info "代码下载完成"

# 创建必要的目录
mkdir -p data ssl logs backups

# 生成自签名SSL证书
log_step "生成SSL证书..."
if [ ! -f ssl/nginx-selfsigned.crt ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/nginx-selfsigned.key \
        -out ssl/nginx-selfsigned.crt \
        -subj "/C=CN/ST=Beijing/L=Beijing/O=GPS System/CN=$(curl -s ifconfig.me 2>/dev/null || echo localhost)"
    log_info "SSL证书生成完成"
else
    log_info "SSL证书已存在"
fi

# 设置文件权限
chmod 600 ssl/nginx-selfsigned.key
chmod 644 ssl/nginx-selfsigned.crt

# 创建环境配置文件
log_step "创建环境配置..."
cat > .env << EOF
# GPS系统环境配置
FLASK_ENV=production
SECRET_KEY=gps-system-secret-key-$(date +%s)
DATABASE_URL=sqlite:///gps_system.db

# Redis配置
REDIS_URL=redis://redis:6379/0

# 邮件配置（可选）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# 系统配置
TZ=Asia/Shanghai
EOF

# 构建并启动服务
log_step "构建并启动服务..."
docker-compose build
docker-compose up -d

# 等待服务启动
log_step "等待服务启动..."
sleep 30

# 检查服务状态
log_step "检查服务状态..."
if docker-compose ps | grep -q "Up"; then
    log_info "服务启动成功"
else
    log_error "服务启动失败，请检查日志"
    docker-compose logs
    exit 1
fi

# 初始化数据库
log_step "初始化数据库..."
docker-compose exec -T gps-app python -c "
from app import init_database
init_database()
print('数据库初始化完成')
" || log_warn "数据库初始化可能失败，请手动检查"

# 创建系统服务文件
log_step "创建系统服务..."
cat > /etc/systemd/system/gps-system.service << EOF
[Unit]
Description=GPS Location Management System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# 启用系统服务
systemctl daemon-reload
systemctl enable gps-system.service

# 配置防火墙
log_step "配置防火墙..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    log_info "防火墙配置完成"
fi

# 创建日志轮转配置
log_step "配置日志轮转..."
cat > /etc/logrotate.d/gps-system << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose -f $APP_DIR/docker-compose.yml restart gps-app
    endscript
}
EOF

# 创建备份脚本
log_step "创建备份脚本..."
cat > $APP_DIR/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/gps-system/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "$(date): 开始备份..." >> $BACKUP_DIR/backup.log

# 备份数据库
if [ -f "/opt/gps-system/gps_system.db" ]; then
    cp /opt/gps-system/gps_system.db $BACKUP_DIR/gps_system_$DATE.db
    echo "$(date): 数据库备份完成" >> $BACKUP_DIR/backup.log
fi

# 备份配置文件
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    /opt/gps-system/.env \
    /opt/gps-system/docker-compose.yml \
    /opt/gps-system/nginx.conf 2>/dev/null

# 清理30天前的备份
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "$(date): 备份完成，清理旧文件" >> $BACKUP_DIR/backup.log
EOF

chmod +x $APP_DIR/backup.sh

# 添加定时备份任务
log_step "配置定时任务..."
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -

# 创建监控脚本
cat > $APP_DIR/monitor.sh << 'EOF'
#!/bin/bash
cd /opt/gps-system

LOG_FILE="logs/monitor.log"
mkdir -p logs

# 检查容器状态
if ! docker-compose ps | grep -q "Up"; then
    echo "$(date): GPS系统容器异常，正在重启..." >> $LOG_FILE
    docker-compose restart
    echo "$(date): 容器重启完成" >> $LOG_FILE
fi

# 检查磁盘空间
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
    echo "$(date): 磁盘使用率过高: ${DISK_USAGE}%" >> $LOG_FILE
fi

# 检查内存使用
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 90 ]; then
    echo "$(date): 内存使用率过高: ${MEM_USAGE}%" >> $LOG_FILE
fi

# 清理日志文件（保持最近1000行）
if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE") -gt 1000 ]; then
    tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp"
    mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi
EOF

chmod +x $APP_DIR/monitor.sh

# 添加监控定时任务
(crontab -l 2>/dev/null; echo "*/5 * * * * $APP_DIR/monitor.sh") | crontab -

# 创建管理脚本
log_step "创建管理脚本..."
cat > $APP_DIR/manage.sh << 'EOF'
#!/bin/bash

case "$1" in
    start)
        echo "启动GPS系统..."
        docker-compose up -d
        ;;
    stop)
        echo "停止GPS系统..."
        docker-compose down
        ;;
    restart)
        echo "重启GPS系统..."
        docker-compose restart
        ;;
    status)
        echo "GPS系统状态:"
        docker-compose ps
        ;;
    logs)
        echo "查看日志:"
        docker-compose logs -f
        ;;
    backup)
        echo "执行备份..."
        ./backup.sh
        ;;
    update)
        echo "更新系统..."
        git pull origin main
        docker-compose build
        docker-compose up -d
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs|backup|update}"
        exit 1
        ;;
esac
EOF

chmod +x $APP_DIR/manage.sh

# 获取服务器IP
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || echo "localhost")

# 最终检查
log_step "最终检查..."
sleep 10

if curl -k -s https://localhost >/dev/null 2>&1; then
    SERVICE_STATUS="✅ 运行正常"
else
    SERVICE_STATUS="⚠️  可能需要等待几分钟"
fi

# 显示部署结果
echo ""
echo "=========================================="
log_info "🎉 GPS位置管理系统部署完成！"
echo "=========================================="
echo ""
echo "📋 部署信息"
echo "----------------------------------------"
echo "🌐 访问地址: https://$SERVER_IP"
echo "🔐 管理员账号: admin"
echo "🔑 管理员密码: admin123"
echo "📁 应用目录: $APP_DIR"
echo "🚀 服务状态: $SERVICE_STATUS"
echo ""
echo "🛠️ 管理命令"
echo "----------------------------------------"
echo "📊 查看状态: cd $APP_DIR && ./manage.sh status"
echo "📝 查看日志: cd $APP_DIR && ./manage.sh logs"
echo "🔄 重启服务: cd $APP_DIR && ./manage.sh restart"
echo "💾 手动备份: cd $APP_DIR && ./manage.sh backup"
echo "🔄 更新系统: cd $APP_DIR && ./manage.sh update"
echo ""
echo "🔧 API接口示例"
echo "----------------------------------------"
echo "📍 上传GPS: POST https://$SERVER_IP/api/gps/upload"
echo "📱 设备位置: GET https://$SERVER_IP/api/devices/{device_id}/location"
echo "📈 历史轨迹: GET https://$SERVER_IP/api/devices/{device_id}/history"
echo ""
echo "⚠️  重要提醒"
echo "----------------------------------------"
echo "1. 首次访问需要接受自签名证书"
echo "2. 建议配置正式SSL证书"
echo "3. 系统已配置自动备份和监控"
echo "4. 防火墙已开放80、443、22端口"
echo ""
echo "📞 技术支持"
echo "----------------------------------------"
echo "• 查看服务: docker-compose ps"
echo "• 查看日志: docker-compose logs -f"
echo "• 监控日志: tail -f logs/monitor.log"
echo "• 备份日志: tail -f backups/backup.log"
echo ""
log_info "🚀 部署完成！请访问 https://$SERVER_IP 开始使用系统"
echo "==========================================" 