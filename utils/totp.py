import pyotp
from .validators import validate_2fa_secret

def get_2fa_code(secret: str) -> str | None:
    try:
        normalized = validate_2fa_secret(secret)
        if not normalized:
            return None
        padded = normalized + "=" * ((8 - len(normalized) % 8) % 8)
        return pyotp.TOTP(padded).now()
    except Exception:
        return None
