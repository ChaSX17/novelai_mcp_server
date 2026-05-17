#!/bin/bash
# 不在这里设置 API Key，由 AstrBot MCP 配置传入
cd "$(dirname "$0")"
./venv/bin/python3 server.py
