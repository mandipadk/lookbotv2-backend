from typing import Generator
from app.db.supabase import supabase_client

def get_db() -> Generator:
    """Get database connection."""
    try:
        yield supabase_client
    finally:
        pass  # Connection is managed by Supabase client
