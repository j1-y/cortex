import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CORTEX_INTERNAL_API_KEY = os.getenv("CORTEX_INTERNAL_API_KEY")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Copy .env.example to .env and set DATABASE_URL "
        "to your Neon PostgreSQL connection string."
    )
