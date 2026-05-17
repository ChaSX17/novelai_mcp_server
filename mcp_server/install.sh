#!/bin/bash
# NovelAI MCP Server 安装脚本（Linux Ubuntu）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/home/ubuntu/novelai_mcp_server"

echo "=== NovelAI MCP Server 安装 ==="
echo "源目录: $SCRIPT_DIR"
echo "安装目录: $INSTALL_DIR"

# 创建目录
mkdir -p "$INSTALL_DIR/tokenizers"

# 复制文件（如果源和目标不同）
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp "$SCRIPT_DIR/server.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/spm_decoder.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/tokenizers/"* "$INSTALL_DIR/tokenizers/"
fi

# 创建虚拟环境
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 安装依赖
echo "安装依赖..."
./venv/bin/python3 -m pip install -r requirements.txt

chmod +x start.sh 2>/dev/null || true

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步：在 AstrBot WebUI 中配置 MCP 服务器"
echo "  设置 → MCP 服务器 → 添加"
echo "  Command: /home/ubuntu/novelai_mcp_server/venv/bin/python3"
echo "  Args: [\"server.py\"]"
echo "  CWD: /home/ubuntu/novelai_mcp_server"
echo "  Env: NOVELAI_API_KEY=你的密钥, NOVELAI_PROXY=http://127.0.0.1:7890"
