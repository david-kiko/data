import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("neo4j").setLevel(logging.ERROR)

from neo4j import GraphDatabase
import os
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from sentence_transformers import SentenceTransformer
import numpy as np
import httpx
import asyncio

# Neo4j connection parameters
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://192.168.30.232:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

# Milvus connection parameters
MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding_v3"

PATH_CHUNK_MAXLEN = int(os.getenv("PATH_CHUNK_MAXLEN", 4096))
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "http://192.168.80.134:9998/v1/embeddings")

# 初始化模型
model = SentenceTransformer("BAAI/bge-large-zh-v1.5")

async def get_embeddings(texts: list, is_local: bool = False) -> list:
    """
    获取文本的embedding向量
    
    Args:
        texts: 文本列表
        is_local: 是否使用本地模型，True使用本地模型，False使用远程API
        
    Returns:
        list: embedding向量列表
    """
    if is_local:
        embeddings = model.encode(texts, show_progress_bar=False)
        return [emb.tolist() if isinstance(emb, np.ndarray) else emb for emb in embeddings]
    else:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    EMBEDDING_API_URL,
                    json={
                        "input": texts,
                        "model": "bge-large-zh-v1.5"
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
            print(f"Error calling embedding API: {str(e)}")
            raise

# 获取所有表名
def get_all_table_names(session):
    result = session.run("MATCH (n:Table) RETURN n.name AS name")
    # 过滤掉特定前缀和后缀的表
    filtered_tables = []
    for record in result:
        name = record["name"]
        if (not name.startswith("DM_") and 
            not name.startswith("TEST") and 
            not name.endswith("_TEST") and 
            not name.endswith("_BAK") and 
            not name.endswith("_LOG")):
            filtered_tables.append(name)
    return filtered_tables

# 针对单个表名生成分页Cypher
def get_paged_query_for_table(table_name):
    return f"""
    CALL {{
        // 1. 先补自己的路径
        MATCH (start:Table {{name: '{table_name}'}})
        RETURN start.name AS startNode, 
               coalesce(start.meta, '') AS pathStr
        UNION
        // 2. 再查最短正向路径
        MATCH (start:Table {{name: '{table_name}'}}), (end:Table)
        WHERE start <> end 
          AND NOT end.name STARTS WITH 'DM_' 
          AND NOT end.name STARTS WITH 'TEST'
          AND NOT end.name ENDS WITH '_TEST'
          AND NOT end.name ENDS WITH '_BAK'
          AND NOT end.name ENDS WITH '_LOG'
        MATCH path = shortestPath((start)-[*..5]->(end))
        WITH start, path
        WITH start, [n IN nodes(path) | n.name] AS names, path
        WITH start, nodes(path) AS ns, relationships(path) AS rs
        WITH start, 
            [i IN range(0, size(ns)-1) | coalesce(ns[i].meta, '')] AS nodeStrs,
            [r IN rs | ' (' + coalesce(r.from, '') + ') ' + type(r) + '(' + coalesce(r.to, '') + ') '] AS relStrs
        RETURN start.name AS startNode, 
               apoc.text.join([x IN range(0, size(relStrs)-1) | nodeStrs[x] + relStrs[x]] + [nodeStrs[-1]], '') AS pathStr
    }}
    RETURN startNode, pathStr
    SKIP $skip LIMIT $limit
    """

def ensure_milvus_collection(dim):
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if COLLECTION_NAME in utility.list_collections():
        collection = Collection(COLLECTION_NAME)
        collection.load()
        return collection
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="origin_path_id", dtype=DataType.INT64),
        FieldSchema(name="path", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields, description="Neo4j paths embedding collection")
    collection = Collection(COLLECTION_NAME, schema)
    return collection

def split_long_path_by_bytes(path_str, max_bytes=PATH_CHUNK_MAXLEN):
    # 按UTF-8字节数切分，确保不截断多字节字符
    encoded = path_str.encode('utf-8')
    chunks = []
    start = 0
    while start < len(encoded):
        end = start + max_bytes
        # 保证不截断多字节字符
        while end < len(encoded) and (encoded[end] & 0b11000000) == 0b10000000:
            end -= 1
        chunk_bytes = encoded[start:end]
        chunks.append(chunk_bytes.decode('utf-8', errors='ignore'))
        start = end
    return chunks

async def main():
    # 超长路径输出文件
    long_path_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_paths.txt")
    all_paths_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_paths.txt")
    
    # 清空文件
    with open(long_path_file, "w", encoding="utf-8") as f_long, \
         open(all_paths_file, "w", encoding="utf-8") as f_all:
        pass

    # 初始化 Milvus，导入前先清空 collection
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if COLLECTION_NAME in utility.list_collections():
        Collection(COLLECTION_NAME).drop()
    
    # 获取embedding维度
    emb_dim = model.get_sentence_embedding_dimension()
    collection = ensure_milvus_collection(emb_dim)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    page_size = 100
    total_count = 0
    global_row_id = 0
    try:
        with driver.session() as session, \
             open(long_path_file, "a", encoding="utf-8") as f_long, \
             open(all_paths_file, "a", encoding="utf-8") as f_all:
            table_names = get_all_table_names(session)
            num_tables = len(table_names)
            print(f"Found {num_tables} tables.")
            for idx, table_name in enumerate(table_names, 1):
                print(f"Processing table: {table_name} ({idx}/{num_tables}) ...", end=' ')
                page = 1
                table_count = 0
                while True:
                    skip = (page - 1) * page_size
                    paged_query = get_paged_query_for_table(table_name)
                    result = session.run(paged_query, skip=skip, limit=page_size)
                    data = [dict(record) for record in result]
                    if not data:
                        break
                    # 写入所有路径到文件，只写入pathStr
                    for record in data:
                        f_all.write(f"{record['pathStr']}\n")
                    # embedding & insert to Milvus
                    all_path_strs = []
                    all_origin_path_ids = []
                    for record in data:
                        chunks = split_long_path_by_bytes(record['pathStr'])
                        for chunk in chunks:
                            all_path_strs.append(chunk)
                            all_origin_path_ids.append(global_row_id)
                        global_row_id += 1
                    # 批量插入
                    if all_path_strs:
                        embeddings = await get_embeddings(all_path_strs, is_local=False)
                        entities = [
                            all_origin_path_ids,
                            all_path_strs,
                            embeddings
                        ]
                        collection.insert(entities)
                        table_count += len(all_path_strs)
                        total_count += len(all_path_strs)
                    if len(data) < page_size:
                        break
                    page += 1
                print(f"{table_count} records.")
            print(f"Total records: {total_count}")
        # 插入完所有数据后创建索引并load
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
    finally:
        driver.close()
    print(f"All paths embedded and inserted into Milvus collection '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    asyncio.run(main()) 