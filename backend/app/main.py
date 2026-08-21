import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.runtime import ArbiCastRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = ArbiCastRuntime(get_settings())
    app.state.runtime = service
    await service.start()
    yield
    await service.close()


app = FastAPI(title="ArbiCast Research API", version="0.2.0", description="Read-only Kalshi × Polymarket market-data research and paper-trading API. No real trading endpoints exist.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])
app.include_router(router)


@app.get("/", summary="Safety boundary")
async def root(): return {"name":"ArbiCast","trading":"disabled","docs":"/docs"}
