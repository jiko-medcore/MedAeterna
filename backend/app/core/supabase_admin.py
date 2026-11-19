from supabase import create_client, Client
from app.core.config import settings


# ---- Admin Supabase Client ----
if settings.SUPABASE_URL is None:
    raise ValueError("SUPABASE_URL is required")
if settings.SUPABASE_SECRET_KEY is None:
    raise ValueError("SUPABASE_SECRET_KEY is required")

supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SECRET_KEY
)
