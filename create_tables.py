
import asyncio
from database import Base, engine
# Import all models here so that Base has them registered
from models import User, PasswordReset, Session, Recording, Dataset, Endereco, Familiar, HistoricoMoradia

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(create_tables())
