import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("neo4j").setLevel(logging.ERROR)

from neo4j import GraphDatabase
import os
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from sentence_transformers import SentenceTransformer
import numpy as np

# Neo4j connection parameters
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://192.168.30.232:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

# Milvus connection parameters
MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.30.232")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "neo4j_paths_embedding"

PATH_CHUNK_MAXLEN = int(os.getenv("PATH_CHUNK_MAXLEN", 2048))

# 获取所有表名
def get_all_table_names(session):
    result = session.run("MATCH (n:Table) RETURN n.name AS name")
    return [record["name"] for record in result]

# 针对单个表名生成分页Cypher
def get_paged_query_for_table(table_name):
    return f"""
    CALL {{
        // 1. 先补自己的路径
        MATCH (start:Table {{name: '{table_name}'}})
        RETURN start.name AS startNode, coalesce(start.meta, '') AS pathStr
        UNION
        // 2. 再查最短正向路径
        MATCH (start:Table {{name: '{table_name}'}}), (end:Table)
        WHERE start <> end
        MATCH path = shortestPath((start)-[*..5]->(end))
        WITH start, path
        WITH start, [n IN nodes(path) | n.name] AS names, path
        WITH start, nodes(path) AS ns, relationships(path) AS rs
        WITH start, 
            [i IN range(0, size(ns)-1) | coalesce(ns[i].meta, '')] AS nodeStrs,
            [r IN rs | ' (' + coalesce(r.from, '') + ') ' + type(r) + '(' + coalesce(r.to, '') + ') '] AS relStrs
        RETURN start.name AS startNode, apoc.text.join([x IN range(0, size(relStrs)-1) | nodeStrs[x] + relStrs[x]] + [nodeStrs[-1]], '') AS pathStr
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
        FieldSchema(name="path", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields, description="Neo4j paths embedding collection")
    collection = Collection(COLLECTION_NAME, schema)
    # 不要立即 load
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

def main():
    # 超长路径输出文件
    long_path_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_paths.txt")
    with open(long_path_file, "w", encoding="utf-8") as f_long:
        pass  # 先清空

    # 初始化 embedding 模型
    model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 维
    emb_dim = model.get_sentence_embedding_dimension()

    # 初始化 Milvus，导入前先清空 collection
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if COLLECTION_NAME in utility.list_collections():
        Collection(COLLECTION_NAME).drop()
    collection = ensure_milvus_collection(emb_dim)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    page_size = 100
    total_count = 0
    global_row_id = 0  # 全局唯一行号
    try:
        with driver.session() as session, open(long_path_file, "a", encoding="utf-8") as f_long:
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
                    # embedding & insert to Milvus
                    all_path_strs = []
                    all_origin_path_ids = []
                    for path_str in [record['pathStr'] for record in data]:
                        chunks = split_long_path_by_bytes(path_str)
                        for chunk in chunks:
                            all_path_strs.append(chunk)
                            all_origin_path_ids.append(global_row_id)
                        global_row_id += 1
                    # 批量插入
                    if all_path_strs:
                        embeddings = model.encode(all_path_strs, show_progress_bar=False)
                        entities = [
                            all_origin_path_ids,
                            all_path_strs,
                            [emb.tolist() if isinstance(emb, np.ndarray) else emb for emb in embeddings]
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
    main() 