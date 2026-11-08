import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "llama-3.1-8b-instant")
STRONG_MODEL = os.getenv("STRONG_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"
MAX_RETRIES = 3            # retries after the first attempt
REQUEST_TIMEOUT = 30.0     # seconds
BACKOFF_BASE = 1.0         # waits 1s, 2s, 4s between retries
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")