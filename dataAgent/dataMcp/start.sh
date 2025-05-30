#!/bin/bash

# 默认使用MCP方式启动
STARTUP_MODE=${STARTUP_MODE:-"mcp"}

if [ "$STARTUP_MODE" = "mcp" ]; then
    echo "Starting in MCP mode..."
    # 启动MCP服务
    python -c "from app.main import mcp; mcp.run(transport='streamable-http', host='0.0.0.0', port=8000, path='/mcp')"
elif [ "$STARTUP_MODE" = "fastapi" ]; then
    echo "Starting in FastAPI mode..."
    # 启动FastAPI服务
    python -m app.main
else
    echo "Invalid STARTUP_MODE. Use 'mcp' or 'fastapi'"
    exit 1
fi 