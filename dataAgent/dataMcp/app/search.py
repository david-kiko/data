import os
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
from typing import AsyncGenerator, Dict, Any
import time

# Milvus connection parameters
MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding"  # 更新为新的collection名称
TOP_K = 10  # 检索topK个最相似chunk

async def search_and_aggregate(query: str, top_k: int = TOP_K) -> AsyncGenerator[Dict[str, Any], None]:
    """
    搜索并聚合结果，以异步生成器形式返回结果
    """
    start_total = time.time()
    # 1. embedding
    start = time.time()
    model = SentenceTransformer("BAAI/bge-large-zh-v1.5")  # 1024 维
    query_emb = model.encode([query])[0]
    print(f"[计时] embedding: {time.time() - start:.3f}s")

    # 2. 连接Milvus
    start = time.time()
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(COLLECTION_NAME)
    collection.load()
    print(f"[计时] 连接Milvus并加载collection: {time.time() - start:.3f}s")

    # 3. 检索，获取 topK 个最相似的 origin_path_id
    start = time.time()
    search_params = {"metric_type": "L2", "params": {"nprobe": 512}}  # 使用 L2 距离作为相似度度量
    results = collection.search(
        data=[query_emb.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=top_k * 10,  # 扩大检索范围，确保覆盖全部chunk
        output_fields=["origin_path_id", "path"]
    )
    print(f"[计时] Milvus 检索: {time.time() - start:.3f}s")

    # 4. 收集命中的 origin_path_id，并记录原始分数
    start = time.time()
    origin_path_ids = {}
    for hit in results[0]:
        oid = hit.entity.get("origin_path_id")
        if oid not in origin_path_ids:
            origin_path_ids[oid] = hit.distance
    print(f"[计时] 处理检索结果: {time.time() - start:.3f}s")

    # 检查 origin_path_ids 是否为空
    if not origin_path_ids:
        print(f"[计时] 总耗时: {time.time() - start_total:.3f}s")
        return  # 直接返回，避免后续处理

    # 5. 对每个 origin_path_id，查询所有 chunk，按顺序拼接
    start = time.time()
    candidates = []
    for oid, score in origin_path_ids.items():
        expr = f'origin_path_id == {oid}'
        res = collection.query(expr, output_fields=["path"])
        chunks = [record["path"] for record in res]
        full_path = "".join(chunks)
        candidates.append({
            "origin_path_id": oid,
            "path": full_path,
            "score": score
        })
    print(f"[计时] 查询并拼接chunk: {time.time() - start:.3f}s")

    # 6. 重排
    start = time.time()
    reranker = CrossEncoder("BAAI/bge-reranker-base")  # 使用 base 版本的重排模型
    # 准备重排数据
    pairs = [(query, candidate["path"]) for candidate in candidates]
    scores = reranker.predict(pairs, batch_size=32)
    print(f"[计时] CrossEncoder重排: {time.time() - start:.3f}s")
    
    # 将分数添加到候选项中
    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)
    
    # 按重排分数排序
    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]

    print(f"[计时] 总耗时: {time.time() - start_total:.3f}s")

    # 7. 以异步生成器形式返回结果
    for item in reranked:
        print(f"path_id: {item['origin_path_id']}, score: {round(float(item['score']), 4)}")
        yield item["path"] 