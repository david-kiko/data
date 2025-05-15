import os
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np

MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding"
TOP_K = 5  # 检索topK个最相似chunk

def search_and_aggregate(query, top_k=TOP_K):
    # 1. embedding
    model = SentenceTransformer("BAAI/bge-large-zh-v1.5")  # 1024 维
    query_emb = model.encode([query])[0]

    # 2. 连接Milvus
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(COLLECTION_NAME)
    collection.load()

    # 3. 检索，获取 topK 个最相似的 origin_path_id
    search_params = {"metric_type": "L2", "params": {"nprobe": 128}}  # 增加nprobe，提高召回率
    results = collection.search(
        data=[query_emb.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        output_fields=["origin_path_id", "path"]
    )

    # 4. 收集命中的 origin_path_id，并记录相似度分数
    origin_path_ids = {}
    for hit in results[0]:
        oid = hit.entity.get("origin_path_id")
        if oid not in origin_path_ids:
            origin_path_ids[oid] = hit.distance  # 记录相似度分数

    # 5. 对每个 origin_path_id，查询所有 chunk，按顺序拼接
    candidates = []
    for oid, score in origin_path_ids.items():
        expr = f'origin_path_id == {oid}'
        res = collection.query(expr, output_fields=["path"])
        chunks = [record["path"] for record in res]
        full_path = "".join(chunks)
        candidates.append({"origin_path_id": oid, "path": full_path, "score": score})

    # 6. 重排
    reranker = CrossEncoder("BAAI/bge-reranker-large")  # 使用 BAAI/bge-reranker-large 作为重排模型
    reranked = reranker.rerank(query, candidates, top_k=top_k)

    # 7. 输出重排结果
    for item in reranked:
        print(f"\n[origin_path_id={item['origin_path_id']}, score={item['score']}]")
        print(item["path"])

if __name__ == "__main__":
    query = input("请输入检索内容：")
    search_and_aggregate(query) 