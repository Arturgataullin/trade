from fastapi import FastAPI

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.users import router as users_router


app = FastAPI(
    title="Exchange Simulator",
)


app.include_router(
    auth_router,
    prefix="/api",
)
app.include_router(
    users_router,
    prefix="/api",
)

