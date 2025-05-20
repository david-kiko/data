import os
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
from typing import AsyncGenerator, Dict, Any

# Milvus connection parameters
MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding_v2"  # v2 collection名称
TOP_K = 5  # 检索topK个最相似chunk

async def search_and_aggregate(query: str, top_k: int = TOP_K) -> AsyncGenerator[Dict[str, Any], None]:
    """
    搜索并聚合结果，以异步生成器形式返回结果
    """
    # 1. embedding
    model = SentenceTransformer("BAAI/bge-base-zh")  # v2模型
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
        limit=top_k * 2,  # 扩大检索范围，以便后续重排序
        output_fields=["origin_path_id", "path", "table_path"]
    )

    # 4. 收集命中的 origin_path_id，并记录相似度分数
    origin_path_ids = {}
    for hit in results[0]:
        oid = hit.entity.get("origin_path_id")
        if oid not in origin_path_ids:
            # 使用距离作为基础分数
            origin_path_ids[oid] = hit.distance

    # 5. 对每个 origin_path_id，查询所有 chunk，按顺序拼接
    candidates = []
    for oid, score in origin_path_ids.items():
        expr = f'origin_path_id == {oid}'
        res = collection.query(expr, output_fields=["path", "table_path"])
        chunks = [record["path"] for record in res]
        full_path = "".join(chunks)
        table_path = res[0]["table_path"] if res else ""
        candidates.append({
            "origin_path_id": oid,
            "path": full_path,
            "table_path": table_path,
            "score": score
        })

    # 6. 重排
    reranker = CrossEncoder("BAAI/bge-reranker-large")  # 使用 large 版本的重排模型
    # 分别对path和table_path重排
    pairs_path = [(query, candidate["path"]) for candidate in candidates]
    pairs_table = [(query, candidate["table_path"]) for candidate in candidates]
    scores_path = reranker.predict(pairs_path)
    scores_table = reranker.predict(pairs_table)
    for candidate, path_score, table_score in zip(candidates, scores_path, scores_table):
        candidate["final_score"] = 0.3 * float(path_score) + 0.7 * float(table_score)
    reranked = sorted(candidates, key=lambda x: x["final_score"], reverse=True)[:top_k]

    # 7. 以异步生成器形式返回结果
    for item in reranked:
        print(f"path_id: {item['origin_path_id']}, score: {round(float(item['final_score']), 4)}")
        yield item["path"] 