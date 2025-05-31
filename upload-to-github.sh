#!/bin/bash

# 上传GPS系统到GitHub的脚本
# 使用方法: chmod +x upload-to-github.sh && ./upload-to-github.sh

echo "📦 准备上传GPS位置管理系统到GitHub..."
echo "仓库地址: https://github.com/qyjqio/nissanlot"
echo ""

# 检查git是否安装
if ! command -v git &> /dev/null; then
    echo "❌ Git未安装，请先安装Git"
    exit 1
fi

# 初始化git仓库（如果还没有）
if [ ! -d ".git" ]; then
    echo "🔧 初始化Git仓库..."
    git init
    git branch -M main
fi

# 添加远程仓库
echo "🔗 配置远程仓库..."
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/qyjqio/nissanlot.git

# 添加所有文件
echo "📁 添加文件到Git..."
git add .

# 提交更改
echo "💾 提交更改..."
git commit -m "GPS位置管理系统 - 完整部署包

✨ 功能特性:
- 🗺️ 实时位置监控 (支持1000台设备)
- 📱 设备管理和用户管理
- 🔐 权限控制和软件授权
- 📊 数据分析和轨迹回放
- 🛡️ 电子围栏和超速报警
- 💾 数据压缩和智能存储
- 🔒 HTTPS加密和安全配置

🚀 部署特性:
- 一键部署脚本
- Docker容器化
- 自动监控和备份
- 针对1GB内存优化
- 完整的管理工具

📋 系统架构:
- Flask + SQLite (轻量化)
- Bootstrap 5 前端
- Nginx + SSL代理
- Redis缓存 (可选)
- 自动化运维脚本"

# 推送到GitHub
echo "🚀 推送到GitHub..."
git push -u origin main

echo ""
echo "✅ 上传完成！"
echo ""
echo "🌐 仓库地址: https://github.com/qyjqio/nissanlot"
echo "📚 README文档: https://github.com/qyjqio/nissanlot/blob/main/README.md"
echo ""
echo "🎯 现在可以在服务器上执行一键部署:"
echo "curl -fsSL https://raw.githubusercontent.com/qyjqio/nissanlot/main/deploy.sh | bash"
echo ""
echo "📱 或者使用快速部署:"
echo "curl -fsSL https://raw.githubusercontent.com/qyjqio/nissanlot/main/quick-deploy.sh | bash" 