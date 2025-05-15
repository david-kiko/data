import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("neo4j").setLevel(logging.ERROR)

from neo4j import GraphDatabase
import os

# Neo4j connection parameters
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://192.168.30.232:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

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

def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # 输出文件放在父级目录下的neo4j_data/all_paths.txt
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(parent_dir, "neo4j_data")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "all_paths.txt")
    page_size = 100
    # 先清空输出文件内容
    with open(output_file, "w", encoding="utf-8") as f:
        pass
    total_count = 0
    try:
        with driver.session() as session, open(output_file, "a", encoding="utf-8") as f:
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
                    for record in data:
                        f.write(f"{record['pathStr']}\n")
                    table_count += len(data)
                    total_count += len(data)
                    if len(data) < page_size:
                        break
                    page += 1
                print(f"{table_count} records.")
            print(f"Total records: {total_count}")
    finally:
        driver.close()
    print(f"All paths written to {output_file}")

if __name__ == "__main__":
    main() 