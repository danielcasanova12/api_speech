import asyncio
from sqlalchemy import text
from database import async_session_maker
from models import Dataset, Bloco

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

async def reset_and_populate():
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
        return

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

    async with async_session_maker() as session:
        print("Resetando tabelas datasets, blocos, frases, sessions e recordings...")
        # TRUNCATE CASCADE irá limpar datasets, blocos e tabelas dependentes (frases, sessions, recordings)
        # para garantir que os IDs possam ser reinseridos sem conflito.
        await session.execute(text("TRUNCATE TABLE datasets, blocos CASCADE;"))
        await session.commit()
        
        print("Inserindo Datasets...")
        for ds in datasets:
            new_ds = Dataset(id=ds["id"], name=ds["name"])
            session.add(new_ds)
            
        print("Inserindo Blocos...")
        for bl in blocos:
            new_bl = Bloco(
                id=bl["id"],
                nome_bloco=bl["nome_bloco"],
                emocao_numerico=bl["emocao_numerico"],
                espontaniedade=bl["espontaniedade"],
                descricao_emocao=bl["descricao_emocao"],
                tipo=bl["tipo"]
            )
            session.add(new_bl)
            
        await session.commit()
        
        # Ajustar as sequências do PostgreSQL para que novas inserções sigam a partir do último ID inserido
        try:
            await session.execute(text("SELECT setval(pg_get_serial_sequence('datasets', 'id'), (SELECT MAX(id) FROM datasets));"))
            await session.execute(text("SELECT setval(pg_get_serial_sequence('blocos', 'id'), (SELECT MAX(id) FROM blocos));"))
            await session.commit()
        except Exception as e:
            print(f"Aviso ao tentar ajustar as sequences (pode ser ignorado se não estiver usando PostgreSQL): {e}")

        print("Processo concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(reset_and_populate())
