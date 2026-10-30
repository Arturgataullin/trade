from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.market import router as market_router
from backend.app.api.routes.simulations import router as simulations_router
from backend.app.api.routes.users import router as users_router
from backend.app.api.routes.simulation_results import router as results_router
from backend.app.db.session import SessionLocal
from backend.app.services.simulation_execution import SimulationWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = SimulationWorker(SessionLocal)
    worker.start()
    try:
        yield
    finally:
        await run_in_threadpool(worker.stop)


app = FastAPI(
    title="Exchange Simulator",
    lifespan=lifespan,
)


app.include_router(
    auth_router,
    prefix="/api",
)
app.include_router(
    users_router,
    prefix="/api",
)
app.include_router(
    market_router,
    prefix="/api",
)
app.include_router(
    simulations_router,
    prefix="/api",
)
app.include_router(results_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}

