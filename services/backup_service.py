import base64
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import COOKIE_DIR
from utils.validators import ValidationError

BACKUP_VERSION = 1


class BackupService:
    """Export/import all account data and cookie files in one portable JSON file."""

    def __init__(self, cookie_dir: Path = COOKIE_DIR):
        self.cookie_dir = Path(cookie_dir)

    def export_backup(self, accounts: list[dict], dest_path: str) -> dict:
        destination = Path(dest_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "app": "facebook-caretool",
            "version": BACKUP_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "accounts": [self._pack_account(account) for account in accounts],
        }
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"accounts": len(payload["accounts"]), "path": str(destination)}

    def import_backup(self, source_path: str, existing_accounts: list[dict]) -> dict:
        source = Path(source_path)
        if not source.exists():
            raise ValidationError("File backup không tồn tại.")

        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("app") != "facebook-caretool" or payload.get("version") != BACKUP_VERSION:
            raise ValidationError("File backup không đúng định dạng hoặc không được hỗ trợ.")
        packed_accounts = payload.get("accounts")
        if not isinstance(packed_accounts, list):
            raise ValidationError("File backup không có danh sách tài khoản hợp lệ.")

        accounts = [deepcopy(account) for account in existing_accounts]
        indexes = {
            self._account_key(account): index
            for index, account in enumerate(accounts)
            if self._account_key(account)
        }
        added = 0
        updated = 0
        restored_cookies = 0

        for packed in packed_accounts:
            if not isinstance(packed, dict) or not isinstance(packed.get("data"), dict):
                continue
            account = deepcopy(packed["data"])
            original_cookie_file = account.get("cookie_file", "")
            cookie_path = self._restore_cookie(account, packed.get("cookie"))
            account["cookie_file"] = cookie_path
            if cookie_path and cookie_path != original_cookie_file:
                restored_cookies += 1

            key = self._account_key(account)
            if key and key in indexes:
                accounts[indexes[key]] = account
                updated += 1
            else:
                accounts.append(account)
                if key:
                    indexes[key] = len(accounts) - 1
                added += 1

        return {
            "accounts": accounts,
            "added": added,
            "updated": updated,
            "restored_cookies": restored_cookies,
        }

    def _pack_account(self, account: dict) -> dict:
        packed = {"data": deepcopy(account), "cookie": None}
        cookie_file = account.get("cookie_file")
        if cookie_file and Path(cookie_file).exists():
            cookie_path = Path(cookie_file)
            packed["cookie"] = {
                "filename": cookie_path.name,
                "encoding": "base64",
                "data": base64.b64encode(cookie_path.read_bytes()).decode("ascii"),
            }
        return packed

    def _restore_cookie(self, account: dict, cookie: Optional[dict]) -> str:
        if not cookie:
            return ""
        if cookie.get("encoding") != "base64" or not cookie.get("data"):
            return ""

        filename = self._safe_cookie_filename(account, cookie.get("filename", "cookie.json"))
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cookie_dir / filename
        destination.write_bytes(base64.b64decode(cookie["data"]))
        return str(destination)

    def _safe_cookie_filename(self, account: dict, original_name: str) -> str:
        stem = account.get("uid") or account.get("name") or Path(original_name).stem or "account"
        safe = "".join(ch for ch in stem if ch.isalnum() or ch in "_-.")[:80] or "account"
        return f"{safe}.json"

    @staticmethod
    def _account_key(account: dict) -> str:
        uid = str(account.get("uid", "")).strip()
        if uid:
            return f"uid:{uid}"
        name = str(account.get("name", "")).strip().lower()
        if name:
            return f"name:{name}"
        return ""
