from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)

from app.core.security import get_current_user

from .schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)

from .service import (
    create_department_service,
    get_department_service,
    list_departments_service,
    update_department_service,
    delete_department_service,
)

from app.modules.organizations.dependencies import (
    require_organization_access,
    require_organization_admin,
)



router = APIRouter(
    prefix="/{organization_id}/departments", 
    tags=["Organization Departments"],
)


# ---------------------------------
# POST / CREATE DEPARTMENT ENDPOINT
# ---------------------------------
@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    organization_id: UUID,
    payload: DepartmentCreate,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin),
):
    return create_department_service(
        organization_id=organization_id,
        payload=payload,
        actor_id=current_user["id"],
    )


# ---------------------------------
# GET / LIST DEPARTMENTS ENDPOINT
# ---------------------------------
@router.get(
    "",
    response_model=list[DepartmentResponse],
)
def list_departments(
    organization_id: UUID,
    organization=Depends(require_organization_access),
):
    return list_departments_service(
        organization_id=organization_id,
    )


# -----------------------------------
# GET / REQUEST A DEPARTMENT ENDPOINT
# -----------------------------------
@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def get_department(
    organization_id: UUID,
    department_id: UUID,
    organization=Depends(require_organization_access),
):
    return get_department_service(
        organization_id=organization_id,
        department_id=department_id,
    )


# -----------------------------------
# PATCH / UPDATE DEPARTMENT ENDPOINT
# -----------------------------------
@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    organization_id: UUID,
    department_id: UUID,
    payload: DepartmentUpdate,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin),
):
    return update_department_service(
        organization_id=organization_id,
        department_id=department_id,
        payload=payload,
        actor_id=current_user["id"],
    )



# --------------------------
# DELETE DEPARTMENT ENDPOINT
# --------------------------
@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_department(
    organization_id: UUID,
    department_id: UUID,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin),
):
    delete_department_service(
        organization_id=organization_id,
        department_id=department_id,
        actor_id=current_user["id"],
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)