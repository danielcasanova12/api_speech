import asyncio
import os
import sys
from sqlalchemy.exc import SQLAlchemyError

# Adiciona o diretório raiz ao path para permitir a importação de módulos da aplicação
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
from config import settings

# Importe todos os seus modelos aqui para que o SQLAlchemy os reconheça.
# O SQLAlchemy 'Base.metadata' rastreia as classes que herdam de Base.
from models import (
    User,
    Endereco,
    HistoricoMoradia,
    Familiar,
    PasswordReset,
    Dataset,
    Session,
    Recording,
)


async def reset_database():
    """
    ATENÇÃO: Este script é destrutivo.
    Ele se conectará ao banco de dados especificado na variável de ambiente
    NEONDB_CONNECTION_STRING, excluirá TODAS as tabelas e as recriará do zero.
    TODOS OS DADOS SERÃO PERDIDOS.
    """
    
    db_connection_string = settings.NEONDB_CONNECTION_STRING
    if not db_connection_string:
        print("ERRO: A variável de ambiente NEONDB_CONNECTION_STRING não está definida.")
        print("Por favor, configure-a no seu arquivo .env.")
        return

    print("--- INICIANDO SCRIPT DE RESET DO BANCO DE DADOS ---")
    print(f"Alvo: {db_connection_string.split('@')[-1]}") # Mostra o host para segurança
    print("\nAVISO: Este script irá apagar TODAS as tabelas e dados existentes")
    print("e recriar a estrutura do zero.")
    
    confirmacao = input('Para continuar, digite "sim": ')
    
    if confirmacao.lower() != "sim":
        print("Operação cancelada.")
        return
        
    print("\nConectando ao banco de dados...")
    try:
        async with engine.begin() as conn:
            print("Conexão bem-sucedida.")
            
            print("Apagando todas as tabelas existentes (se houver)...")
            await conn.run_sync(Base.metadata.drop_all)
            print("Tabelas apagadas.")
            
            print("Criando todas as tabelas com base nos modelos...")
            await conn.run_sync(Base.metadata.create_all)
            print("Tabelas criadas com sucesso.")

    except SQLAlchemyError as e:
        print(f"\nOcorreu um erro de banco de dados: {e}")
        print("Verifique sua string de conexão e se o banco de dados está acessível.")
    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
    finally:
        # Garante que a pool de conexões do engine seja fechada.
        await engine.dispose()
        print("\n--- SCRIPT FINALIZADO ---")


if __name__ == "__main__":
    # Executa a função assíncrona
    asyncio.run(reset_database())