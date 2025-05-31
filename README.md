# GPS位置管理系统

🚗 专为车机设备设计的GPS位置监控与管理平台

## ✨ 功能特性

- 🗺️ **实时位置监控** - 支持1000台设备同时在线
- 📱 **设备管理** - 车机设备注册、状态监控
- 👥 **用户管理** - 车主信息管理，手机号绑定
- 🔐 **权限控制** - 软件授权管理，动态配置
- 📊 **数据分析** - 轨迹回放、里程统计、常去地点
- 🛡️ **电子围栏** - 区域监控、超速报警
- 💾 **数据压缩** - 智能存储，节省空间
- 🔒 **安全加密** - HTTPS加密，数据安全

## 🏗️ 系统架构

- **后端**: Flask + SQLite（轻量化设计）
- **前端**: Bootstrap 5 + 现代化UI
- **缓存**: Redis（可选）
- **代理**: Nginx + SSL
- **容器**: Docker + Docker Compose
- **监控**: 自动化监控脚本

## 📋 服务器要求

- **最低配置**: 1GB内存 + 20GB存储
- **操作系统**: Ubuntu 18.04+ / Debian 9+
- **网络**: 支持Docker Hub访问
- **权限**: Root用户权限

## 🚀 一键部署

### 方法1：直接部署（推荐）

```bash
# 在服务器上执行一条命令即可完成部署
curl -fsSL https://raw.githubusercontent.com/qyjqio/nissanlot/main/deploy.sh | bash
```

### 方法2：Git克隆部署

```bash
# 克隆仓库
git clone https://github.com/qyjqio/nissanlot.git
cd nissanlot

# 执行部署脚本
chmod +x deploy.sh
sudo ./deploy.sh
```

## 📱 部署完成后

部署成功后，您将看到以下信息：

```
🎉 GPS位置管理系统部署完成！

==========================================
📋 部署信息
==========================================
🌐 访问地址: https://your-server-ip
🔐 管理员账号: admin
🔑 管理员密码: admin123
📁 应用目录: /opt/gps-system
📊 服务状态: docker-compose ps
📝 查看日志: docker-compose logs -f
🔄 重启服务: systemctl restart gps-system
💾 手动备份: /opt/gps-system/backup.sh
==========================================
```

## 🔧 API接口文档

### 上传GPS数据
```bash
POST /api/gps/upload
Content-Type: application/json

{
  "device_id": "DEVICE001",
  "locations": [
    {
      "latitude": 39.9042,
      "longitude": 116.4074,
      "altitude": 50.0,
      "accuracy": 10.0,
      "speed": 60.5,
      "heading": 180.0,
      "timestamp": "2025-01-27T10:30:00"
    }
  ]
}
```

### 获取设备位置
```bash
GET /api/devices/{device_id}/location
```

### 获取历史轨迹
```bash
GET /api/devices/{device_id}/history?start_date=2025-01-01&end_date=2025-01-31
```

### 获取设备列表
```bash
GET /api/devices
Authorization: 需要登录
```

## 🛠️ 系统管理

### 查看服务状态
```bash
cd /opt/gps-system
docker-compose ps
```

### 查看日志
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f gps-app
docker-compose logs -f nginx
docker-compose logs -f redis
```

### 重启服务
```bash
# 重启所有服务
systemctl restart gps-system

# 或者
cd /opt/gps-system
docker-compose restart
```

### 备份数据
```bash
# 手动备份
/opt/gps-system/backup.sh

# 查看备份文件
ls -la /opt/gps-system/backups/
```

### 监控系统
```bash
# 查看监控日志
tail -f /opt/gps-system/logs/monitor.log

# 查看备份日志
tail -f /opt/gps-system/logs/backup.log
```

## 📊 性能优化

系统已针对1GB内存服务器进行优化：

- ✅ 使用SQLite替代PostgreSQL
- ✅ 单体应用架构，减少内存占用
- ✅ GPS数据压缩存储
- ✅ 自动清理过期数据
- ✅ 限制每设备最多10条实时位置
- ✅ Redis缓存（可选）

## 🔒 安全配置

- ✅ HTTPS加密传输
- ✅ 自签名SSL证书（可替换为正式证书）
- ✅ API接口限流
- ✅ 防火墙配置
- ✅ 安全头设置

## 📈 扩展功能

### 配置正式SSL证书
```bash
# 将证书文件放到 /opt/gps-system/ssl/ 目录
# 修改 nginx.conf 中的证书路径
# 重启nginx服务
docker-compose restart nginx
```

### 配置邮件告警
```bash
# 编辑环境配置
vim /opt/gps-system/.env

# 添加邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 数据库管理
```bash
# 进入应用容器
docker-compose exec gps-app bash

# 使用Python操作数据库
python -c "
from app import app, db
with app.app_context():
    # 查看表结构
    print(db.engine.table_names())
"
```

## 🐛 故障排除

### 服务无法启动
```bash
# 检查Docker状态
systemctl status docker

# 检查端口占用
netstat -tlnp | grep :80
netstat -tlnp | grep :443

# 重新构建镜像
cd /opt/gps-system
docker-compose build --no-cache
docker-compose up -d
```

### 内存不足
```bash
# 查看内存使用
free -h
docker stats

# 清理Docker缓存
docker system prune -f
```

### 存储空间不足
```bash
# 查看磁盘使用
df -h

# 清理旧备份
find /opt/gps-system/backups -name "*.db" -mtime +7 -delete

# 清理Docker镜像
docker image prune -f
```

## 📞 技术支持

如果遇到问题，请：

1. 查看系统日志：`docker-compose logs -f`
2. 检查监控日志：`tail -f /opt/gps-system/logs/monitor.log`
3. 确认服务状态：`docker-compose ps`
4. 检查防火墙设置：`ufw status`

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**⚡ 快速开始：复制上面的一键部署命令到您的服务器执行即可！** 