
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from config import settings
from database import get_async_session
from models import User, Endereco, HistoricoMoradia, Familiar
from schemas import UserRead, UserCreate, UserUpdate
from user_manager import get_user_manager

# --- JWT Config ---
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.SECRET_KEY, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# --- FastAPIUsers Instance ---
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# --- Custom Register Route ---
auth_router = APIRouter()

@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def custom_register(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    user_manager = Depends(get_user_manager),
):
    # This function now correctly handles the creation of a user and all related
    # nested objects within a single, coherent database transaction.
    
    # 1. Check if user already exists
    existing_user = await user_manager.user_db.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="REGISTER_USER_ALREADY_EXISTS")

    try:
        # Create a dictionary of the user data, excluding fields we'll handle manually
        user_dict = user_create.model_dump(exclude={"cidade_nascimento", "cidade_atual", "historico_moradia", "familiares", "password"})
        
        # Manually hash the password as we are constructing the User object ourselves
        hashed_password = user_manager.password_helper.hash(user_create.password)
        
        # Create the User object without saving it yet
        db_user = User(**user_dict, hashed_password=hashed_password)

        # Create nested address objects and link them
        cidade_nascimento_obj = Endereco(**user_create.cidade_nascimento.model_dump())
        cidade_atual_obj = Endereco(**user_create.cidade_atual.model_dump())
        
        db_user.cidade_nascimento = cidade_nascimento_obj
        db_user.cidade_atual = cidade_atual_obj

        # Add the main user object and its core addresses to the session
        session.add(db_user)
        
        # Create and add related objects, linking them to the db_user instance
        for hist_data in user_create.historico_moradia:
            endereco_obj = Endereco(**hist_data.endereco.model_dump())
            hist = HistoricoMoradia(periodo=hist_data.periodo, endereco=endereco_obj, user=db_user)
            session.add(hist)

        for fam_data in user_create.familiares:
            endereco_obj = Endereco(**fam_data.endereco.model_dump())
            fam = Familiar(nome=fam_data.nome, grau_parentesco=fam_data.grau_parentesco, endereco=endereco_obj, user=db_user)
            session.add(fam)
        
        # Commit all objects to the database in one transaction
        await session.commit()
        
        # Eagerly load relationships before returning
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.historico_moradia),
                selectinload(User.familiares)
            )
            .where(User.id == db_user.id)
        )
        db_user = result.scalars().one()

        return db_user

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Standard FastAPIUsers Routers ---
auth_router.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/jwt", tags=["auth"])
auth_router.include_router(fastapi_users.get_reset_password_router(), tags=["auth"])
auth_router.include_router(fastapi_users.get_verify_router(UserRead), tags=["auth"])

users_router = APIRouter()
users_router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), tags=["users"])
