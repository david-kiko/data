from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio
from .search import search_and_aggregate
from fastmcp import FastMCP

# FastAPI app for HTTP路由
app = FastAPI()

# FastMCP实例
mcp = FastMCP(name="Neo4j Paths Search MCP")

# MCP工具：返回完整list结果
@mcp.tool()
async def search(query: str, top_k: int = 5):
    results = []
    async for item in search_and_aggregate(query, top_k):
        results.append(item)
    return results

@mcp.tool()
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

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
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp") 