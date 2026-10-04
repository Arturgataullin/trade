from fastapi import FastAPI

from backend.app.api.routes.auth import router as auth_router


app = FastAPI(
    title="Exchange Simulator",
)


app.include_router(
    auth_router,
    prefix="/api",
)


@app.get("/health")
def health():
    return {"status": "ok"}