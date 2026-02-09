from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_async_session
from models import Frase, Bloco
import schemas

router = APIRouter(prefix="/frases", tags=["Frases"])

@router.post("", response_model=schemas.FraseRead, status_code=status.HTTP_201_CREATED)
async def create_frase(
    frase: schemas.FraseCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new phrase.
    """
    # 1. Validate bloco
    db_bloco = await db.get(Bloco, frase.bloco_id)
    if not db_bloco:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bloco with id {frase.bloco_id} not found.")

    # 2. Create new phrase
    new_frase = Frase(**frase.model_dump())
    
    db.add(new_frase)
    await db.commit()
    await db.refresh(new_frase)
    
    return new_frase

@router.get("/{frase_id}", response_model=schemas.FraseRead)
async def get_frase(
    frase_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Gets a specific phrase by its ID.
    """
    db_frase = await db.get(Frase, frase_id)
    if not db_frase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phrase not found.")
    
    return db_frase

@router.get("/bloco/{bloco_id}", response_model=list[schemas.FraseRead])
async def get_frases_by_bloco(
    bloco_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Gets all phrases for a specific bloco.
    """
    result = await db.execute(select(Frase).where(Frase.bloco_id == bloco_id))
    frases = result.scalars().all()
    
    return frases
