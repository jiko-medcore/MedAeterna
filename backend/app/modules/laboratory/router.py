from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from .service import build_lab_detail

router = APIRouter()


@router.get("/api/v1/lab-results/{lab_id}")
def get_lab_result(
    lab_id: str,
    current_user: dict = Depends(get_current_user),
):
    return build_lab_detail(lab_id, current_user)

