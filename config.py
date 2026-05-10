from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
COOKIE_DIR = BASE_DIR / "cookies"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

ACCOUNTS_FILE = DATA_DIR / "accounts.enc.json"
LEGACY_ACCOUNTS_FILE = BASE_DIR / "accounts.json"
LOGS_FILE = DATA_DIR / "logs.jsonl"
APP_KEY_FILE = DATA_DIR / ".app_key"

DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
