from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
STATIC_DIR = BASE_DIR / "static"

# Load project-local settings before any service reads os.environ.
load_dotenv(BASE_DIR / ".env", override=False)

# Conversation data can be stored in PostgreSQL while the rest of the local
# workspace continues to use SQLite. Prefer the scoped variable to avoid
# accidentally moving unrelated tables when a generic DATABASE_URL is present.
CHAT_DATABASE_URL = os.getenv("CHAT_DATABASE_URL") or os.getenv("DATABASE_URL") or ""

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
