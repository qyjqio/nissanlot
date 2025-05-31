#!/bin/bash

# GPS系统快速部署脚本
# 使用方法: curl -fsSL https://raw.githubusercontent.com/qyjqio/nissanlot/main/quick-deploy.sh | bash

set -e

echo "🚀 GPS位置管理系统 - 快速部署"
echo "================================"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用root用户运行此脚本"
    echo "💡 使用方法: sudo bash"
    exit 1
fi

# 获取GitHub仓库信息
GITHUB_USER="qyjqio"
GITHUB_REPO="nissanlot"
GITHUB_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO"

echo "📦 从GitHub下载部署脚本..."
echo "仓库地址: $GITHUB_URL"

# 下载并执行部署脚本
curl -fsSL https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/main/deploy.sh | bash

echo ""
echo "✅ 快速部署完成！"
echo ""
echo "🔗 项目地址: $GITHUB_URL"
echo "📚 文档地址: $GITHUB_URL/blob/main/README.md"
echo ""
echo "🎯 下一步操作:"
echo "1. 访问 https://$(curl -s ifconfig.me) 使用系统"
echo "2. 使用 admin/admin123 登录管理后台"
echo "3. 根据需要配置SSL证书和邮件告警" 