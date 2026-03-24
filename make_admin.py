import asyncio
import sys
import argparse
from sqlalchemy.future import select

from database import async_session_maker, engine
from models import User

async def make_user_admin(email: str, remove_admin: bool = False):
    """
    Torna um usuário existente um administrador (superuser) ou remove o privilégio.
    """
    print(f"Buscando usuário com email: {email}...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"ERRO: Usuário com email '{email}' não encontrado no banco de dados.")
            return

        if remove_admin:
            if not user.is_superuser:
                print(f"AVISO: O usuário '{email}' já NÃO é um administrador.")
            else:
                user.is_superuser = False
                await session.commit()
                print(f"SUCESSO: Privilégios de administrador REMOVIDOS do usuário '{email}'.")
        else:
            if user.is_superuser:
                print(f"AVISO: O usuário '{email}' já é um administrador.")
            else:
                user.is_superuser = True
                user.is_active = True # Garante que ele pode logar
                await session.commit()
                print(f"SUCESSO: O usuário '{email}' agora é um ADMINISTRADOR (Superusuário).")

async def main():
    parser = argparse.ArgumentParser(description="Gerenciar privilégios de administrador de usuários.")
    parser.add_argument("email", help="O email do usuário alvo")
    parser.add_argument("--remove", action="store_true", help="Remove os privilégios de administrador em vez de conceder")
    
    args = parser.parse_args()
    
    await make_user_admin(args.email, args.remove)
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
