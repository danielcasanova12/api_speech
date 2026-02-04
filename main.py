
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from auth_router import auth_router as jwt_auth_router, users_router
from sessions_router import router as sessions_router
from recordings_router import router as recordings_router
from database import engine, Base

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API for collecting speech datasets."
)

@app.on_event("startup")
async def on_startup():
    # This ensures all tables are created based on the models.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(jwt_auth_router, prefix="/auth")
app.include_router(users_router, prefix="/users")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(recordings_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

