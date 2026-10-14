from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import AdminUser, DbSession
from backend.app.schemas.user import UserRead, UserRoleUpdate
from backend.app.services.users import UserNotFoundError, change_user_role


router = APIRouter(prefix="/users", tags=["users"])


@router.put("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> UserRead:
    try:
        user = change_user_role(db, user_id, data.role)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc

    return UserRead.model_validate(user)
