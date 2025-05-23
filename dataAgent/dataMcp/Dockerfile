FROM python:3.10-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

# 安装uv并用清华源加速
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

ENV MILVUS_HOST=192.168.30.232
ENV MILVUS_PORT=19530
ENV COLLECTION_NAME=neo4j_paths_embedding
ENV TOP_K=5
ENV SQL_EXEC_URL=http://192.168.30.232:18086/api/sql/execute/v2
ENV RERANK_API_URL=http://192.168.80.134:9998/v1/rerank
ENV EMBEDDING_API_URL=http://192.168.80.134:9998/v1/embeddings

CMD ["python", "-m", "app.main"] 