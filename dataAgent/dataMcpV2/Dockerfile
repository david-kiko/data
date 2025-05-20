FROM python:3.10-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

# 安装uv并用清华源加速
RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN uv pip install --system -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 预下载 SentenceTransformer 模型
RUN pip install sentence-transformers \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-zh-v1.5')"

COPY . .

ENV MILVUS_HOST=192.168.30.232
ENV MILVUS_PORT=19530
ENV COLLECTION_NAME=neo4j_paths_embedding_v2
ENV TOP_K=5

CMD ["python", "-m", "app.main"] 