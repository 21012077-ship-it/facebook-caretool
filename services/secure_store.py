import json
import shutil
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from config import ACCOUNTS_FILE, APP_KEY_FILE, LEGACY_ACCOUNTS_FILE

SENSITIVE_FIELDS = {"uid", "password", "two_fa", "proxy", "cookie_file"}

class SecureAccountStore:
    def __init__(self, path: Path = ACCOUNTS_FILE, key_path: Path = APP_KEY_FILE):
        self.path = Path(path)
        self.key_path = Path(key_path)
        self.fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def load(self) -> list[dict]:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                token = payload.get("data", "")
                plain = self.fernet.decrypt(token.encode("utf-8"))
                return json.loads(plain.decode("utf-8"))
            except InvalidToken as e:
                raise RuntimeError("Không giải mã được accounts.enc.json. Có thể thiếu/sai file data/.app_key.") from e
            except Exception as e:
                raise RuntimeError(f"Không đọc được kho account đã mã hóa: {e}") from e
        if LEGACY_ACCOUNTS_FILE.exists():
            accounts = json.loads(LEGACY_ACCOUNTS_FILE.read_text(encoding="utf-8"))
            if not isinstance(accounts, list):
                accounts = []
            self.save(accounts)
            backup = LEGACY_ACCOUNTS_FILE.with_suffix(".json.bak")
            shutil.copy2(LEGACY_ACCOUNTS_FILE, backup)
            return accounts
        return []

    def save(self, accounts: list[dict]) -> None:
        plain = json.dumps(accounts, ensure_ascii=False, indent=2).encode("utf-8")
        token = self.fernet.encrypt(plain).decode("utf-8")
        self.path.write_text(json.dumps({"version": 1, "encrypted": True, "data": token}, indent=2), encoding="utf-8")

    @staticmethod
    def public_account(account: dict) -> dict:
        masked = dict(account)
        for field in SENSITIVE_FIELDS:
            if masked.get(field):
                masked[field] = "••••••"
        return masked
