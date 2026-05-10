import random
import time
from playwright.sync_api import sync_playwright
from utils.spin import spin_text
from .browser_service import BrowserService

class CommentCampaignService:
    def __init__(self, browser_service: BrowserService, log_service, ui_log=lambda msg: None):
        self.browser_service = browser_service
        self.log_service = log_service
        self.ui_log = ui_log

    def distribute_urls(self, account_indexes: list[int], urls: list[str], limit_per_account: int) -> dict[int, list[str]]:
        tasks = {idx: [] for idx in account_indexes}
        cursor = 0
        for url in urls:
            attempts = 0
            while attempts < len(account_indexes):
                idx = account_indexes[cursor % len(account_indexes)]
                cursor += 1
                attempts += 1
                if len(tasks[idx]) < limit_per_account:
                    tasks[idx].append(url)
                    break
        return {idx: items for idx, items in tasks.items() if items}

    def run(self, accounts: list[dict], account_indexes: list[int], urls: list[str], raw_content: str, settings: dict, control):
        lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Không tìm thấy nội dung comment hợp lệ.")
        tasks = self.distribute_urls(account_indexes, urls, settings["limit_per_account"])
        for acc_idx, acc_urls in tasks.items():
            control.wait_if_paused()
            if acc_idx >= len(accounts):
                continue
            account = accounts[acc_idx]
            name = account.get("name", "Unknown")
            browser = None
            self.ui_log(f"[{name}] Được phân công {len(acc_urls)} link.")
            try:
                with sync_playwright() as p:
                    browser, context, page = self.browser_service.launch_page(p, account)
                    self.browser_service.ensure_login(context, page, account)
                    for url in acc_urls:
                        control.wait_if_paused()
                        content = spin_text(random.choice(lines))
                        self.log_service.event("comment", "running", account=name, url=url)
                        page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(random.uniform(3, 6))
                        page.mouse.wheel(0, 500)
                        time.sleep(1)
                        try:
                            box = page.locator(
                                'div[role="textbox"][contenteditable="true"][aria-label="Viết bình luận..."], '
                                'div[role="textbox"][contenteditable="true"][data-lexical-editor="true"]'
                            ).last
                            box.scroll_into_view_if_needed()
                            box.wait_for(state="visible", timeout=10000)
                            box.click()
                            page.keyboard.type(content, delay=random.uniform(40, 100))
                            time.sleep(random.uniform(1, 2))
                            if settings.get("image_path"):
                                self.ui_log(f"[{name}] Có file đính kèm được cấu hình; vui lòng kiểm tra thủ công nếu giao diện không hỗ trợ upload.")
                            page.keyboard.press("Enter")
                            self.log_service.event("comment", "done", account=name, url=url)
                            self.ui_log(f"[{name}] Hoàn tất thao tác trên link.")
                        except Exception as e:
                            self.log_service.event("comment", "error", account=name, url=url, error=str(e))
                            self.ui_log(f"[{name}] Lỗi khi thao tác comment: {e}")
                        delay = random.uniform(*settings["delay_range"])
                        self.ui_log(f"[{name}] Nghỉ {int(delay)} giây.")
                        # Sleep có kiểm tra stop/pause từng giây.
                        end = time.time() + delay
                        while time.time() < end:
                            control.wait_if_paused()
                            time.sleep(min(1, end - time.time()))
            except InterruptedError:
                self.log_service.event("comment", "stopped", account=name)
                raise
            except Exception as e:
                self.log_service.event("comment", "error", account=name, error=str(e))
                self.ui_log(f"[{name}] Lỗi profile: {e}")
            finally:
                if browser:
                    browser.close()
