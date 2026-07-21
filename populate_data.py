import argparse
import asyncio
from urllib.parse import urlparse

from sqlalchemy import text
from database import DATABASE_URL, async_session_maker
from models import Dataset, Bloco


def redact_database_target(connection_string: str) -> str:
    parsed = urlparse(connection_string)
    host = parsed.hostname or "<host-desconhecido>"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    database_name = parsed.path.lstrip("/") or "<banco-desconhecido>"
    return f"{host}/{database_name}"


def confirm_destructive_reset(target: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    print("AVISO: datasets, blocos, frases, sessões e gravações serão apagados.")
    try:
        confirmation = input(
            f'Para continuar no alvo {target}, digite exatamente "APAGAR DADOS": '
        )
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.")
        return False
    return confirmation.strip() == "APAGAR DADOS"

def get_tipo_bloco(nome, espontaneidade):
    nome_lower = nome.lower()
    if "ruído" in nome_lower or "ruido" in nome_lower:
        return "ruido"
    if "leitura" in nome_lower:
        return "leitura"
    if "resposta" in nome_lower:
        return "resposta"
    return "emocao_espontanea" if espontaneidade == 1 else "emocao_controlada"

async def main(*, assume_yes: bool = False):
    # 1. Ler e processar o arquivo data.txt
    try:
        with open("data.txt", "r", encoding="utf-8") as f:
            raw_content = f.read().strip()
            # Split por blocos de linhas em branco (podem ser uma ou mais)
            import re
            content = re.split(r'\n\s*\n', raw_content)
    except FileNotFoundError:
        print("Erro: Arquivo data.txt não encontrado.")
        return False
    
    if len(content) < 3:
        print(f"Erro: O arquivo data.txt deve conter 3 seções. Encontradas: {len(content)}")
        return False

    # Seção 1: Datasets (ID \t Name)
    datasets_data = []
    for line in content[0].strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2:
            datasets_data.append({"id": int(parts[0]), "name": parts[1].strip()})

    # Seção 3: Mapeamento de Emoções (id,nome)
    emocoes_map = {0: "nenhuma"}
    for line in content[2].strip().split("\n"):
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                emocoes_map[int(parts[0])] = parts[1].strip()
            except ValueError as exc:
                raise ValueError(f"Mapeamento de emoção inválido: {line!r}") from exc

    # Seção 2: Blocos (blockId,name,emocao,espontaneidade)
    blocos_data = []
    lines_blocos = content[1].strip().split("\n")
    for line in lines_blocos:
        if line.startswith("blockId"): continue # Pula cabeçalho
        parts = line.split(",")
        if len(parts) >= 4:
            try:
                b_id = int(parts[0])
                name = parts[1].strip()
                emo_id = int(parts[2])
                espont = int(parts[3])
                
                blocos_data.append({
                    "id": b_id,
                    "nome_bloco": name,
                    "emocao_numerico": emo_id,
                    "espontaniedade": espont,
                    "descricao_emocao": emocoes_map.get(emo_id, ""),
                    "tipo": get_tipo_bloco(name, espont)
                })
            except ValueError as exc:
                raise ValueError(f"Linha de bloco inválida: {line!r}") from exc

    if not datasets_data or not blocos_data:
        raise ValueError("data.txt deve produzir ao menos um dataset e um bloco")
    dataset_ids = [item["id"] for item in datasets_data]
    bloco_ids = [item["id"] for item in blocos_data]
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("data.txt contém IDs de dataset duplicados")
    if len(bloco_ids) != len(set(bloco_ids)):
        raise ValueError("data.txt contém IDs de bloco duplicados")

    target = redact_database_target(DATABASE_URL)
    print(f"Alvo do reset: {target}")
    if not confirm_destructive_reset(target, assume_yes):
        print("Operação cancelada.")
        return False

    # 2. Resetar e Inserir no Banco
    async with async_session_maker() as session:
        async with session.begin():
            print("Limpando tabelas existentes (TRUNCATE CASCADE)...")
            await session.execute(text("TRUNCATE TABLE datasets, blocos, frases, sessions, recordings CASCADE;"))

            print(f"Inserindo {len(datasets_data)} Datasets...")
            for d in datasets_data:
                session.add(Dataset(id=d["id"], name=d["name"]))

            print(f"Inserindo {len(blocos_data)} Blocos...")
            for b in blocos_data:
                session.add(Bloco(
                    id=b["id"],
                    nome_bloco=b["nome_bloco"],
                    emocao_numerico=b["emocao_numerico"],
                    espontaniedade=b["espontaniedade"],
                    descricao_emocao=b["descricao_emocao"],
                    tipo=b["tipo"]
                ))

            await session.flush()
            await session.execute(text("SELECT setval(pg_get_serial_sequence('datasets', 'id'), (SELECT MAX(id) FROM datasets));"))
            await session.execute(text("SELECT setval(pg_get_serial_sequence('blocos', 'id'), (SELECT MAX(id) FROM blocos));"))
            print("Sequências de IDs sincronizadas.")

    print("\nProcesso concluído! O banco está limpo e populado com os dados de data.txt.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Substitui datasets e blocos pelos dados de data.txt."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma a operação destrutiva sem prompt interativo",
    )
    args = parser.parse_args()
    succeeded = asyncio.run(main(assume_yes=args.yes))
    raise SystemExit(0 if succeeded else 1)
