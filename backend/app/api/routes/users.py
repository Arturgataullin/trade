from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import AdminUser, DbSession
from backend.app.schemas.user import UserRead, UserRoleUpdate
from backend.app.services.users import UserNotFoundError, change_user_role, list_users


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def read_users(
    db: DbSession,
    _admin: AdminUser,
) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in list_users(db)]


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
