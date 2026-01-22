import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from router import api_router
from auth_router import auth_router as jwt_auth_router, users_router
from database import engine
from models import Base

app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
)

@app.on_event("startup")
async def on_startup():
    # Cria as tabelas do SQLAlchemy (User, Endereco, etc.)
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

# Inclui o router de autenticação (login, registro, etc.)
app.include_router(jwt_auth_router, prefix="/auth")

# Inclui o router de usuários (gerenciamento de perfil)
app.include_router(users_router, prefix="/users")

# Inclui seu router de API existente
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
