import email
from fastapi import HTTPException
from app.core.supabase_client import supabase
from app.core.supabase_admin import supabase_admin
from app.modules.auth.role_assignment_service import assign_onboarding_role



# ----- Siugnup Service [email & password] -----
def signup_user(email: str, password: str):

    res = supabase.auth.sign_up({
        "email": email,
        "password": password
    })

    # Email confirmation required
    if not res.session:
        return {
            "status": "pending_verification",
            "message": "Check your email to confirm account"
        }

    # User is immediately available
    user = res.user

    if not user:
        raise Exception("Signup failed")

    try:
        # Create patient profile
        supabase_admin.table("profiles").insert({
            "id": user.id,
            "type": "patient"
        }).execute()

        # Get patient role
        role_resp = (
            supabase_admin
            .table("roles")
            .select("id, is_active")
            .eq("name", "patient")
            .eq("role_type", "system")
            .eq("is_active", True)
            .single()
            .execute()
        )

        assign_onboarding_role(
            target_user_id=user.id,
            role_name="patient",
            organization_id=None,
            actor_id=None,
            reason="Patient account created through public signup",
        )

    except Exception as e:
        # Only rollback if session exists (real user created)
        supabase_admin.auth.admin.delete_user(user.id)
        raise Exception(f"Signup failed: {str(e)}")

    return {
        "status": "success",
        "user_id": user.id
    }


# ----- Ensure User Profile Exists -----
def ensure_profile_exists(user_id: str, user_email: str):
    """
    Ensure a profiles row exists for authenticated users. Sync Supabase Auth → DB

    input: user (dict) from get_current_user
    Returns: None
    """
# ---- Check if profile exists ----
    profile = (
        supabase_admin
        .table("profiles")
        .select("id")
        .eq("id", user_id)
        .execute()
    )

    if not profile.data:
        supabase_admin.table("profiles").insert({
            "id": user_id,
            "email": user_email
        }).execute()

    # ---- Check if role already assigned ----
    role_resp = (
        supabase_admin
        .table("roles")
        .select("id")
        .eq("name", "patient")
        .eq("role_type", "system")
        .is_("organization_id", "null")
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not role_resp.data:
        raise HTTPException(status_code=500, detail="Patient role not configured")

    role_check = (
        supabase_admin
        .table("user_roles")
        .select("id")
        .eq("user_id", user_id)
        .eq("role_id", role_resp.data["id"])
        .is_("organization_id", None)
        .eq("status", "active")
        .execute()
    )

    if role_check.data:
        return  # already onboarded (idempotent)

    assign_onboarding_role(
        target_user_id=user_id,
        role_name="patient",
        organization_id=None,
        actor_id=None,
        reason="Patient role provisioned during account reconciliation",
    )


# ---- Login Service [email & password] -----
def login_user(email: str, password: str):

    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    if not response.user or not response.session:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    user_id = response.user.id

    # Ensure onboarding is completed
    ensure_profile_exists(user_id, user_email=email)

    return {
        "access_token": response.session.access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": response.user.email
        },
    }
