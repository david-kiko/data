from fastapi import FastAPI
from app.routers import cypher

app = FastAPI(title="DataHandle Service")

app.include_router(cypher.router, prefix="/cypher", tags=["Cypher"]) 