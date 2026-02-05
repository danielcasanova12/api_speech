from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import models
import schemas
from database import get_async_session
from auth_router import fastapi_users

current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(
    prefix="/blocos",
    tags=["blocos"],
)

@router.post("/", response_model=schemas.BlocoRead, status_code=status.HTTP_201_CREATED)
async def create_bloco(
    bloco_in: schemas.BlocoCreate, 
    db: AsyncSession = Depends(get_async_session),
    user: models.User = Depends(current_active_user)
):
    """
    Cria um novo bloco. Requer autenticação.
    """
    result = await db.execute(select(models.Bloco).filter(models.Bloco.nome_bloco == bloco_in.nome_bloco))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Bloco with this name already exists.")
        
    db_bloco = models.Bloco(**bloco_in.model_dump())
    db.add(db_bloco)
    await db.commit()
    await db.refresh(db_bloco)
    return db_bloco

@router.get("/", response_model=List[schemas.BlocoRead])
async def get_all_blocos(db: AsyncSession = Depends(get_async_session)):
    """
    Retorna uma lista de todos os blocos.
    """
    result = await db.execute(select(models.Bloco))
    return result.scalars().all()

@router.get("/{bloco_id}", response_model=schemas.BlocoRead)
async def get_bloco(bloco_id: int, db: AsyncSession = Depends(get_async_session)):
    """
    Retorna um bloco específico pelo seu ID.
    """
    db_bloco = await db.get(models.Bloco, bloco_id)
    if not db_bloco:
        raise HTTPException(status_code=404, detail=f"Bloco with id {bloco_id} not found.")
    return db_bloco

@router.put("/{bloco_id}", response_model=schemas.BlocoRead)
async def update_bloco(
    bloco_id: int,
    bloco_in: schemas.BlocoUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: models.User = Depends(current_active_user)
):
    """
    Atualiza um bloco existente. Requer autenticação.
    """
    db_bloco = await db.get(models.Bloco, bloco_id)
    if not db_bloco:
        raise HTTPException(status_code=404, detail=f"Bloco with id {bloco_id} not found.")
    
    update_data = bloco_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_bloco, key, value)
    
    await db.commit()
    await db.refresh(db_bloco)
    return db_bloco

@router.delete("/{bloco_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bloco(
    bloco_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: models.User = Depends(current_active_user)
):
    """
    Deleta um bloco. Requer autenticação.
    """
    db_bloco = await db.get(models.Bloco, bloco_id)
    if not db_bloco:
        raise HTTPException(status_code=404, detail=f"Bloco with id {bloco_id} not found.")
    
    await db.delete(db_bloco)
    await db.commit()
    return None
