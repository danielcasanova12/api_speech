import asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from database import async_session_maker
from models import Dataset, Bloco, Frase
 
async def create_datasets(session):
    datasets_to_create = []
    # Voz Geral 1-10
    for i in range(1, 11):
        datasets_to_create.append(f"Voz Geral {i}")
    # Emocao 1-10
    for i in range(1, 11):
        datasets_to_create.append(f"Emocao {i}")
    # Canto 1-10
    for i in range(1, 11):
        datasets_to_create.append(f"Canto {i}")

    print("Creating Datasets...")
    for name in datasets_to_create:
        result = await session.execute(select(Dataset).filter(Dataset.name == name))
        if not result.scalars().first():
            new_dataset = Dataset(name=name)
            session.add(new_dataset)
            print(f"Added Dataset: {name}")
        else:
            print(f"Dataset {name} already exists.")
    await session.commit()

async def create_blocks(session):
    blocks_data = [
        # 1. Leitura
        {
            "nome_bloco": "Bloco de Leitura",
            "descricao": "Frases para leitura controlada em tom neutro",
            "tipo": "leitura",
            "emocao_numerico": 1,
            "descricao_emocao": "neutral",
            "espontaniedade": 0
        },
        # 2. Respostas
        {
            "nome_bloco": "Bloco de Respostas",
            "descricao": "Respostas espontaneas em tom neutro",
            "tipo": "resposta",
            "emocao_numerico": 1,
            "descricao_emocao": "neutral",
            "espontaniedade": 1
        },
        # Controlled Emotions
        {
            "nome_bloco": "Bloco de Emocao neutral",
            "descricao": "Expressao controlada em tom neutro",
            "tipo": "emocao_controlada",
            "emocao_numerico": 1,
            "descricao_emocao": "neutral",
            "espontaniedade": 0
        },
        {
            "nome_bloco": "Bloco de Emocao happy",
            "descricao": "Expressao controlada em tom feliz",
            "tipo": "emocao_controlada",
            "emocao_numerico": 2,
            "descricao_emocao": "happy",
            "espontaniedade": 0
        },
        {
            "nome_bloco": "Bloco de Emocao sad",
            "descricao": "Expressao controlada em tom triste",
            "tipo": "emocao_controlada",
            "emocao_numerico": 3,
            "descricao_emocao": "sad",
            "espontaniedade": 0
        },
        {
            "nome_bloco": "Bloco de Emocao energetic",
            "descricao": "Expressao controlada em tom energetico",
            "tipo": "emocao_controlada",
            "emocao_numerico": 4,
            "descricao_emocao": "energetic",
            "espontaniedade": 0
        },
        {
            "nome_bloco": "Bloco de Emocao motivated",
            "descricao": "Expressao controlada em tom motivado",
            "tipo": "emocao_controlada",
            "emocao_numerico": 5,
            "descricao_emocao": "motivated",
            "espontaniedade": 0
        },
        # Spontaneous Emotions
        {
            "nome_bloco": "Bloco de Emocao neutral espontanea",
            "descricao": "Expressao espontanea em tom neutro",
            "tipo": "emocao_espontanea",
            "emocao_numerico": 1,
            "descricao_emocao": "neutral",
            "espontaniedade": 1
        },
        {
            "nome_bloco": "Bloco de Emocao happy espontanea",
            "descricao": "Expressao espontanea em tom feliz",
            "tipo": "emocao_espontanea",
            "emocao_numerico": 2,
            "descricao_emocao": "happy",
            "espontaniedade": 1
        },
        {
            "nome_bloco": "Bloco de Emocao sad espontanea",
            "descricao": "Expressao espontanea em tom triste",
            "tipo": "emocao_espontanea",
            "emocao_numerico": 3,
            "descricao_emocao": "sad",
            "espontaniedade": 1
        },
        {
            "nome_bloco": "Bloco de Emocao energetic espontanea",
            "descricao": "Expressao espontanea em tom energetico",
            "tipo": "emocao_espontanea",
            "emocao_numerico": 4,
            "descricao_emocao": "energetic",
            "espontaniedade": 1
        },
        {
            "nome_bloco": "Bloco de Emocao motivated espontanea",
            "descricao": "Expressao espontanea em tom motivado",
            "tipo": "emocao_espontanea",
            "emocao_numerico": 5,
            "descricao_emocao": "motivated",
            "espontaniedade": 1
        }
    ]

    print("Creating Blocks...")
    created_blocks = {}
    for block_data in blocks_data:
        result = await session.execute(select(Bloco).filter(Bloco.nome_bloco == block_data["nome_bloco"]))
        existing_block = result.scalars().first()
        
        if not existing_block:
            new_block = Bloco(**block_data)
            session.add(new_block)
            await session.commit()
            await session.refresh(new_block)
            created_blocks[block_data["nome_bloco"]] = new_block
            print(f"Added Block: {block_data['nome_bloco']}")
        else:
            created_blocks[block_data["nome_bloco"]] = existing_block
            print(f"Block {block_data['nome_bloco']} already exists.")
            
    return created_blocks

