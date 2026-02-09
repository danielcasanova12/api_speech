
import uvicorn
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.responses import JSONResponse
import logging
import traceback

from config import settings
from auth_router import auth_router as jwt_auth_router, users_router
from sessions_router import router as sessions_router
from recordings_router import router as recordings_router
from datasets_router import router as datasets_router
from blocos_router import router as blocos_router
from frases_router import router as frases_router
from database import engine, Base

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API for collecting speech datasets."
)

# Custom OpenAPI schema for bearer token authentication in Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token"
        }
    }
    # Apply the security scheme to all operations that need authentication
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            # This is a simple check; you might need to adjust it based on your decorators
            if "tags" in openapi_schema["paths"][path][method] and any(tag.lower() in ["users", "sessions", "recordings", "datasets", "blocos", "frases"] for tag in openapi_schema["paths"][path][method]["tags"]):
                openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

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

# Group all v1 API routers under a single prefix
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(sessions_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(blocos_router)
api_v1_router.include_router(frases_router)
api_v1_router.include_router(recordings_router)
app.include_router(api_v1_router)


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

