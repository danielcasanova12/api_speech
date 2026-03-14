import asyncio
from database import async_session_maker
from models import Frase
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

async def main():
    frases_data = [
        {"id": 1, "texto": "O gato subiu no telhado.", "bloco_id": 2},
        {"id": 2, "texto": "Que horas são agora?", "bloco_id": 2},
        {"id": 3, "texto": "A reunião foi adiada para a próxima semana.", "bloco_id": 2},
        {"id": 4, "texto": "Preciso comprar pão e leite no mercado.", "bloco_id": 2},
        {"id": 5, "texto": "O filme começou às oito da noite.", "bloco_id": 2},
        {"id": 6, "texto": "Ela trabalha em um escritório de advocacia.", "bloco_id": 2},
        {"id": 7, "texto": "A importância da educação para o desenvolvimento social e econômico de uma nação é inegável.", "bloco_id": 2},
        {"id": 8, "texto": "Os pesquisadores concluíram que a vacina experimental demonstrou resultados promissores na prevenção de novas infecções.", "bloco_id": 2},
        {"id": 9, "texto": "Você gostaria de café ou chá?", "bloco_id": 2},
        {"id": 10, "texto": "O trânsito estava congestionado por causa de um acidente na rodovia.", "bloco_id": 2},
        {"id": 11, "texto": "Que notícia incrível!", "bloco_id": 5},
        {"id": 12, "texto": "Vamos começar o projeto agora mesmo!", "bloco_id": 5},
        {"id": 13, "texto": "Você não vai acreditar no que aconteceu.", "bloco_id": 5},
        {"id": 14, "texto": "Isso é fantástico!", "bloco_id": 5},
        {"id": 15, "texto": "Todos estão muito animados com o resultado.", "bloco_id": 5},
        {"id": 16, "texto": "", "bloco_id": 56},
        {"id": 17, "texto": "Dói no coração ver uma criança precisando pedir ajuda na rua.", "bloco_id": 56},
        {"id": 18, "texto": "Ninguém deveria crescer sem ter o básico garantido.", "bloco_id": 56},
        {"id": 19, "texto": "É triste precisar depender da bondade alheia pra sobreviver.", "bloco_id": 56},
        {"id": 20, "texto": "", "bloco_id": 55},
        {"id": 21, "texto": "Ver essa menina de uniforme me deixou sem palavras.", "bloco_id": 55},
        {"id": 22, "texto": "Pequenos gestos podem mudar a história de uma vida inteira.", "bloco_id": 55},
        {"id": 23, "texto": "Que emoção saber que ela agora tem um futuro pela frente.", "bloco_id": 55},
        {"id": 24, "texto": "", "bloco_id": 105},
        {"id": 25, "texto": "Isso mostra o poder que temos de transformar nossas vidas.", "bloco_id": 105},
        {"id": 26, "texto": "Quando nos dedicamos, conseguimos alcançar qualquer objetivo.", "bloco_id": 105},
        {"id": 27, "texto": "Nenhuma conquista grande vem sem sacrifício.", "bloco_id": 105},
    ]

    async with async_session_maker() as session:
        # Update or Insert
        for data in frases_data:
            stmt = insert(Frase).values(id=data["id"], texto=data["texto"], bloco_id=data["bloco_id"])
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_=dict(texto=stmt.excluded.texto, bloco_id=stmt.excluded.bloco_id)
            )
            try:
                await session.execute(stmt)
                print(f"Atualizada/Inserida frase_id {data['id']}")
            except Exception as e:
                print(f"Erro ao inserir frase_id {data['id']}: {e}")
                
        # Atualizar a sequência do ID
        from sqlalchemy import text
        await session.execute(text("SELECT setval('frases_id_seq', (SELECT MAX(id) FROM frases));"))
        await session.commit()
        print("Finalizado!")

if __name__ == "__main__":
    asyncio.run(main())
