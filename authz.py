import uuid

from fastapi import HTTPException, status

from models import User


def is_admin(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def require_admin(user: User) -> None:
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required.",
        )


def require_owner_or_admin(
    user: User,
    owner_id: uuid.UUID,
    *,
    hide_forbidden: bool = True,
) -> None:
    if owner_id == user.id or is_admin(user):
        return
    raise HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if hide_forbidden
            else status.HTTP_403_FORBIDDEN
        ),
        detail="Resource not found.",
    )
