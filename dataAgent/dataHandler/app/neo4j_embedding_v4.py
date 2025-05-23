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
COLLECTION_NAME = "neo4j_paths_embedding_v4"

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
    result = session.run("MATCH (n:Table) RETURN n.name AS name, n.meta AS meta")
    # 过滤掉特定前缀和后缀的表
    filtered_tables = []
    for record in result:
        name = record["name"]
        meta = record["meta"]
        if (not name.startswith("DM_") and 
            not name.startswith("TEST") and 
            not name.endswith("_TEST") and 
            not name.endswith("_BAK") and 
            not name.endswith("_LOG")):
            filtered_tables.append((name, meta))
    return filtered_tables

def ensure_milvus_collection(dim):
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if COLLECTION_NAME in utility.list_collections():
        collection = Collection(COLLECTION_NAME)
        collection.load()
        return collection
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="meta", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields, description="Neo4j tables meta embedding collection")
    collection = Collection(COLLECTION_NAME, schema)
    return collection

def split_long_text_by_bytes(text: str, max_bytes=PATH_CHUNK_MAXLEN):
    # 按UTF-8字节数切分，确保不截断多字节字符
    encoded = text.encode('utf-8')
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
    # 超长文本输出文件
    long_text_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_texts.txt")
    all_texts_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_texts.txt")
    
    # 清空文件
    with open(long_text_file, "w", encoding="utf-8") as f_long, \
         open(all_texts_file, "w", encoding="utf-8") as f_all:
        pass

    # 初始化 Milvus，导入前先清空 collection
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if COLLECTION_NAME in utility.list_collections():
        Collection(COLLECTION_NAME).drop()
    
    # 获取embedding维度
    emb_dim = model.get_sentence_embedding_dimension()
    collection = ensure_milvus_collection(emb_dim)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    total_count = 0
    try:
        with driver.session() as session, \
             open(long_text_file, "a", encoding="utf-8") as f_long, \
             open(all_texts_file, "a", encoding="utf-8") as f_all:
            table_info = get_all_table_names(session)
            num_tables = len(table_info)
            print(f"Found {num_tables} tables.")
            
            # 准备批量插入的数据
            all_table_names = []
            all_meta_texts = []
            
            for idx, (table_name, meta) in enumerate(table_info, 1):
                print(f"Processing table: {table_name} ({idx}/{num_tables}) ...", end=' ')
                
                if not meta:
                    print("No meta information.")
                    continue
                    
                # 写入所有文本到文件
                f_all.write(f"{meta}\n")
                
                # 处理超长文本
                chunks = split_long_text_by_bytes(meta)
                if len(chunks) > 1:
                    f_long.write(f"Table {table_name} has {len(chunks)} chunks\n")
                
                # 为每个chunk添加表名
                for chunk in chunks:
                    all_table_names.append(table_name)
                    all_meta_texts.append(chunk)
                
                print(f"{len(chunks)} chunks.")
                total_count += len(chunks)
            
            # 批量插入
            if all_meta_texts:
                embeddings = await get_embeddings(all_meta_texts, is_local=False)
                entities = [
                    all_table_names,
                    all_meta_texts,
                    embeddings
                ]
                collection.insert(entities)
            
            print(f"Total chunks: {total_count}")
            
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
    print(f"All table meta information embedded and inserted into Milvus collection '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    asyncio.run(main()) 