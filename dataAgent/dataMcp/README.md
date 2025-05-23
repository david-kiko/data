# Neo4j Paths Search MCP

这是一个基于 FastAPI 的 MCP 服务，提供 Neo4j 路径的流式搜索功能。

## 功能特点

- 支持自然语言查询
- 流式响应（Streaming Response）
- 支持表路径和路径内容的混合搜索
- 基于 Milvus 的向量检索
- 支持结果重排序

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

## 安装

1. 安装 uv（如果尚未安装）：
```bash
pip install uv
```

2. 使用 uv 创建虚拟环境并安装依赖：
```bash
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

3. 配置环境变量（可选）：
```bash
MILVUS_HOST=192.168.30.232
MILVUS_PORT=19530
RERANK_API_URL=http://192.168.80.134:9998/v1/rerank
EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings
```

## 运行服务

### 1. 启动 FastAPI HTTP 接口（推荐开发/调试用）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 访问 http://localhost:8000/docs 查看API文档

### 2. 启动 MCP 工具服务

#### 方式一：FastAPI HTTP 接口

```bash
docker run -d -p 8000:8000 \
  -e MILVUS_HOST=192.168.30.232 \
  -e MILVUS_PORT=19530 \
  -e COLLECTION_NAME=neo4j_paths_embedding \
  -e TOP_K=5 \
  -e SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute \
  -e RERANK_API_URL=http://192.168.80.134:9998/v1/rerank \
  -e EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings \
  datamcp
```

- 你可以根据需要修改环境变量（如 MILVUS_HOST、COLLECTION_NAME、SQL_EXEC_URL、RERANK_API_URL、EMBEDDING_API_URL 等）。
- 容器启动后，FastAPI 服务会监听 0.0.0.0:8000，路径为 `/docs`。

#### 方式二：MCP 工具服务（streamable-http）

如果你希望以 MCP 工具服务方式启动（即 `mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp")`），Docker 启动命令同上，容器会自动以 MCP 工具服务模式运行：

```bash
docker run -d -p 8000:8000 \
  -e MILVUS_HOST=192.168.30.232 \
  -e MILVUS_PORT=19530 \
  -e COLLECTION_NAME=neo4j_paths_embedding \
  -e TOP_K=5 \
  -e SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute \
  -e RERANK_API_URL=http://192.168.80.134:9998/v1/rerank \
  -e EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings \
  datamcp
```

- 容器启动后，MCP 工具服务会监听 0.0.0.0:8000，路径为 `/mcp`。
- 你可以根据需要选择 FastAPI 或 MCP 工具服务方式。

### 3. 直接本地启动 MCP 工具服务（非 Docker）

```bash
python -m app.main
```

- 这会以 MCP 工具服务（streamable-http）方式启动，监听 0.0.0.0:8000，路径为 /mcp。
- 适合本地开发、调试或测试。

## Docker 部署

### 1. 构建镜像

在 dataMcp 目录下执行：

```bash
docker build -t datamcp .
```

### 2. 启动容器（MCP 工具服务方式）

```bash
docker run -d -p 8000:8000 \
  -e MILVUS_HOST=192.168.30.232 \
  -e MILVUS_PORT=19530 \
  -e COLLECTION_NAME=neo4j_paths_embedding \
  -e TOP_K=5 \
  -e SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute \
  -e RERANK_API_URL=http://192.168.80.134:9998/v1/rerank \
  -e EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings \
  datamcp
```

- 你可以根据需要修改环境变量（如 MILVUS_HOST、COLLECTION_NAME、SQL_EXEC_URL、RERANK_API_URL、EMBEDDING_API_URL 等）。
- 容器启动后，MCP 工具服务会监听 0.0.0.0:8000，路径为 `/mcp`。

## API 使用

### 搜索接口

```
curl "http://localhost:8000/search?query=工作中心有多少条数据&top_k=5"
curl -X POST "http://localhost:8000/mcp" -H "Content-Type: application/json" -d '{"tool": "execute_sql", "arguments": {"sql": "SELECT 1 FROM DUAL"}}'
```

## 清理 pyc 文件

```bash
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```