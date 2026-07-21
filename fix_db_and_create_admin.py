import argparse
import asyncio
from datetime import date
import sys
from getpass import getpass
from sqlalchemy import inspect, select, text

from database import async_session_maker, engine
from models import User, Endereco
from passlib.context import CryptContext

# Configuração de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def fix_database_columns():
    """
    Verifica se as colunas de controle do FastAPI Users existem e as adiciona se necessário.
    """
    print("--- Verificando Estrutura do Banco de Dados ---")
    async with engine.begin() as conn:
        # Colunas que o FastAPI Users exige
        required_columns = {
            "is_superuser": "BOOLEAN DEFAULT FALSE NOT NULL",
            "is_active": "BOOLEAN DEFAULT TRUE NOT NULL",
            "is_verified": "BOOLEAN DEFAULT FALSE NOT NULL"
        }

        existing_columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"]
                for column in inspect(sync_conn).get_columns("user")
            }
        )

        for column, column_type in required_columns.items():
            if column in existing_columns:
                print(f"OK: Coluna '{column}' já existe.")
            else:
                print(f"AVISO: Coluna '{column}' não encontrada. Tentando adicionar...")
                await conn.execute(
                    text(f'ALTER TABLE "user" ADD COLUMN {column} {column_type}')
                )
                print(f"SUCESSO: Coluna '{column}' adicionada.")


async def create_superuser(email: str):
    """
    Cria o usuário administrador.
    """
    print("Criação de Superusuário (Admin) ---")
    email = email.strip()
    if not email:
        print("Email é obrigatório.")
        return False

    password = getpass("Senha do Admin: ")
    if not password:
        print("Senha é obrigatória.")
        return False
    
    confirm_password = getpass("Confirme a senha: ")
    if password != confirm_password:
        print("As senhas não conferem.")
        return False

    nome_completo = "daniel"

    async with async_session_maker() as session:
        # Verificar se usuário já existe
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"AVISO: O usuário {email} já existe. Deseja transformá-lo em Superuser? (s/n)")
            try:
                opcao = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nOperação cancelada.")
                return False
            if opcao == 's':
                existing_user.is_superuser = True
                existing_user.is_active = True
                existing_user.is_verified = True
                await session.commit()
                print(f"SUCESSO: Usuário {email} agora é Superusuário.")
                return True
            print("Operação cancelada.")
            return False

        try:
            # Hash da senha
            hashed_password = pwd_context.hash(password)

            # Criar endereços básicos (necessários pelo seu Model)
            end_nasc = Endereco(cidade="São Paulo", estado="SP")
            end_atual = Endereco(cidade="São Paulo", estado="SP")

            # Criar usuário com todas as flags de permissão
            new_user = User(
                email=email,
                hashed_password=hashed_password,
                nome_completo=nome_completo,
                data_nascimento=date(2000, 1, 1), 
                is_superuser=True,
                is_active=True,
                is_verified=True,
                cidade_nascimento=end_nasc,
                cidade_atual=end_atual
            )
            
            session.add(new_user)
            await session.commit()
            print(f"SUCESSO: Superusuário {email} criado com sucesso!")
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"ERRO ao criar usuário: {e}")
            return False

async def main(email: str):
    try:
        await fix_database_columns()
        return await create_superuser(email)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Corrige colunas do FastAPI Users e cria/promove um administrador."
    )
    parser.add_argument(
        "--email",
        help="Email do administrador; se omitido, será solicitado interativamente",
    )
    args = parser.parse_args()

    admin_email = args.email
    if not admin_email:
        try:
            admin_email = input("Email do Admin: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperação cancelada.")
            raise SystemExit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    succeeded = asyncio.run(main(admin_email))
    raise SystemExit(0 if succeeded else 1)
