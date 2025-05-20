import os
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding_v2"  # 更改collection名称
TOP_K = 20  # 检索topK个最相似chunk

# 字段权重配置
FIELD_WEIGHTS = {
    "table_path": 0.7,  # 表路径权重
    "path": 0.3,  # 路径内容权重
}

def search_and_aggregate(query, top_k=TOP_K):
    # 1. embedding
    model = SentenceTransformer("BAAI/bge-base-zh")  # 512 维
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
            # 计算加权分数
            base_score = hit.distance
            table_path = hit.entity.get("table_path")
            path = hit.entity.get("path")
            
            # 计算表路径和路径的相似度（用余弦相似度）
            query_vec = model.encode([query], show_progress_bar=False)[0]
            table_vec = model.encode([table_path], show_progress_bar=False)[0]
            path_vec = model.encode([path], show_progress_bar=False)[0]
            table_score = cosine_similarity([query_vec], [table_vec])[0][0]
            path_score = cosine_similarity([query_vec], [path_vec])[0][0]
            
            # 加权计算最终分数
            weighted_score = (table_score * FIELD_WEIGHTS["table_path"] + 
                            path_score * FIELD_WEIGHTS["path"])
            origin_path_ids[oid] = weighted_score

    # 5. 对每个 origin_path_id，查询所有 chunk，按顺序拼接
    candidates = []
    for oid, score in origin_path_ids.items():
        expr = f'origin_path_id == {oid}'
        res = collection.query(expr, output_fields=["path", "table_path"])
        chunks = [record["path"] for record in res]
        full_path = "".join(chunks)
        table_path = res[0]["table_path"] if res else "UNKNOWN"
        candidates.append({
            "origin_path_id": oid,
            "path": full_path,
            "score": score,
            "table_path": table_path
        })

    # 6. 重排
    reranker = CrossEncoder("BAAI/bge-reranker-base")  # 使用 BAAI/bge-reranker-base 作为重排模型
    # 准备重排数据
    pairs = [(query, candidate["path"]) for candidate in candidates]
    scores = reranker.predict(pairs)
    
    # 将分数添加到候选项中，并考虑表路径权重
    for candidate, score in zip(candidates, scores):
        # 计算表路径相似度（用余弦相似度）
        query_vec = model.encode([query], show_progress_bar=False)[0]
        table_vec = model.encode([candidate["table_path"]], show_progress_bar=False)[0]
        table_score = cosine_similarity([query_vec], [table_vec])[0][0]
        # 加权计算最终分数
        candidate["rerank_score"] = (float(score) * FIELD_WEIGHTS["path"] + 
                                   float(table_score) * FIELD_WEIGHTS["table_path"])
    
    # 按重排分数排序
    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]

    # 7. 输出重排结果
    for item in reranked:
        print(f"\n[路径ID={item['origin_path_id']}, 相关度得分={item['rerank_score']:.4f}]")
        print(f"表路径：{item['table_path']}")
        print(f"路径内容：{item['path']}")

if __name__ == "__main__":
    query = input("请输入检索内容：")
    search_and_aggregate(query) 