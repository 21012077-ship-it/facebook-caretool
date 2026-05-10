import json
import logging
from datetime import datetime
from pathlib import Path
from config import LOGS_FILE, LOG_DIR

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "app.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    encoding="utf-8",
)

class LogService:
    def __init__(self, path: Path = LOGS_FILE):
        self.path = Path(path)
        self.logger = logging.getLogger("facebook_care_refactor")

    def event(self, action: str, status: str, account: str = "", url: str = "", error: str = "", **extra) -> dict:
        item = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account": account,
            "url": url,
            "action": action,
            "status": status,
            "error": error,
            **extra,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        if error:
            self.logger.error(json.dumps(item, ensure_ascii=False))
        else:
            self.logger.info(json.dumps(item, ensure_ascii=False))
        return item

    def read_recent(self, limit: int = 300) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def clear(self):
        self.path.write_text("", encoding="utf-8")
