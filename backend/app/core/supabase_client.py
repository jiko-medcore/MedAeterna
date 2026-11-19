from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from app.core.config import settings


# ---- Public / User-scoped Supabase Client ----
if settings.SUPABASE_URL is None:
    raise ValueError("SUPABASE_URL is required")
if settings.SUPABASE_PUBLISHABLE_KEY is None:
    raise ValueError("SUPABASE_PUBLISHABLE_KEY is required")

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_PUBLISHABLE_KEY,
)

def create_caller_scoped_client(verified_access_token: str) -> Client:
    """Create a per-request client whose PostgREST calls carry the caller JWT.

    Call only after the token has been verified. Never cache this client or
    mutate a shared client's auth session with caller-specific credentials.
    """
    if not verified_access_token:
        raise ValueError("A verified caller access token is required")

    options = SyncClientOptions(
        headers={"Authorization": f"Bearer {verified_access_token}"},
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_PUBLISHABLE_KEY,
        options=options,
    )
