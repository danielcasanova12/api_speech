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
from models import Frase, Recording, User

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

async def reset_database():
    """
    Script de reset de banco de dados autocontido e corrigido.
    """
    db_connection_string = get_env_variable('NEONDB_CONNECTION_STRING')
    if not db_connection_string:
        print("ERRO: Não foi possível encontrar NEONDB_CONNECTION_STRING no arquivo .env.")
        return

    print("--- INICIANDO SCRIPT DE RESET DO BANCO DE DADOS ---")
    print(f"Alvo: {db_connection_string.split('@')[-1].split('/')[0]}") # Mostra apenas o host
    
    # --- DEBUGGING: Imprime a string de conexão bruta do .env ---
    print(f"[DEBUG] NEONDB_CONNECTION_STRING do .env: {db_connection_string}")

    print("\nAVISO: Este script irá apagar TODAS as tabelas e dados existentes.")
    
    confirmacao = input('Para continuar, digite "sim": ')
    if confirmacao.lower() != "sim":
        print("Operação cancelada.")
        return

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
            print(f"[DEBUG] Removendo 'channel_binding' dos connect_args: {connect_args['channel_binding']}")
            del connect_args['channel_binding']

        new_url_parts = (
            original_url.scheme, original_url.netloc, original_url.path,
            original_url.params, '', original_url.fragment
        )
        db_url_clean = urlunparse(new_url_parts)
        DATABASE_URL = db_url_clean.replace("postgresql://", "postgresql+asyncpg://")
        
        # --- DEBUGGING: Imprime a URL de banco de dados final e os argumentos de conexão ---
        print(f"[DEBUG] DATABASE_URL final para o engine: {DATABASE_URL}")
        print(f"[DEBUG] connect_args final para o engine: {connect_args}")

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

    except SQLAlchemyError as e:
        print(f"\nOcorreu um erro de banco de dados: {e}")
    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
    finally:
        if engine:
            await engine.dispose()
        print("\n--- SCRIPT FINALIZADO ---")

if __name__ == "__main__":
    asyncio.run(reset_database())
