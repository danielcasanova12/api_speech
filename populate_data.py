import asyncio
from sqlalchemy import text
from database import async_session_maker
from models import Dataset, Bloco

def get_tipo_bloco(nome, espontaneidade):
    nome_lower = nome.lower()
    if "ruído" in nome_lower or "ruido" in nome_lower:
        return "ruido"
    if "leitura" in nome_lower:
        return "leitura"
    if "resposta" in nome_lower:
        return "resposta"
    return "emocao_espontanea" if espontaneidade == 1 else "emocao_controlada"

async def main():
    # 1. Ler e processar o arquivo data.txt
    try:
        with open("data.txt", "r", encoding="utf-8") as f:
            raw_content = f.read().strip()
            # Split por blocos de linhas em branco (podem ser uma ou mais)
            import re
            content = re.split(r'\n\s*\n', raw_content)
    except FileNotFoundError:
        print("Erro: Arquivo data.txt não encontrado.")
        return
    
    if len(content) < 3:
        print(f"Erro: O arquivo data.txt deve conter 3 seções. Encontradas: {len(content)}")
        return

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
            except ValueError:
                continue

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
            except ValueError:
                continue

    # 2. Resetar e Inserir no Banco
    async with async_session_maker() as session:
        print("Limpando tabelas existentes (TRUNCATE CASCADE)...")
        await session.execute(text("TRUNCATE TABLE datasets, blocos, frases, sessions, recordings CASCADE;"))
        await session.commit()

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

        await session.commit()
        
        # Ajustar as sequências do ID para o PostgreSQL
        try:
            await session.execute(text("SELECT setval(pg_get_serial_sequence('datasets', 'id'), (SELECT MAX(id) FROM datasets));"))
            await session.execute(text("SELECT setval(pg_get_serial_sequence('blocos', 'id'), (SELECT MAX(id) FROM blocos));"))
            await session.commit()
            print("Sequências de IDs sincronizadas.")
        except Exception as e:
            print(f"Nota: Não foi possível sincronizar sequências (comum em bancos não-Postgres): {e}")

    print("\nProcesso concluído! O banco está limpo e populado com os dados de data.txt.")

if __name__ == "__main__":
    asyncio.run(main())
