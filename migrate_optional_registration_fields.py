"""Allow registration language and address fields to be absent in PostgreSQL.

Run once in each existing environment with:
    python migrate_optional_registration_fields.py

The statements are idempotent: running the script again is safe.
"""

import asyncio

from sqlalchemy import text

from database import engine


STATEMENTS = (
    'ALTER TABLE "user" ALTER COLUMN language DROP NOT NULL',
    'ALTER TABLE "user" ALTER COLUMN cidade_nascimento_id DROP NOT NULL',
    'ALTER TABLE "user" ALTER COLUMN cidade_atual_id DROP NOT NULL',
    "ALTER TABLE enderecos ALTER COLUMN cidade DROP NOT NULL",
    "ALTER TABLE enderecos ALTER COLUMN estado DROP NOT NULL",
)


async def run_migration() -> None:
    async with engine.begin() as connection:
        for statement in STATEMENTS:
            await connection.execute(text(statement))
    print("Optional registration fields migration completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_migration())
