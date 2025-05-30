# Neo4j Paths Search MCP

这是一个基于 FastAPI 的 MCP 服务，提供 Neo4j 路径的流式搜索功能。

## 功能特点

- 支持自然语言查询
- 流式响应（Streaming Response）
- 支持表路径和路径内容的混合搜索
- 基于 Milvus 的向量检索
- 支持结果重排序

## 环境要求

- Python 3.10+
- Docker (可选)

## 安装

### 1. 使用 uv 安装（推荐）

```bash
# 安装 uv
pip install uv

# 创建虚拟环境，指定python版本
uv venv --python=python3.10

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt
```

### 2. 使用 pip 安装

```bash
pip install -r requirements.txt
```

## 配置

在运行服务之前，请确保设置以下环境变量：

```bash
MILVUS_HOST=192.168.30.232
MILVUS_PORT=19530
COLLECTION_NAME=neo4j_paths_embedding_v4
TOP_K=5
SQL_EXEC_URL=http://192.168.30.232:18086/api/sql/execute/v2
RERANK_API_URL=http://192.168.80.134:9998/v1/rerank
EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings
```

## 启动服务

### 1. 直接运行

```bash
# 启动 FastAPI 服务（开发/调试用）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或启动 MCP 服务
python -m app.main
```

### 2. 使用 Docker

#### 构建镜像

```bash
docker build -t datamcp .
```

#### 运行容器

```bash
# 使用 MCP 方式启动（默认）
docker run -d -p 8000:8000 \
  -e MILVUS_HOST=192.168.30.232 \
  -e MILVUS_PORT=19530 \
  -e COLLECTION_NAME=neo4j_paths_embedding \
  -e TOP_K=5 \
  -e SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute \
  -e RERANK_API_URL=http://192.168.80.134:9998/v1/rerank \
  -e EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings \
  datamcp

# 或使用 FastAPI 方式启动
docker run -d -p 8000:8000 \
  -e STARTUP_MODE=fastapi \
  -e MILVUS_HOST=192.168.30.232 \
  -e MILVUS_PORT=19530 \
  -e COLLECTION_NAME=neo4j_paths_embedding \
  -e TOP_K=5 \
  -e SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute \
  -e RERANK_API_URL=http://192.168.80.134:9998/v1/rerank \
  -e EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings \
  datamcp
```

## 启动模式说明

服务支持两种启动模式：

1. **MCP 模式**（默认）
   - 使用 `transport='streamable-http'` 启动
   - 监听 8000 端口
   - 路径为 `/mcp`
   - 适合与 Dify 等需要 MCP 协议的服务集成

2. **FastAPI 模式**
   - 使用标准的 FastAPI 服务器启动
   - 监听 8000 端口
   - 提供标准的 REST API 接口
   - 适合直接作为 API 服务使用

可以通过设置环境变量 `STARTUP_MODE` 来选择启动模式：
- `STARTUP_MODE=mcp`: 使用 MCP 模式启动（默认）
- `STARTUP_MODE=fastapi`: 使用 FastAPI 模式启动

## API 使用

### 搜索接口

```bash
# FastAPI 模式
curl "http://localhost:8000/search?query=工作中心有多少条数据&top_k=5"

# MCP 模式
curl -X POST "http://localhost:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{"tool": "execute_sql", "arguments": {"sql": "SELECT 1 FROM DUAL"}}'
```

### API 文档
启动服务后，可以访问以下地址查看 API 文档：
- FastAPI 模式：http://localhost:8000/docs
- MCP 模式：http://localhost:8000/mcp/docs

## 私有镜像仓库

本项目包含一个基于 Docker Compose 的私有镜像仓库配置，用于存储和管理 Docker 镜像。

### 1. 启动私有镜像仓库

```bash
# 创建数据目录
mkdir -p registry-data

# 启动仓库
docker-compose up -d
```

### 2. 配置 Docker 客户端

在 Linux 系统上，编辑或创建 `/etc/docker/daemon.json`：

```json
{
  "insecure-registries": ["192.168.80.134:5000"]
}
```

然后重启 Docker 服务：

```bash
sudo systemctl restart docker
```

### 3. 使用私有仓库

```bash
# 标记镜像
docker tag datamcp 192.168.80.134:5000/datamcp:latest

# 推送镜像
docker push 192.168.80.134:5000/datamcp:latest

# 拉取镜像
docker pull 192.168.80.134:5000/datamcp:latest
```

### 4. 查看仓库内容

```bash
# 列出所有镜像
curl http://192.168.80.134:5000/v2/_catalog

# 列出特定镜像的标签
curl http://192.168.80.134:5000/v2/datamcp/tags/list
```

## 维护

### 清理缓存文件

```bash
# 清理 Python 缓存文件
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```