from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
import json
import asyncio
from .search import search_and_aggregate
from fastmcp import FastMCP
import requests
import httpx
import os
import logging
from neo4j import GraphDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Neo4j connection parameters
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://192.168.30.232:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

# FastAPI app for HTTP路由
app = FastAPI()

# FastMCP实例
mcp = FastMCP(name="Neo4j Paths Search MCP")

# MCP工具：返回完整list结果
@mcp.tool()
async def search(query: str, top_k: int = 10):
    """在元数据中搜索用户问题，返回与问题相似性最相关的元数据表结构
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
        
    Returns:
        list[str]: 返回path字符串列表
    """
    logger.info(f"MCP search called with params: query='{query}', top_k={top_k}")
    results = []
    async for path in search_and_aggregate(query, top_k):
        results.append(path)
    return results

@mcp.tool()
async def get_relationship() -> list[str]:
    """获取表之间的关系，返回格式为 ["A(字段名) references B(字段名)"] 的数组
    
    Returns:
        list[str]: 关系数组，每个元素格式为 "A(字段名) references B(字段名)"
    """
    logger.info(f"MCP get_relationship called (no params)")
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            query = """
            MATCH (a:Table)-[r:REFERENCES]->(b:Table)
            RETURN a.name AS source_table, r.from AS source_field,
                   b.name AS target_table, r.to AS target_field
            """
            result = session.run(query)
            relationships = []
            for record in result:
                rel = f"{record['source_table']}({record['source_field']}) references {record['target_table']}({record['target_field']})"
                relationships.append(rel)
            return relationships
    except Exception as e:
        logger.error(f"Error getting relationships: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"获取表关系失败: {str(e)}",
                "type": "database_error"
            }
        )
    finally:
        driver.close()

@mcp.tool()
async def execute_sql(sql: str, limit: int = 20):
    """将输入 SQL 语句转发到远程 SQL 执行服务，并返回结果
    
    Args:
        sql: 要执行的SQL语句
        limit: 返回结果的最大条数，默认为20，-1表示不限制条数
        
    Returns:
        dict: 包含执行结果或错误信息的字典
        
    Raises:
        HTTPException: 当SQL执行出错时抛出，包含详细的错误信息
    """
    logger.info(f"MCP execute_sql called with SQL: {sql}, limit: {limit}")
    url = os.getenv("SQL_EXEC_URL", "http://192.168.30.232:18086/api/sql/execute/v2")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json={"sql": sql, "limit": limit})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_msg = f"SQL执行服务返回错误: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "error": error_msg,
                "sql": sql,
                "limit": limit,
                "status_code": e.response.status_code,
                "response": e.response.text
            }
        )
    except httpx.RequestError as e:
        error_msg = f"SQL执行服务请求失败: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=503,
            detail={
                "error": error_msg,
                "sql": sql,
                "limit": limit,
                "type": "request_error"
            }
        )
    except Exception as e:
        error_msg = f"SQL执行发生未知错误: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "sql": sql,
                "limit": limit,
                "type": "unknown_error"
            }
        )

# FastAPI路由：流式响应
@app.get("/search")
async def search_stream(
    query: str, 
    top_k: int = 10
):
    """流式搜索接口
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
    """
    logger.info(f"HTTP search_stream called with params: query='{query}', top_k={top_k}")
    async def generate():
        async for path in search_and_aggregate(query, top_k):
            yield json.dumps({"path": path}, ensure_ascii=False) + '\n'
    return StreamingResponse(generate(), media_type="application/x-ndjson")

@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp") 