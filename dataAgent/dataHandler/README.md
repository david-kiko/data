# dataHandle

Neo4j 数据处理工具，用于查询和展示所有节点的正向路径（含自环）。

## 功能简介
- 执行 Neo4j Cypher 查询，获取所有节点的正向路径（含自环）
- 支持分页查询，避免一次性返回过多数据
- 直接打印查询结果，便于查看和分析

## 环境管理

本项目使用 uv 进行 Python 环境管理。

### 1. 安装 uv

```bash
# Windows
pip install uv

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows
.venv/Scripts/activate

# Linux/macOS
source .venv/bin/activate
```

### 3. 安装依赖

```bash
uv pip install -r requirements.txt
```

## 运行程序

```bash
python app/neo4j_client.py
```

## 配置 Neo4j 连接

可通过环境变量设置：
- `NEO4J_URI`（默认：bolt://localhost:7687）
- `NEO4J_USER`（默认：neo4j）
- `NEO4J_PASSWORD`（默认：password）

## 输出示例

程序会分页显示查询结果，每页默认显示100条记录：

```
Page 1:
Start Node: A
Path: A[用户表](USER_ID:VARCHAR:用户ID) ...
--------------------------------------------------
Start Node: B
Path: B[订单表](ORDER_ID:VARCHAR:订单ID) ...
--------------------------------------------------
```

## 注意事项
- 确保 Neo4j 数据库已启动并可访问
- 确保已安装必要的 Python 包
- 如需修改每页显示记录数，可在代码中调整 `page_size` 参数
- 使用 uv 管理环境可以确保依赖版本的一致性

---
如有问题欢迎反馈！ 