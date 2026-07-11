import argparse
import asyncio
import os
import sys
import re
from urllib.parse import urlparse, parse_qs, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import SQLAlchemyError

# Adiciona o diretório raiz ao path para permitir a importação de modelos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importe todos os seus modelos. Eles compartilham um objeto 'metadata'
# que usaremos para criar as tabelas.
from models import Base, User, Session, Dataset, Bloco, Recording, Endereco, HistoricoMoradia, Familiar, PasswordReset, Frase


def redact_database_target(connection_string: str) -> str:
    """Return only host, optional port and database name for confirmation/logging."""
    parsed = urlparse(connection_string)
    host = parsed.hostname or "<host-desconhecido>"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    database_name = parsed.path.lstrip("/") or "<banco-desconhecido>"
    return f"{host}/{database_name}"


def confirm_destructive_reset(target: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True

    print("\nAVISO: este script apagará TODAS as tabelas e dados do alvo acima.")
    try:
        confirmation = input(
            f'Para continuar no alvo {target}, digite exatamente "APAGAR TUDO": '
        )
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.")
        return False
    return confirmation.strip() == "APAGAR TUDO"

def get_env_variable(var_name):
    """Lê uma variável específica de um arquivo .env no diretório atual."""
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    # Use split('=', 1) para lidar com valores que contêm '='
                    key, value = line.strip().split('=', 1)
                    if key == var_name:
                        # Remove aspas que podem envolver o valor
                        return re.sub(r'^"|"$', '', value)
    except FileNotFoundError:
        print("AVISO: Arquivo .env não encontrado.")
        return None
    return None

async def reset_database(*, assume_yes: bool = False):
    """
    Script de reset de banco de dados autocontido e corrigido.
    """
    db_connection_string = get_env_variable('NEONDB_CONNECTION_STRING')
    if not db_connection_string:
        print("ERRO: Não foi possível encontrar NEONDB_CONNECTION_STRING no arquivo .env.")
        return False

    print("--- INICIANDO SCRIPT DE RESET DO BANCO DE DADOS ---")
    target = redact_database_target(db_connection_string)
    print(f"Alvo: {target}")

    if not confirm_destructive_reset(target, assume_yes):
        print("Operação cancelada.")
        return False

    engine = None
    try:
        # --- Lógica de conexão isolada e correta ---
        original_url = urlparse(db_connection_string)
        query_params = parse_qs(original_url.query)
        
        connect_args = {key: value[0] for key, value in query_params.items()}
        if 'sslmode' in connect_args:
            connect_args['ssl'] = connect_args.pop('sslmode')

        # --- Tentativa de lidar com channel_binding explicitamente ---
        # asyncpg pode não gostar de channel_binding como connect_arg direto
        if 'channel_binding' in connect_args:
            # Removemos da lista de connect_args para que não seja passado como kwarg
            # Se o driver precisar disso, ele pode estar em outro lugar ou não ser suportado.
            print("Removendo parâmetro de conexão não suportado: channel_binding")
            del connect_args['channel_binding']

        new_url_parts = (
            original_url.scheme, original_url.netloc, original_url.path,
            original_url.params, '', original_url.fragment
        )
        db_url_clean = urlunparse(new_url_parts)
        DATABASE_URL = db_url_clean.replace("postgresql://", "postgresql+asyncpg://")
        
        engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
        
        metadata = User.metadata
        
        print("\nConectando ao banco de dados...")
        async with engine.begin() as conn:
            print("Conexão bem-sucedida.")
            
            print("Apagando todas as tabelas existentes...")
            await conn.run_sync(metadata.drop_all)
            print("Tabelas apagadas.")
            
            print("Criando todas as tabelas com base nos modelos...")
            await conn.run_sync(metadata.create_all)
            print("Tabelas criadas com sucesso.")

        return True

    except SQLAlchemyError as e:
        print(f"\nOcorreu um erro de banco de dados: {e}")
        return False
    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
        return False
    finally:
        if engine:
            await engine.dispose()
        print("\n--- SCRIPT FINALIZADO ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apaga e recria todas as tabelas do banco configurado."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma a operação destrutiva sem prompt interativo",
    )
    args = parser.parse_args()
    succeeded = asyncio.run(reset_database(assume_yes=args.yes))
    raise SystemExit(0 if succeeded else 1)
