from supabase import create_client
from app.core.config import get_settings
from functools import lru_cache

settings = get_settings()

@lru_cache()
def get_supabase_client():
    """Get Supabase client instance."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Create singleton instance
supabase_client = get_supabase_client()
