import os
from pathlib import Path
from dotenv import load_dotenv

# load repo-root .env then backend/.env (later wins)
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
load_dotenv(_root / "backend" / ".env", override=True)


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
MODEL = env("SENTINEL_MODEL", "claude-opus-5")

NEO4J_URI = env("NEO4J_URI")
NEO4J_USERNAME = env("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = env("NEO4J_PASSWORD")
NEO4J_DATABASE = env("NEO4J_DATABASE", "neo4j")

DUPLO_BASE_URL = env("DUPLO_BASE_URL", "http://localhost:60031").rstrip("/")
DUPLO_TOKEN = env("DUPLO_TOKEN")
DUPLO_WORKSPACE_ID = env("DUPLO_WORKSPACE_ID")
DUPLO_AGENT_ID = env("DUPLO_AGENT_ID")
DUPLO_SCOPE_IDS = [s for s in env("DUPLO_SCOPE_IDS").split(",") if s]
DUPLO_UI_URL = env("DUPLO_UI_URL", "http://localhost:4210").rstrip("/")

VULTR_API_KEY = env("VULTR_API_KEY")
NEBIUS_IAM_TOKEN = env("NEBIUS_IAM_TOKEN")
NEBIUS_PARENT_ID = env("NEBIUS_PARENT_ID")

AUTONOMY = env("SENTINEL_AUTONOMY", "earned")
TICK_SECONDS = float(env("SENTINEL_TICK_SECONDS", "2"))
AUTO_CHAOS = env("SENTINEL_AUTO_CHAOS", "true").lower() == "true"

OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "@preset/duplo-nebius-glm")
BRAVE_API_KEY = env("BRAVE_API_KEY")
