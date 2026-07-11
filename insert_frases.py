import asyncio
from database import async_session_maker
from models import Frase
from sqlalchemy.dialects.postgresql import insert

async def main():
    frases_data = [
        {"id": 14, "texto": "This is a placeholder for ID 14", "bloco_id": 5}, # Added just in case it was missing
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
        async with session.begin():
            for data in frases_data:
                stmt = (
                    insert(Frase)
                    .values(
                        id=data["id"],
                        texto=data["texto"],
                        bloco_id=data["bloco_id"],
                    )
                    .on_conflict_do_nothing()
                )
                try:
                    await session.execute(stmt)
                except Exception as exc:
                    raise RuntimeError(
                        f"Falha ao inserir frase_id {data['id']}; nenhuma alteração foi confirmada"
                    ) from exc
                print(f"Processada frase_id {data['id']}")

            # Atualizar a sequência na mesma transação das inserções.
            from sqlalchemy import text

            try:
                await session.execute(
                    text(
                        "SELECT setval("
                        "pg_get_serial_sequence('frases', 'id'), "
                        "COALESCE((SELECT MAX(id) FROM frases), 1), "
                        "EXISTS (SELECT 1 FROM frases)"
                        ");"
                    )
                )
            except Exception as exc:
                raise RuntimeError(
                    "Falha ao sincronizar a sequência de frases; nenhuma alteração foi confirmada"
                ) from exc

        print("Finalizado!")

if __name__ == "__main__":
    asyncio.run(main())
