
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi_users import FastAPIUsers, exceptions
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.exc import IntegrityError

from config import settings
from models import User, Endereco, HistoricoMoradia, Familiar
from schemas import UserRead, UserCreate, UserUpdate
from user_manager import get_user_manager


logger = logging.getLogger(__name__)

# --- JWT Config ---
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.SECRET_KEY, lifetime_seconds=86400)

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
    user_manager = Depends(get_user_manager),
):
    normalized_email = str(user_create.email).strip().lower()

    # 1. Check if user already exists
    existing_user = await user_manager.user_db.get_by_email(normalized_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este endereço de e-mail já está cadastrado."
        )

    session = user_manager.user_db.session
    try:
        await user_manager.validate_password(user_create.password, user_create)
        # Registration is a public endpoint. Permission flags must always be
        # server-controlled, regardless of fields inherited from BaseUserCreate.
        user_dict = user_create.model_dump(
            exclude={
                "cidade_nascimento",
                "cidade_atual",
                "historico_moradia",
                "familiares",
                "password",
                "is_active",
                "is_superuser",
                "is_verified",
            }
        )
        user_dict.update(
            email=normalized_email,
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
        
        # Manually hash the password as we are constructing the User object ourselves
        hashed_password = await run_in_threadpool(
            user_manager.password_helper.hash,
            user_create.password,
        )
        
        # Create the User object without saving it yet
        db_user = User(**user_dict, hashed_password=hashed_password)

        # Create nested address objects and link them
        cidade_nascimento_obj = Endereco(**user_create.cidade_nascimento.model_dump())
        cidade_atual_obj = Endereco(**user_create.cidade_atual.model_dump())
        
        db_user.cidade_nascimento = cidade_nascimento_obj
        db_user.cidade_atual = cidade_atual_obj
        # Keep empty collections loaded in memory. Otherwise response
        # serialization may try to lazy-load them after the commit, which is
        # not supported outside SQLAlchemy's async greenlet context.
        db_user.historico_moradia = []
        db_user.familiares = []

        # Add the main user object and its core addresses to the session
        session.add(db_user)
        
        # Create and add related objects, linking them to the db_user instance
        for hist_data in user_create.historico_moradia:
            endereco_obj = Endereco(**hist_data.endereco.model_dump())
            hist = HistoricoMoradia(periodo=hist_data.periodo, endereco=endereco_obj)
            db_user.historico_moradia.append(hist)
            session.add(hist)

        for fam_data in user_create.familiares:
            endereco_obj = Endereco(**fam_data.endereco.model_dump())
            fam = Familiar(nome=fam_data.nome, grau_parentesco=fam_data.grau_parentesco, endereco=endereco_obj)
            db_user.familiares.append(fam)
            session.add(fam)
        
        # Flush first so database-generated values (notably the user ID) are
        # available while the transaction can still be rolled back. Building
        # a detached response snapshot here prevents any database access while
        # FastAPI serializes the successful response after the commit.
        await session.flush()
        response = UserRead.model_validate(db_user)

        # Commit all objects to the database in one transaction
        await session.commit()
        try:
            await user_manager.on_after_register(db_user)
        except Exception:
            # The account is already durable at this point. A non-critical
            # post-registration hook must not turn success into an error.
            logger.exception("Post-registration hook failed for user %s", db_user.id)
        return response

    except exceptions.InvalidPasswordException as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REGISTER_INVALID_PASSWORD", "reason": error.reason},
        ) from error
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este endereço de e-mail já está cadastrado.",
        )
    except Exception:
        await session.rollback()
        logger.exception("Unexpected error during user registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro inesperado ao criar o usuário. Tente novamente mais tarde."
        )

# --- Standard FastAPIUsers Routers ---
auth_router.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/jwt", tags=["auth"])
auth_router.include_router(fastapi_users.get_reset_password_router(), tags=["auth"])
auth_router.include_router(fastapi_users.get_verify_router(UserRead), tags=["auth"])

users_router = APIRouter()
users_router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), tags=["users"])
