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
KNOWLEDGE_DATABASE_URL = os.getenv("KNOWLEDGE_DATABASE_URL", "").strip()


PROVIDERS = {
    "openai": {
        "label": "OpenAI / 兼容接口",
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
        "base_url": None,
        "model_env": "OPENAI_MODEL",
        "models_env": "OPENAI_MODELS",
        "default_model": "gpt-4o-mini",
        "models": ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"),
    },
    "deepseek": {
        "label": "DeepSeek",
        "key_env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL",
        "base_url": "https://api.deepseek.com",
        "model_env": "DEEPSEEK_MODEL",
        "models_env": "DEEPSEEK_MODELS",
        "default_model": "deepseek-flash",
        "models": ("deepseek-flash", "deepseek-v4-pro"),
    },
    "gemini": {
        "label": "Gemini",
        "key_env": "GEMINI_API_KEY",
        "base_env": "GEMINI_BASE_URL",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_env": "GEMINI_MODEL",
        "models_env": "GEMINI_MODELS",
        "default_model": "gemini-3.8-flash",
        "models": ("gemini-3.8-flash", "gemini-3.5-flash"),
    },
}


def provider_connection(provider: str) -> tuple[str, str | None]:
    config = PROVIDERS[provider]
    return (
        os.getenv(config["key_env"], "").strip(),
        os.getenv(config["base_env"], "").strip() or config["base_url"],
    )


def available_models() -> list[dict[str, str | bool]]:
    choices = []
    for provider, config in PROVIDERS.items():
        default = os.getenv(config["model_env"], "").strip() or config["default_model"]
        custom = os.getenv(config["models_env"], "").strip()
        models = custom.split(",") if custom else config["models"]
        key, _ = provider_connection(provider)
        for model in dict.fromkeys([default, *(item.strip() for item in models if item.strip())]):
            choices.append({
                "id": f"{provider}:{model}",
                "provider": provider,
                "provider_label": config["label"],
                "model": model,
                "configured": bool(key),
            })
    return choices


DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
