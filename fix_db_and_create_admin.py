import asyncio
from datetime import date
import sys
from getpass import getpass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from database import async_session_maker, engine
from models import User, Endereco
from config import settings
from passlib.context import CryptContext

# Configuração de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def fix_database_columns():
    """
    Verifica se as colunas de controle do FastAPI Users existem e as adiciona se necessário.
    """
    print("--- Verificando Estrutura do Banco de Dados ---")
    async with engine.connect() as conn:
        # Colunas que o FastAPI Users exige
        required_columns = {
            "is_superuser": "BOOLEAN DEFAULT FALSE NOT NULL",
            "is_active": "BOOLEAN DEFAULT TRUE NOT NULL",
            "is_verified": "BOOLEAN DEFAULT FALSE NOT NULL"
        }
        
        for column, column_type in required_columns.items():
            try:
                # Tenta fazer um select simples na coluna para ver se ela existe
                await conn.execute(text(f"SELECT {column} FROM \"user\" LIMIT 1"))
                print(f"OK: Coluna '{column}' já existe.")
            except Exception:
                # Se der erro, assume que a coluna não existe e tenta adicionar
                print(f"AVISO: Coluna '{column}' não encontrada. Tentando adicionar...")
                try:
                    await conn.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {column} {column_type}"))
                    await conn.commit()
                    print(f"SUCESSO: Coluna '{column}' adicionada.")
                except Exception as e:
                    print(f"ERRO ao adicionar coluna '{column}': {e}")
        
        await conn.commit()

async def create_superuser():
    """
    Cria o usuário administrador.
    """
    print("Criação de Superusuário (Admin) ---")
    email = "danil.s.c9090@gmail.com"
    if not email:
        print("Email é obrigatório.")
        return

    password = getpass("Senha do Admin: ")
    if not password:
        print("Senha é obrigatória.")
        return
    
    confirm_password = getpass("Confirme a senha: ")
    if password != confirm_password:
        print("As senhas não conferem.")
        return

    nome_completo = "daniel"

    async with async_session_maker() as session:
        # Verificar se usuário já existe
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"AVISO: O usuário {email} já existe. Deseja transformá-lo em Superuser? (s/n)")
            opcao = input().lower()
            if opcao == 's':
                existing_user.is_superuser = True
                existing_user.is_active = True
                existing_user.is_verified = True
                await session.commit()
                print(f"SUCESSO: Usuário {email} agora é Superusuário.")
            return

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
            
        except Exception as e:
            await session.rollback()
            print(f"ERRO ao criar usuário: {e}")

async def main():
    await fix_database_columns()
    await create_superuser()
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
