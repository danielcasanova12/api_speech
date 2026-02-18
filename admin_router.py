import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import get_async_session
from models import User, Recording, Session
from auth_router import fastapi_users

# Dependência para garantir que apenas superusuários acessem
current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.delete("/users/delete-by-email", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_and_data_by_email(
    email: str,
    user: User = Depends(current_superuser), # Garante que quem chama é admin
    db: AsyncSession = Depends(get_async_session),
):
    """
    LGPD Compliance: Deleta permanentemente um usuário e TODOS os seus dados associados (sessões, gravações, arquivos).
    Apenas superusuários podem executar esta ação.
    """
    # 1. Buscar o usuário alvo
    result = await db.execute(select(User).where(User.email == email))
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{email}' não encontrado."
        )

    # Não permitir que o admin se delete a si mesmo por engano (opcional, mas seguro)
    if target_user.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode deletar sua própria conta de administrador por aqui."
        )

    print(f"Iniciando deleção completa para o usuário: {target_user.email} (ID: {target_user.id})")

    # 2. Buscar e deletar arquivos físicos (Recordings)
    # Precisamos carregar as gravações antes de deletar o usuário
    recordings_result = await db.execute(
        select(Recording)
        .join(Session)
        .where(Session.user_id == target_user.id)
    )
    recordings = recordings_result.scalars().all()

    deleted_files_count = 0
    errors_count = 0

    for recording in recordings:
        if recording.path_local:
            try:
                if os.path.exists(recording.path_local):
                    os.remove(recording.path_local)
                    deleted_files_count += 1
                    print(f"Arquivo deletado: {recording.path_local}")
                else:
                    print(f"Arquivo não encontrado (já deletado?): {recording.path_local}")
            except Exception as e:
                errors_count += 1
                print(f"Erro ao deletar arquivo {recording.path_local}: {e}")

    # 3. Deletar o usuário do banco
    # Devido ao 'cascade="all, delete-orphan"' nos models, isso deve levar:
    # - Sessions
    # - Recordings (registros no banco)
    # - HistoricoMoradia
    # - Familiares
    # - PasswordResets
    try:
        await db.delete(target_user)
        await db.commit()
        print(f"Usuário {email} e dados relacionados removidos do banco.")
        print(f"Arquivos físicos removidos: {deleted_files_count}. Erros: {errors_count}.")
        
    except Exception as e:
        await db.rollback()
        print(f"Erro ao deletar usuário do banco: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar usuário: {str(e)}"
        )

    return None # 204 No Content
