from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import models
import schemas
from database import get_async_session
from auth_router import fastapi_users

current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
)

@router.post(
    "/",
    response_model=schemas.Dataset,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    dataset_in: schemas.DatasetCreate, 
    db: AsyncSession = Depends(get_async_session),
    user: models.User = Depends(current_superuser)
):
    """
    Cria um novo dataset. Apenas superusuários podem criar.
    """
    # Verifica se já existe um dataset com o mesmo nome para evitar duplicatas
    result = await db.execute(select(models.Dataset).filter(models.Dataset.name == dataset_in.name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Dataset with this name already exists.")
        
    db_dataset = models.Dataset(**dataset_in.model_dump())
    db.add(db_dataset)
    await db.commit()
    await db.refresh(db_dataset)
    return db_dataset

@router.get("/", response_model=list[schemas.Dataset])
async def get_datasets(db: AsyncSession = Depends(get_async_session)):
    """
    Retorna uma lista de todos os datasets existentes.
    """
    result = await db.execute(select(models.Dataset))
    datasets = result.scalars().all()
    return datasets

@router.get("/{dataset_id}", response_model=schemas.Dataset)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_async_session)):
    """
    Retorna um dataset específico pelo seu ID.
    """
    db_dataset = await db.get(models.Dataset, dataset_id)
    if not db_dataset:
        raise HTTPException(status_code=404, detail=f"Dataset with id {dataset_id} not found.")
    return db_dataset

@router.put("/{dataset_id}", response_model=schemas.Dataset)
async def update_dataset(
    dataset_id: int,
    dataset_in: schemas.DatasetUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: models.User = Depends(current_superuser)
):
    """
    Atualiza um dataset existente. Apenas superusuários podem alterar.
    """
    db_dataset = await db.get(models.Dataset, dataset_id)
    if not db_dataset:
        raise HTTPException(status_code=404, detail=f"Dataset with id {dataset_id} not found.")
    
    # Verifica se o novo nome já está em uso por outro dataset
    if dataset_in.name != db_dataset.name:
        result = await db.execute(select(models.Dataset).filter(models.Dataset.name == dataset_in.name))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Dataset with this name already exists.")

    # Preserve the previous type when older clients omit dataset_type, while
    # persisting it whenever it is explicitly supplied.
    for key, value in dataset_in.model_dump(exclude_unset=True).items():
        setattr(db_dataset, key, value)
    await db.commit()
    await db.refresh(db_dataset)
    return db_dataset
