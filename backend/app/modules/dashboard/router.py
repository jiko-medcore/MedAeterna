from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from .service import build_user_summary

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/user/summary")
def user_summary(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_patient"):
        raise HTTPException(status_code=403, detail="Access denied")
    return build_user_summary(current_user)
