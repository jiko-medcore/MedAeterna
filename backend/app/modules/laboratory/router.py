from fastapi import APIRouter, Depends

from app.core.clinical_authorization import authorize_table_access
from app.core.security import get_current_user
from .service import build_lab_detail

router = APIRouter()


@router.get("/api/v1/lab-results/{lab_id}")
def get_lab_result(
    lab_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorized_context = authorize_table_access(
        current_user,
        "lab_results",
        str(lab_id),
        "read",
        relationship_resource_family="lab_result",
    )
    return build_lab_detail(
        str(lab_id),
        authorized_context=authorized_context,
    )
