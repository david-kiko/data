import os
from pymilvus import connections, Collection
import numpy as np
from typing import AsyncGenerator
import time
import httpx
from contextlib import contextmanager
import json
import logging

# Milvus connection parameters
MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding_v4"  # 更新为新的collection名称
TOP_K = 10  # 检索topK个最相似chunk
RERANK_API_URL = "https://api.siliconflow.cn/v1/rerank"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
API_KEY = "sk-vtnuqpakabawcslqxbiqijqxqznyaswlyovjdcnqjnefrndg"

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 连接池配置
MILVUS_POOL_SIZE = 20  # 连接池大小
MILVUS_POOL_TIMEOUT = 30  # 连接超时时间（秒）

@contextmanager
def get_milvus_connection():
    """获取Milvus连接的上下文管理器"""
    try:
        # 检查是否已连接
        if not connections.has_connection("default"):
            connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        yield
    finally:
        # 不主动断开连接，让连接池管理
        pass

async def get_embeddings(texts: list) -> list:
    """
    获取文本的embedding向量
    
    Args:
        texts: 文本列表
        
    Returns:
        list: embedding向量列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                EMBEDDING_API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "Pro/BAAI/bge-m3",
                    "input": texts,
                    "encoding_format": "float"
                }
            )
            response.raise_for_status()
            result = response.json()
            if "data" in result:
                # 按index排序结果，确保顺序与输入一致
                sorted_results = sorted(result["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_results]
            else:
                raise ValueError("Unexpected API response format")
    except Exception as e:
        logger.error(f"Error calling embedding API: {str(e)}")
        raise

async def search_and_aggregate(query: str, top_k: int = TOP_K, table_filter: str = None, path_filter: str = None, return_fields: list = ["meta"]) -> AsyncGenerator[str, None]:
    """
    搜索并聚合结果，以异步生成器形式返回结果
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
        table_filter: 表名过滤条件
        path_filter: 路径过滤条件
        return_fields: 返回的字段列表
        
    Returns:
        AsyncGenerator[str, None]: 返回meta字符串的异步生成器
    """
    start_total = time.time()
    
    # 1. embedding
    start = time.time()
    embeddings = await get_embeddings([query])
    query_emb = embeddings[0]
    print(f"[计时] embedding: {time.time() - start:.3f}s")

    # 2. 连接Milvus（使用连接池）
    start = time.time()
    with get_milvus_connection():
        collection = Collection(COLLECTION_NAME)
        collection.load()
        print(f"[计时] 连接Milvus并加载collection: {time.time() - start:.3f}s")

        # 3. 检索，获取 topK 个最相似的记录
        start = time.time()
        search_params = {"metric_type": "L2", "params": {"nprobe": 512}}  # 使用 L2 距离作为相似度度量
        results = collection.search(
            data=[query_emb],
            anns_field="embedding",
            param=search_params,
            limit=top_k * 10,  # 扩大检索范围，确保覆盖全部chunk
            output_fields=["table_name", "meta"]
        )
        print(f"[计时] Milvus 检索: {time.time() - start:.3f}s")

        # 4. 按表名分组并收集meta信息
        start = time.time()
        table_metas = {}
        for hit in results[0]:
            table_name = hit.entity.get("table_name")
            meta = hit.entity.get("meta")
            
            # 应用过滤条件
            if table_filter and table_filter.lower() not in table_name.lower():
                continue
            if path_filter and path_filter.lower() not in meta.lower():
                continue
                
            if table_name not in table_metas:
                table_metas[table_name] = {
                    "meta": meta,
                    "score": hit.distance
                }
        print(f"[计时] 处理检索结果: {time.time() - start:.3f}s")

        # 检查 table_metas 是否为空
        if not table_metas:
            print(f"[计时] 总耗时: {time.time() - start_total:.3f}s")
            return  # 直接返回，避免后续处理

        # 5. 重排
        start = time.time()
        try:
            print(f"[重排] 开始调用重排API，候选数量: {len(table_metas)}")
            async with httpx.AsyncClient(timeout=30) as client:
                request_data = {
                    "model": "BAAI/bge-reranker-v2-m3",
                    "query": query,
                    "documents": [item["meta"] for item in table_metas.values()],
                    "top_n": len(table_metas),
                    "return_documents": False,
                    "max_chunks_per_doc": 1024,
                    "overlap_tokens": 80
                }
                response = await client.post(
                    RERANK_API_URL,
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=request_data
                )
                response.raise_for_status()
                response_data = response.json()
                if "results" in response_data:
                    sorted_results = sorted(response_data["results"], key=lambda x: x["index"])
                    scores = [result["relevance_score"] for result in sorted_results]
                else:
                    print(f"[重排] 警告: API响应格式不符合预期")
                    scores = [0.0] * len(table_metas)
        except httpx.HTTPStatusError as e:
            print(f"[重排] HTTP错误: {e.response.status_code} - {e.response.text}")
            scores = [0.0] * len(table_metas)
        except httpx.RequestError as e:
            print(f"[重排] 请求错误: {str(e)}")
            scores = [0.0] * len(table_metas)
        except Exception as e:
            print(f"[重排] 未知错误: {str(e)}")
            scores = [0.0] * len(table_metas)
        print(f"[计时] 外部重排API调用: {time.time() - start:.3f}s")

        # 将分数添加到候选项中
        table_items = list(table_metas.items())
        for (table_name, item), score in zip(table_items, scores):
            item["rerank_score"] = float(score)
        
        # 按重排分数排序
        reranked = sorted(table_items, key=lambda x: x[1]["rerank_score"], reverse=True)

        # 6. 选择top_k个最相关的结果
        final_results = reranked[:top_k]
        print(f"[计时] 选择最终结果: {time.time() - start:.3f}s")

        print(f"[计时] 总耗时: {time.time() - start_total:.3f}s")

        # 7. 以异步生成器形式返回结果
        for table_name, item in final_results:
            yield item["meta"] 