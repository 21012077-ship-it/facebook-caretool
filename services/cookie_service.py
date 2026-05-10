import json
import shutil
from pathlib import Path
from config import COOKIE_DIR
from utils.validators import validate_cookie_file, ValidationError

class CookieService:
    @staticmethod
    def normalize_cookie(cookie: dict) -> dict:
        same_site = str(cookie.get("sameSite", "Lax")).lower()
        mapping = {"no_restriction": "None", "lax": "Lax", "strict": "Strict", "unspecified": "Lax", "none": "None"}
        item = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", ".facebook.com"),
            "path": cookie.get("path", "/"),
            "httpOnly": cookie.get("httpOnly", False),
            "secure": cookie.get("secure", True),
            "sameSite": mapping.get(same_site, "Lax"),
        }
        if "expirationDate" in cookie:
            item["expires"] = int(cookie["expirationDate"])
        elif "expires" in cookie:
            try:
                item["expires"] = int(cookie["expires"])
            except Exception:
                pass
        return item

    def load(self, path: str) -> list[dict]:
        if not path or not Path(path).exists():
            return []
        validate_cookie_file(path)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cookies = data.get("cookies") if isinstance(data, dict) else data
        return [self.normalize_cookie(c) for c in cookies]

    def save(self, path: str, cookies: list[dict]) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)

    def default_cookie_path(self, uid_or_name: str) -> str:
        safe = "".join(ch for ch in (uid_or_name or "account") if ch.isalnum() or ch in "_-.")[:80]
        return str(COOKIE_DIR / f"{safe or 'account'}.json")

    def delete(self, path: str) -> bool:
        if path and Path(path).exists():
            Path(path).unlink()
            return True
        return False

    def import_cookie(self, source_path: str, uid_or_name: str) -> str:
        validate_cookie_file(source_path)
        dest = Path(self.default_cookie_path(uid_or_name))
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(source_path, dest)
        return str(dest)

    def export_cookie(self, source_path: str, dest_path: str) -> str:
        if not source_path or not Path(source_path).exists():
            raise ValidationError("Không có file cookie để export.")
        validate_cookie_file(source_path)
        shutil.copy2(source_path, dest_path)
        return dest_path
