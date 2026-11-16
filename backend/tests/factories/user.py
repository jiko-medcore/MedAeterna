from copy import deepcopy

from .constants import (
    USER_ID,
    ORGANIZATION_ID,
)


_DEFAULT_USER = {
    "id": USER_ID,
    "email": "admin@test.com",
    "role": "org_admin",
    "roles": [
        {
            "name": "org_admin",
            "role_type": "organization",
            "organization_id": str(ORGANIZATION_ID),
            "category": "organization_administrator",
        }
    ],
    "organization_ids": [
        str(ORGANIZATION_ID),
    ],
    "is_patient": False,
    "is_practitioner": False,
    "is_admin": False,
    "is_org_admin": True,
    "is_super_admin": False,
}


def user_factory(**overrides):
    user = deepcopy(_DEFAULT_USER)
    user.update(overrides)
    return user
