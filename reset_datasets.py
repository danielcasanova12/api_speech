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
    print("AVISO: datasets, blocos e tabelas dependentes serão apagados.")
    try:
        confirmation = input(
            f'Para continuar no alvo {target}, digite exatamente "APAGAR DADOS": '
        )
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.")
        return False
    return confirmation.strip() == "APAGAR DADOS"

def determine_tipo(nome, espontaneidade):
    nome_lower = nome.lower()
    if "ruído" in nome_lower or "ruido" in nome_lower:
        return "ruido"
    elif "leitura" in nome_lower:
        return "leitura"
    elif "respostas" in nome_lower or "resposta" in nome_lower:
        return "resposta"
    elif "emoção" in nome_lower or "emocao" in nome_lower:
        return "emocao_espontanea" if espontaneidade == 1 else "emocao_controlada"
    return ""

async def reset_and_populate(*, assume_yes: bool = False):
    # Lê o arquivo data.txt
    with open("data.txt", "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    # Divide em seções baseado em linhas em branco
    sections = []
    current_section = []
    for line in lines:
        if line.strip() == "":
            if current_section:
                sections.append(current_section)
                current_section = []
        else:
            current_section.append(line)
    if current_section:
        sections.append(current_section)

    if len(sections) < 3:
        print("Erro: O arquivo data.txt não possui as 3 seções esperadas.")
        return False

    datasets_lines = sections[0]
    blocos_lines = sections[1]
    emocoes_lines = sections[2]

    # Processar Datasets
    datasets = []
    for line in datasets_lines:
        parts = line.split('\t')
        if len(parts) >= 2:
            dataset_id = int(parts[0])
            name = parts[1].strip()
            datasets.append({"id": dataset_id, "name": name})

    # Processar Emoções
    emocoes = {}
    for line in emocoes_lines:
        parts = line.split(',')
        if len(parts) >= 2:
            emocao_id = int(parts[0])
            nome_emocao = parts[1].strip()
            emocoes[emocao_id] = nome_emocao
    emocoes[0] = "Nenhuma"

    # Processar Blocos
    blocos = []
    # Ignora o cabeçalho (blockId,name,emocao,espontaneidade)
    for line in blocos_lines[1:]:
        parts = line.split(',')
        if len(parts) >= 4:
            bloco_id = int(parts[0])
            name = parts[1].strip()
            emocao = int(parts[2])
            espontaneidade = int(parts[3])
            
            descricao_emocao = emocoes.get(emocao, "")
            tipo = determine_tipo(name, espontaneidade)
            
            blocos.append({
                "id": bloco_id,
                "nome_bloco": name,
                "emocao_numerico": emocao,
                "espontaniedade": espontaneidade,
                "descricao_emocao": descricao_emocao,
                "tipo": tipo
            })

    if not datasets or not blocos:
        raise ValueError("data.txt deve produzir ao menos um dataset e um bloco")
    dataset_ids = [item["id"] for item in datasets]
    bloco_ids = [item["id"] for item in blocos]
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("data.txt contém IDs de dataset duplicados")
    if len(bloco_ids) != len(set(bloco_ids)):
        raise ValueError("data.txt contém IDs de bloco duplicados")

    target = redact_database_target(DATABASE_URL)
    print(f"Alvo do reset: {target}")
    if not confirm_destructive_reset(target, assume_yes):
        print("Operação cancelada.")
        return False

    async with async_session_maker() as session:
        async with session.begin():
            print("Resetando tabelas datasets, blocos, frases, sessions e recordings...")
            # O TRUNCATE e todas as inserções pertencem à mesma transação.
            await session.execute(text("TRUNCATE TABLE datasets, blocos CASCADE;"))

            print("Inserindo Datasets...")
            for ds in datasets:
                session.add(Dataset(id=ds["id"], name=ds["name"]))

            print("Inserindo Blocos...")
            for bl in blocos:
                session.add(Bloco(
                    id=bl["id"],
                    nome_bloco=bl["nome_bloco"],
                    emocao_numerico=bl["emocao_numerico"],
                    espontaniedade=bl["espontaniedade"],
                    descricao_emocao=bl["descricao_emocao"],
                    tipo=bl["tipo"]
                ))

            await session.flush()
            await session.execute(text("SELECT setval(pg_get_serial_sequence('datasets', 'id'), (SELECT MAX(id) FROM datasets));"))
            await session.execute(text("SELECT setval(pg_get_serial_sequence('blocos', 'id'), (SELECT MAX(id) FROM blocos));"))

        print("Processo concluído com sucesso!")
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
    succeeded = asyncio.run(reset_and_populate(assume_yes=args.yes))
    raise SystemExit(0 if succeeded else 1)
