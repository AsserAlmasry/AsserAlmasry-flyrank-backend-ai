"""All settings come from environment variables (.env), never from code."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")


def env(name: str, default: str) -> str:
    return os.getenv(name, default).split("#")[0].strip()


DB_PATH = Path(env("DB_PATH", str(BASE / "data" / "shelfwatch.db")))
CACHE_DIR = BASE / "data" / "page-cache"
REPORTS_DIR = BASE / "data" / "reports"

JWT_SECRET = env("JWT_SECRET", "")
JWT_TTL_MINUTES = int(env("JWT_TTL_MINUTES", "60"))

TARGET_START_URL = env("TARGET_START_URL", "https://books.toscrape.com/catalogue/page-1.html")
SCAN_PAGES = int(env("SCAN_PAGES", "3"))
PAGE_CACHE_HOURS = float(env("PAGE_CACHE_HOURS", "6"))
DEMO_DRIFT = env("DEMO_DRIFT", "0") == "1"

SCHEDULER_ENABLED = env("SCHEDULER_ENABLED", "true").lower() == "true"
SCAN_CRON = env("SCAN_CRON", "0 6 * * *")
REPORT_CRON = env("REPORT_CRON", "0 7 * * 1")
SCHEDULER_TZ = env("SCHEDULER_TZ", "UTC")

LLM_STUB = env("LLM_STUB", "1") == "1"
LLM_BASE_URL = env("LLM_BASE_URL", "http://localhost:11434/v1/")
LLM_API_KEY = env("LLM_API_KEY", "ollama")
LLM_MODEL = env("LLM_MODEL", "gemma3:1b")
LLM_TIMEOUT_S = float(env("LLM_TIMEOUT_S", "30"))
