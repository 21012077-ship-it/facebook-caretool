import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from config import DEFAULT_USER_AGENT, DEFAULT_VIEWPORT
from utils.validators import validate_proxy
from utils.totp import get_2fa_code
from .cookie_service import CookieService

class BrowserService:
    """Browser automation service.

    This refactor intentionally does not include evasion/stealth logic. It keeps
    browser creation, cookie loading, cookie checking, and ordinary login/care helpers
    in one place for maintainability.
    """
    def __init__(self, log_service, ui_log=lambda msg: None):
        self.cookies = CookieService()
        self.log_service = log_service
        self.ui_log = ui_log

    def launch_page(self, p, account: dict):
        proxy_config = validate_proxy(account.get("proxy", ""))
        
        # Thêm args để giảm thiểu việc bị phát hiện là automation browser
        launch_options = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        }
        
        if proxy_config:
            launch_options["proxy"] = proxy_config
            
        browser = p.chromium.launch(**launch_options)
        
        # Lấy User-Agent và Viewport từ account, nếu không có thì dùng mặc định
        user_agent = account.get("user_agent", DEFAULT_USER_AGENT)
        viewport = account.get("viewport", DEFAULT_VIEWPORT)
        
        context = browser.new_context(
            viewport=viewport, 
            user_agent=user_agent,
            java_script_enabled=True
        )
        
        loaded = self.cookies.load(account.get("cookie_file", "")) if account.get("cookie_file") else []
        if loaded:
            context.add_cookies(loaded)
            
        page = context.new_page()
        
        # Kích hoạt stealth mode ngay sau khi tạo page và trước khi goto
        stealth_sync(page)
        
        return browser, context, page

    def check_cookie(self, account: dict) -> tuple[bool, str]:
        browser = None
        try:
            with sync_playwright() as p:
                browser, context, page = self.launch_page(p, account)
                page.goto("https://m.facebook.com/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                ok = "login" not in page.url and "checkpoint" not in page.url and "two_step" not in page.url
                return ok, page.url
        finally:
            if browser:
                browser.close()

    def ensure_login(self, context, page, account: dict):
        uid = account.get("uid", "")
        password = account.get("password", "")
        two_fa = account.get("two_fa", "")

        page.goto("https://m.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        if "login" not in page.url and "checkpoint" not in page.url and "two_step_verification" not in page.url:
            return True
        if not uid or not password:
            account["status"] = "cookie_error"
            raise RuntimeError("Cookie không hợp lệ và thiếu UID/password để đăng nhập.")

        self.ui_log(f"[{uid}] Cookie trống/die, đang đăng nhập...")
        page.goto("https://m.facebook.com/login/", wait_until="domcontentloaded", timeout=30000)
        page.locator('input[name="email"], input[id="email"]').first.fill(uid)
        page.locator('input[name="pass"], input[id="pass"]').first.fill(password)
        page.locator('input[name="pass"], input[id="pass"]').first.press("Enter")
        time.sleep(7)

        # Regular 2FA handling, not stealth/evasion.
        code = get_2fa_code(two_fa)
        if code:
            try:
                box = page.locator(
                    'input[aria-label="Mã"], input[aria-label="Login code"], '
                    'input[aria-label="Code"], input[autocomplete="one-time-code"], '
                    'input[id="approvals_code"], input[type="text"]'
                ).locator("visible=true").first
                box.wait_for(state="visible", timeout=12000)
                box.fill(code)
                box.press("Enter")
                time.sleep(7)
            except Exception as e:
                self.ui_log(f"[{uid}] Không nhập được 2FA tự động: {e}")

        if "login" in page.url or "checkpoint" in page.url or "two_step_verification" in page.url:
            account["status"] = "checkpoint"
            raise RuntimeError("Đăng nhập thất bại hoặc dính checkpoint/2FA.")

        account["status"] = "active"
        cookie_file = account.get("cookie_file") or self.cookies.default_cookie_path(uid or account.get("name", "account"))
        account["cookie_file"] = cookie_file
        self.cookies.save(cookie_file, context.cookies())
        return True

    def open_facebook(self, account: dict, control):
        browser = None
        try:
            with sync_playwright() as p:
                browser, context, page = self.launch_page(p, account)
                self.ensure_login(context, page, account)
                page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
                while not page.is_closed():
                    control.check_stop()
                    time.sleep(1)
        finally:
            if browser:
                browser.close()

    def scroll_for_minutes(self, page, minutes: int, pause_range: tuple[int, int], mode: str, account_name: str, control):
        end_time = time.time() + minutes * 60
        while time.time() < end_time:
            control.wait_if_paused()
            if mode == "reels":
                page.keyboard.press("ArrowDown")
            else:
                page.mouse.wheel(0, random.randint(350, 900))
            time.sleep(random.uniform(*pause_range))

    def care_account(self, account: dict, settings: dict, control):
        browser = None
        name = account.get("name", "Unknown")
        self.log_service.event("care", "running", account=name)
        try:
            with sync_playwright() as p:
                browser, context, page = self.launch_page(p, account)
                self.ensure_login(context, page, account)
                
                if settings["newsfeed_minutes"] > 0:
                    control.wait_if_paused()
                    page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
                    time.sleep(random.uniform(4, 7))
                    self.scroll_for_minutes(page, settings["newsfeed_minutes"], settings["pause_range"], "newsfeed", name, control)
                    
                if settings["reels_minutes"] > 0:
                    control.wait_if_paused()
                    page.goto("https://www.facebook.com/reel/", wait_until="domcontentloaded")
                    time.sleep(random.uniform(4, 7))
                    self.scroll_for_minutes(page, settings["reels_minutes"], settings["pause_range"], "reels", name, control)
                    
                self.log_service.event("care", "done", account=name)
        except InterruptedError as e:
            self.log_service.event("care", "stopped", account=name, error=str(e))
            raise
        except Exception as e:
            self.log_service.event("care", "error", account=name, error=str(e))
            raise
        finally:
            if browser:
                browser.close()