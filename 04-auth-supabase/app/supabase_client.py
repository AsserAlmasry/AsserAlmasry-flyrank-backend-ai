"""Creates Supabase clients from environment variables (never hard-coded keys)."""
import os

from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client

load_dotenv()


def get_settings() -> tuple[str, str]:
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set (copy .env.example to .env)")
    return url, key


def new_client() -> Client:
    """A fresh client per request.

    The SDK remembers the signed-in session inside the client object. On a server shared by many users,
    one shared client could leak user A's session into user B's request, so each auth call gets its own client.
    """
    url, key = get_settings()
    return create_client(url, key, options=ClientOptions(persist_session=False, auto_refresh_token=False))
