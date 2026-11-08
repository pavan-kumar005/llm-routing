import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "openai/gpt-oss-20b")
STRONG_MODEL = os.getenv("STRONG_MODEL", "openai/gpt-oss-120b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0
BACKOFF_BASE = 1.0

GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

DATABASE_URL = os.getenv("DATABASE_URL", "")
DEFAULT_MONTHLY_LIMIT = int(os.getenv("DEFAULT_MONTHLY_LIMIT", "1000"))

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "8000"))