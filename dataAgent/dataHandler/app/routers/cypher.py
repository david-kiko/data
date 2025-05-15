from fastapi import APIRouter, Query
from app.neo4j_client import run_cypher_with_pagination
from typing import Optional

router = APIRouter()

@router.get("/paths", summary="获取所有节点的正向路径，支持分页")
def get_paths(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    """
    获取所有节点的正向路径，支持分页。
    """
    results, total = run_cypher_with_pagination(page, page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": results
    } 