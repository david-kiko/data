from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio
from .search import search_and_aggregate
from fastmcp import FastMCP
import requests
import httpx
import os

# FastAPI app for HTTP路由
app = FastAPI()

# FastMCP实例
mcp = FastMCP(name="Neo4j Paths Search MCP")

# MCP工具：返回完整list结果
@mcp.tool()
async def search(query: str, top_k: int = 5):
    """在元数据中搜索用户问题，返回与问题相似性最相关的元数据表结构"""
    results = []
    async for item in search_and_aggregate(query, top_k):
        results.append(item)
    return results

@mcp.tool()
async def execute_sql(sql: str):
    """将输入 SQL 语句转发到远程 SQL 执行服务，并返回结果"""
    url = os.getenv("SQL_EXEC_URL", "http://192.168.30.231:18086/api/sql/execute")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json={"sql": sql})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}

# @mcp.tool()
# async def health_check():
#     return {"status": "ok", "version": "1.0.0"}

# FastAPI路由：流式响应
@app.get("/search")
async def search_stream(query: str, top_k: int = 5):
    async def generate():
        async for item in search_and_aggregate(query, top_k):
            yield json.dumps(item, ensure_ascii=False) + '\n'
    return StreamingResponse(generate(), media_type="application/x-ndjson")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp") 