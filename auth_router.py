
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_async_session
from models import User, Endereco, HistoricoMoradia, Familiar
from schemas import UserRead, UserCreate, UserUpdate
from user_manager import get_user_manager

# --- Configuração do JWT ---
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.JWT_SECRET_KEY, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# --- Instância principal do FastAPIUsers ---
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# --- Rota de Registro Customizada ---
auth_router = APIRouter()

@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def custom_register(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    user_manager = Depends(get_user_manager),
):
    """
    Endpoint de registro de usuário que lida com a criação de entidades aninhadas.
    """
    try:
        # 1. Valida a senha e verifica se o usuário já existe
        await user_manager.validate_password(user_create.password, user_create)
        existing_user = await user_manager.user_db.get_by_email(user_create.email)
        if existing_user:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="REGISTER_USER_ALREADY_EXISTS")

        # 2. Inicia a transação
        async with session.begin_nested() if session.in_transaction() else session.begin() as transaction:
            # 3. Cria ou obtém endereços
            async def get_or_create_endereco(endereco_data: dict) -> Endereco:
                # Lógica simples: sempre cria um novo. Em produção, você pode querer
                # buscar por cidade/estado para evitar duplicatas na tabela `enderecos`.
                endereco = Endereco(**endereco_data)
                session.add(endereco)
                await session.flush()
                return endereco

            cidade_nascimento_obj = await get_or_create_endereco(user_create.cidade_nascimento.dict())
            cidade_atual_obj = await get_or_create_endereco(user_create.cidade_atual.dict())

            # 4. Cria o objeto User
            user_dict = user_create.dict(exclude={"cidade_nascimento", "cidade_atual", "historico_moradia", "familiares"})
            hashed_password = user_manager.password_helper.hash(user_create.password)
            
            db_user = User(
                **user_dict,
                hashed_password=hashed_password,
                cidade_nascimento_id=cidade_nascimento_obj.id,
                cidade_atual_id=cidade_atual_obj.id,
            )
            session.add(db_user)
            await session.flush()

            # 5. Cria Histórico de Moradia
            for hist_data in user_create.historico_moradia:
                endereco_obj = await get_or_create_endereco(hist_data.endereco.dict())
                hist = HistoricoMoradia(
                    periodo=hist_data.periodo,
                    endereco_id=endereco_obj.id,
                    user_id=db_user.id
                )
                session.add(hist)

            # 6. Cria Familiares
            for fam_data in user_create.familiares:
                endereco_obj = await get_or_create_endereco(fam_data.endereco.dict())
                fam = Familiar(
                    nome=fam_data.nome,
                    grau_parentesco=fam_data.grau_parentesco,
                    endereco_id=endereco_obj.id,
                    user_id=db_user.id
                )
                session.add(fam)
            
            await transaction.commit()

        await session.refresh(db_user)
        return db_user

    except Exception as e:
        # Em caso de erro, a transação faz rollback automaticamente
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# --- Inclusão dos Routers Padrão ---
# Router de login/logout
auth_router.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/jwt", tags=["auth"])
# Router de esqueci minha senha
auth_router.include_router(fastapi_users.get_reset_password_router(), tags=["auth"])
# Router de verificação de e-mail
auth_router.include_router(fastapi_users.get_verify_router(UserRead), tags=["auth"])

# Router para gerenciar usuários (GET /me, GET /{id}, PATCH /me, DELETE /me)
users_router = APIRouter()
users_router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), tags=["users"])
