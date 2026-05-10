import json
import re
from pathlib import Path
from urllib.parse import urlparse
import base64

FB_HOST_RE = re.compile(r"(^|\.)facebook\.com$|(^|\.)fb\.watch$|(^|\.)m\.facebook\.com$", re.I)

class ValidationError(ValueError):
    pass

def validate_delay_range(value: str) -> tuple[int, int]:
    value = (value or "").strip()
    m = re.fullmatch(r"\s*(\d{1,5})\s*-\s*(\d{1,5})\s*", value)
    if not m:
        raise ValidationError("Delay phải có định dạng min-max, ví dụ 60-120.")
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo < 0 or hi < 0 or lo > hi:
        raise ValidationError("Delay không hợp lệ: min phải <= max và không âm.")
    return lo, hi

def validate_positive_int(value: str, field_name: str = "Giá trị") -> int:
    try:
        num = int(str(value).strip())
    except Exception:
        raise ValidationError(f"{field_name} phải là số nguyên.")
    if num <= 0:
        raise ValidationError(f"{field_name} phải lớn hơn 0.")
    return num

def validate_facebook_url(value: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(f"URL không hợp lệ: {value}")
    host = parsed.netloc.split(":", 1)[0].lower()
    if not FB_HOST_RE.search(host):
        raise ValidationError(f"URL không phải Facebook/fb.watch: {value}")
    return value

def validate_proxy(proxy_text: str):
    proxy_text = (proxy_text or "").strip()
    if not proxy_text:
        return None
    if "://" in proxy_text:
        parsed = urlparse(proxy_text)
        if parsed.scheme not in {"http", "https", "socks4", "socks5"} or not parsed.hostname or not parsed.port:
            raise ValidationError("Proxy URL phải có dạng http://host:port hoặc socks5://host:port.")
        return {"server": proxy_text}
    parts = proxy_text.split(":")
    if len(parts) == 2 and all(parts):
        host, port = parts
        if not port.isdigit():
            raise ValidationError("Port proxy phải là số.")
        return {"server": f"http://{host}:{port}"}
    if len(parts) >= 4 and all(parts[:4]):
        host, port, user = parts[0], parts[1], parts[2]
        password = ":".join(parts[3:])
        if not port.isdigit():
            raise ValidationError("Port proxy phải là số.")
        return {"server": f"http://{host}:{port}", "username": user, "password": password}
    raise ValidationError("Proxy không đúng định dạng host:port hoặc host:port:user:pass.")

def validate_cookie_file(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        raise ValidationError("File cookie không tồn tại.")
    if p.suffix.lower() != ".json":
        raise ValidationError("File cookie phải là JSON.")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValidationError(f"Cookie JSON không đọc được: {e}")
    cookies = data.get("cookies") if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        raise ValidationError("Cookie JSON phải là list cookie hoặc object có key cookies.")
    for c in cookies:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            raise ValidationError("Cookie item thiếu name/value.")
    return path

def validate_2fa_secret(secret: str) -> str:
    secret = (secret or "").replace(" ", "").upper()
    if not secret:
        return ""
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    try:
        base64.b32decode(padded, casefold=True)
    except Exception:
        raise ValidationError("Secret 2FA không đúng Base32.")
    return secret
