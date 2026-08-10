# backend/core/lifespan.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.core.startup import startup
from backend.core.shutdown import shutdown

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup(app)
    yield
    await shutdown(app)
