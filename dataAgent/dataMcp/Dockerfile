FROM 513180854/datamcp:base

COPY . .

ENV MILVUS_HOST=192.168.30.232
ENV MILVUS_PORT=19530
ENV COLLECTION_NAME=neo4j_paths_embedding
ENV TOP_K=5
ENV SQL_EXEC_URL=http://192.168.30.231:18086/api/sql/execute

CMD ["python", "-m", "app.main"] 