async def create_phrases(session, blocks):
    phrases_data = {
        "Bloco de Respostas": [
            "O gato subiu no telhado.",
            "Que horas são agora?",
            "A reunião foi adiada para a próxima semana.",
            "Preciso comprar pão e leite no mercado.",
            "O filme começou às oito da noite.",
            "Ela trabalha em um escritório de advocacia.",
            "A importância da educação para o desenvolvimento social e econômico de uma nação é inegável.",
            "Os pesquisadores concluíram que a vacina experimental demonstrou resultados promissores na prevenção de novas infecções.",
            "Você gostaria de café ou chá?",
            "O trânsito estava congestionado por causa de um acidente na rodovia.",
            "Que notícia incrível!"
        ],
        "Bloco de Emocao happy": [
            "Vamos começar o projeto agora mesmo!",
            "Você não vai acreditar no que aconteceu.",
            "Isso é fantástico!",
            "Todos estão muito animados com o resultado.",
            "Essa situação é muito injusta com os bichinhos.", # Wait, check prompt. This sentence looks sad/angry? 
            # Prompt check: "Essa situação é muito injusta com os bichinhos." is listed under FRASES HAPPY in prompt.md?
            # Let me re-read the prompt content provided in previous turn.
            # "FRASES HAPPY (Bloco de Emocao happy) ... Essa situação é muito injusta com os bichinhos."
            # Actually, looking at the prompt content:
            # "FRASES HAPPY ...
            # Vamos começar o projeto agora mesmo!
            # ...
            # Essa situação é muito injusta com os bichinhos.
            # Isso mostra o poder que temos de transformar nossas vidas."
            #
            # It seems weird for "injusta com os bichinhos" to be happy. But I must follow the prompt EXACTLY.
            "Isso mostra o poder que temos de transformar nossas vidas."
        ],
        "Bloco de Emocao sad": [
            "Muitas animais sofrem sem culpa nenhuma.",
            "É difícil ver tanta crueldade no mundo.",
            "Que alegria ver esse animal recebendo uma segunda chance.", # This looks happy? 
            # Prompt check: "FRASES SAD ... Que alegria ver esse animal recebendo uma segunda chance."
            # "Resgates assim restauram minha fé na humanidade."
            # "Histórias de esperança como essa me inspiram demais."
            # Again, mixed sentiments, but I follow the prompt.
            "Resgates assim restauram minha fé na humanidade.",
            "Histórias de esperança como essa me inspiram demais."
        ],
        "Bloco de Emocao motivated": [
            "Quando nos dedicamos, conseguimos alcançar qualquer objetivo.",
            "Histórias assim me motivam a ser uma pessoa melhor."
        ]
    }

    print("Creating Phrases...")
    for block_name, phrases in phrases_data.items():
        block = blocks.get(block_name)
        if not block:
            print(f"Warning: Block {block_name} not found. Skipping phrases.")
            continue
            
        for text in phrases:
            # Check if phrase exists in this block
            result = await session.execute(
                select(Frase).filter(Frase.texto == text, Frase.bloco_id == block.id)
            )
            if not result.scalars().first():
                new_phrase = Frase(texto=text, bloco_id=block.id)
                session.add(new_phrase)
                print(f"Added Phrase to {block_name}: {text[:30]}...")
            else:
                print(f"Phrase already exists in {block_name}: {text[:30]}...")
    await session.commit()

async def main():
    async with async_session_maker() as session:
        await create_datasets(session)
        blocks = await create_blocks(session)
        await create_phrases(session, blocks)
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
