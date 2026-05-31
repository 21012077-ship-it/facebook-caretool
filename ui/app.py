import threading
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

from services.secure_store import SecureAccountStore
from services.log_service import LogService
from services.task_control import TaskControl
from services.cookie_service import CookieService
from services.backup_service import BackupService
from services.browser_service import BrowserService
from services.comment_service import CommentCampaignService
from utils.validators import (
    ValidationError, validate_proxy, validate_cookie_file, validate_2fa_secret,
    validate_delay_range, validate_positive_int, validate_facebook_url,
)
from utils.spin import spin_text

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class FacebookCareTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Facebook Account Care Tool - Refactor")
        self.geometry("1320x780")
        self.minsize(1200, 720)

        self.store = SecureAccountStore()
        self.logs = LogService()
        self.cookies = CookieService()
        self.backups = BackupService()
        self.control = TaskControl()
        self.browser_service = BrowserService(self.logs, ui_log=lambda m: self.after(0, lambda: self.append_live_log(m)))
        self.comment_service = CommentCampaignService(self.browser_service, self.logs, ui_log=lambda m: self.after(0, lambda: self.append_live_log(m)))

        self.accounts = self.store.load()
        self.selected_index = None
        self.selected_accounts = set()
        self.comment_selected_accounts = set()
        self.comment_image_path = ""
        self.log_lines = []
        self.task_threads = []

        self.build_ui()
        self.refresh_accounts()
        self.refresh_history()

    def save_accounts(self):
        self.store.save(self.accounts)

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="Account Care", font=("Arial", 22, "bold")).pack(pady=(25, 20))
        self.menu_buttons = {}
        for key, text in [("care", "Nuôi tài khoản"), ("comment", "Cấu hình Comment"), ("history", "Lịch sử nuôi"), ("cookies", "Cookie/Profile")]:
            self.menu_buttons[key] = self.create_menu_btn(text, lambda k=key: self.switch_view(k))
        self.stat_label = ctk.CTkLabel(self.sidebar, text="Tổng tài khoản: 0", anchor="w")
        self.stat_label.pack(side="bottom", fill="x", padx=20, pady=20)

        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.view_care = ctk.CTkFrame(self.main_container, fg_color="#0f172a")
        self.view_comment = ctk.CTkFrame(self.main_container, fg_color="#0f172a")
        self.view_history = ctk.CTkFrame(self.main_container, fg_color="#0f172a")
        self.view_cookies = ctk.CTkFrame(self.main_container, fg_color="#0f172a")
        self.build_view_care()
        self.build_view_comment()
        self.build_view_history()
        self.build_view_cookies()
        self.switch_view("care")

    def create_menu_btn(self, text, command):
        btn = ctk.CTkButton(self.sidebar, text=text, height=42, anchor="w", fg_color="transparent", hover_color="#1d4ed8", command=command)
        btn.pack(fill="x", padx=15, pady=5)
        return btn

    def switch_view(self, view_name):
        for frame in [self.view_care, self.view_comment, self.view_history, self.view_cookies]:
            frame.grid_forget()
        for key, btn in self.menu_buttons.items():
            btn.configure(fg_color="#2563eb" if key == view_name else "transparent")
        if view_name == "comment":
            self.refresh_comment_accounts()
        if view_name == "history":
            self.refresh_history()
        if view_name == "cookies":
            self.refresh_cookie_accounts()
        getattr(self, f"view_{view_name}").grid(row=0, column=0, sticky="nsew")

    def build_view_care(self):
        self.view_care.grid_columnconfigure(0, weight=1)
        self.view_care.grid_columnconfigure(1, weight=0)
        self.view_care.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self.view_care, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=25, pady=(25, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Nuôi tài khoản Facebook", font=("Arial", 28, "bold")).grid(row=0, column=0, sticky="w")
        self.search_entry = ctk.CTkEntry(header, width=260, height=40, placeholder_text="Tìm kiếm...")
        self.search_entry.grid(row=0, column=1, padx=8)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_accounts())
        ctk.CTkButton(header, text="Backup", height=40, fg_color="#0d9488", command=self.export_backup).grid(row=0, column=2, padx=4)
        ctk.CTkButton(header, text="Import", height=40, fg_color="#7c3aed", command=self.import_backup).grid(row=0, column=3, padx=4)
        ctk.CTkButton(header, text="+ Thêm", height=40, command=self.add_account_popup).grid(row=0, column=4, padx=(4, 0))

        controls = ctk.CTkFrame(self.view_care, fg_color="transparent")
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=25, pady=5)
        self.filter_var = ctk.StringVar(value="all")
        for text, value in [("Tất cả", "all"), ("Live", "active"), ("Checkpoint", "checkpoint"), ("Die", "cookie_error")]:
            ctk.CTkRadioButton(controls, text=text, variable=self.filter_var, value=value, command=self.refresh_accounts).pack(side="left", padx=8)
        ctk.CTkButton(controls, text="Chọn tất cả đang lọc", fg_color="#374151", command=self.select_all_filtered_accounts).pack(side="left", padx=12)
        ctk.CTkButton(controls, text="Bỏ chọn", fg_color="#374151", command=self.clear_selected_accounts).pack(side="left", padx=4)
        ctk.CTkButton(controls, text="▶ Chạy", fg_color="#16a34a", command=self.start_care_selected_accounts).pack(side="right", padx=4)
        ctk.CTkButton(controls, text="⏸ Pause", fg_color="#475569", command=self.pause_tasks).pack(side="right", padx=4)
        ctk.CTkButton(controls, text="▶ Resume", fg_color="#0d9488", command=self.resume_tasks).pack(side="right", padx=4)
        ctk.CTkButton(controls, text="■ Stop", fg_color="#991b1b", command=self.stop_tasks).pack(side="right", padx=4)

        settings = ctk.CTkFrame(self.view_care, fg_color="#111827", corner_radius=12)
        settings.grid(row=2, column=0, columnspan=2, sticky="ew", padx=25, pady=8)
        self.newsfeed_minutes_var = ctk.StringVar(value="5")
        self.reels_minutes_var = ctk.StringVar(value="5")
        self.pause_seconds_var = ctk.StringVar(value="4-9")
        for label, var, values in [("Newsfeed phút", self.newsfeed_minutes_var, ["0","1","3","5","10","15","20","30"]), ("Reels phút", self.reels_minutes_var, ["0","1","3","5","10","15","20","30"]), ("Nghỉ cuộn", self.pause_seconds_var, ["2-5","4-9","6-12","10-20"] )]:
            ctk.CTkLabel(settings, text=label).pack(side="left", padx=(15, 5), pady=10)
            ctk.CTkOptionMenu(settings, width=100, values=values, variable=var).pack(side="left", padx=5, pady=10)

        self.account_container = ctk.CTkScrollableFrame(self.view_care, fg_color="#111827", corner_radius=12)
        self.account_container.grid(row=3, column=0, sticky="nsew", padx=(25, 8), pady=8)
        self.detail = ctk.CTkFrame(self.view_care, width=330, corner_radius=0)
        self.detail.grid(row=3, column=1, sticky="nsew")
        self.detail.grid_propagate(False)
        ctk.CTkLabel(self.detail, text="Thông tin", font=("Arial", 20, "bold")).pack(pady=(18,8), padx=18, anchor="w")
        self.detail_name = ctk.CTkLabel(self.detail, text="Chưa chọn", font=("Arial", 17, "bold"))
        self.detail_name.pack(fill="x", padx=18, pady=6)
        self.detail_info = ctk.CTkLabel(self.detail, text="", justify="left", anchor="w")
        self.detail_info.pack(fill="x", padx=18, pady=8)
        ctk.CTkButton(self.detail, text="▶ Nuôi acc đang xem", command=self.start_care_selected_account).pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(self.detail, text="🌐 Mở Facebook", command=self.open_selected_account).pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(self.detail, text="✎ Sửa", fg_color="#374151", command=self.edit_selected_account).pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(self.detail, text="🗑 Xóa", fg_color="#991b1b", command=self.delete_selected_account).pack(fill="x", padx=18, pady=6)

        self.live_log_text = ctk.CTkTextbox(self.view_care, height=110, fg_color="#020617")
        self.live_log_text.grid(row=4, column=0, columnspan=2, sticky="ew", padx=25, pady=(4,15))
        self.live_log_text.insert("end", "Sẵn sàng.\n")
        self.live_log_text.configure(state="disabled")

    def build_view_comment(self):
        self.view_comment.grid_columnconfigure(0, weight=2)
        self.view_comment.grid_columnconfigure(1, weight=1)
        self.view_comment.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.view_comment, text="Cấu hình Comment", font=("Arial", 26, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=20)
        left = ctk.CTkFrame(self.view_comment, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(25,10), pady=(0,20))
        left.grid_rowconfigure(1, weight=1); left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="URL bài viết, mỗi dòng 1 link").grid(row=0, column=0, sticky="w")
        self.url_input = ctk.CTkTextbox(left, height=150)
        self.url_input.grid(row=1, column=0, sticky="nsew", pady=5)
        ctk.CTkLabel(left, text="Nội dung comment / spin").grid(row=2, column=0, sticky="w", pady=(10,0))
        self.comment_content = ctk.CTkTextbox(left, height=170)
        self.comment_content.grid(row=3, column=0, sticky="ew", pady=5)
        self.comment_content.insert("1.0", "{Chào|Hi|Hello} bạn nhé. Chúc một ngày {tốt lành|vui vẻ}!")
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.grid(row=4, column=0, sticky="ew")
        ctk.CTkButton(row, text="📷 Chọn file", fg_color="#475569", command=self.choose_comment_image).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Xem spin", fg_color="#0d9488", command=self.preview_spin_content).pack(side="left", padx=4)
        self.spin_preview_label = ctk.CTkLabel(left, text="", wraplength=600, text_color="#fcd34d")
        self.spin_preview_label.grid(row=5, column=0, sticky="w", pady=6)

        right = ctk.CTkFrame(self.view_comment, width=360)
        right.grid(row=1, column=1, sticky="nsew", padx=(10,25), pady=(0,20))
        right.grid_propagate(False)
        ctk.CTkLabel(right, text="Tài khoản chạy", font=("Arial", 18, "bold")).pack(anchor="w", padx=18, pady=(18,6))
        self.cmt_acc_scroll = ctk.CTkScrollableFrame(right, height=220, fg_color="#0f172a")
        self.cmt_acc_scroll.pack(fill="both", expand=True, padx=18, pady=6)
        self.delay_cmt_input = self.setting_entry(right, "Nghỉ giữa mỗi comment", "60-120")
        self.limit_cmt_input = self.setting_entry(right, "Giới hạn comment / tài khoản", "5")
        ctk.CTkButton(right, text="▶ Bắt đầu", height=44, fg_color="#16a34a", command=self.start_comment_campaign).pack(fill="x", padx=18, pady=(16,5))
        ctk.CTkButton(right, text="⏸ Pause", fg_color="#475569", command=self.pause_tasks).pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(right, text="▶ Resume", fg_color="#0d9488", command=self.resume_tasks).pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(right, text="■ Stop", fg_color="#991b1b", command=self.stop_tasks).pack(fill="x", padx=18, pady=4)

    def setting_entry(self, parent, label, default):
        ctk.CTkLabel(parent, text=label).pack(anchor="w", padx=18, pady=(8,0))
        e = ctk.CTkEntry(parent)
        e.pack(fill="x", padx=18, pady=(3,6))
        e.insert(0, default)
        return e

    def build_view_history(self):
        self.view_history.grid_columnconfigure(0, weight=1)
        self.view_history.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self.view_history, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=25, pady=20)
        ctk.CTkLabel(top, text="Lịch sử nuôi / thao tác", font=("Arial", 26, "bold")).pack(side="left")
        ctk.CTkButton(top, text="Refresh", command=self.refresh_history).pack(side="right", padx=5)
        ctk.CTkButton(top, text="Xóa lịch sử", fg_color="#991b1b", command=self.clear_history).pack(side="right", padx=5)
        self.history_box = ctk.CTkTextbox(self.view_history, fg_color="#020617")
        self.history_box.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0,25))

    def build_view_cookies(self):
        self.view_cookies.grid_columnconfigure(0, weight=1)
        self.view_cookies.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.view_cookies, text="Quản lý Cookie/Profile", font=("Arial", 26, "bold")).grid(row=0, column=0, sticky="w", padx=25, pady=20)
        self.cookie_scroll = ctk.CTkScrollableFrame(self.view_cookies, fg_color="#111827")
        self.cookie_scroll.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0,25))

    def get_filtered_accounts(self):
        keyword = self.search_entry.get().lower() if hasattr(self, "search_entry") else ""
        status_filter = self.filter_var.get() if hasattr(self, "filter_var") else "all"
        out = []
        for i, acc in enumerate(self.accounts):
            hay = " ".join([acc.get("name", ""), acc.get("note", ""), acc.get("proxy", "")]).lower()
            if keyword and keyword not in hay:
                continue
            if status_filter != "all" and acc.get("status", "active") != status_filter:
                continue
            out.append((i, acc))
        return out

    def refresh_accounts(self):
        for w in self.account_container.winfo_children(): w.destroy()
        self.stat_label.configure(text=f"Tổng tài khoản: {len(self.accounts)}")
        for i, acc in self.get_filtered_accounts():
            row = ctk.CTkFrame(self.account_container, fg_color="#263244" if i == self.selected_index else "#1f2937", corner_radius=10)
            row.pack(fill="x", padx=4, pady=4)
            checked = ctk.BooleanVar(value=i in self.selected_accounts)
            ctk.CTkCheckBox(row, text="", width=28, variable=checked, command=lambda idx=i, v=checked: self.toggle_account_selection(idx, v.get())).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=acc.get("name", "Không tên"), font=("Arial", 14, "bold"), width=160, anchor="w").pack(side="left", padx=8, pady=10)
            ctk.CTkLabel(row, text=acc.get("status", "active"), width=100).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=acc.get("last_care", "Chưa nuôi"), width=150).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=acc.get("note", ""), anchor="w").pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkButton(row, text="Chi tiết", width=80, command=lambda idx=i: self.select_account(idx)).pack(side="right", padx=6)

    def select_account(self, index):
        self.selected_index = index
        acc = self.accounts[index]
        self.detail_name.configure(text=acc.get("name", "Không tên"))
        self.detail_info.configure(text=(
            f"Trạng thái: {acc.get('status','active')}\n\n"
            f"Cookie: {Path(acc.get('cookie_file','')).name if acc.get('cookie_file') else 'Chưa có'}\n\n"
            f"Proxy: {'Có' if acc.get('proxy') else 'Không dùng'}\n\n"
            f"Ghi chú: {acc.get('note','')}\n\n"
            f"Ngày thêm: {acc.get('created_at','')}\n"
            f"Lần mở cuối: {acc.get('last_open','Chưa mở')}\n"
            f"Lần nuôi cuối: {acc.get('last_care','Chưa nuôi')}"
        ))
        self.refresh_accounts()


    def export_backup(self):
        if not self.accounts:
            return messagebox.showwarning("Backup", "Chưa có tài khoản nào để backup.")
        if not messagebox.askyesno(
            "Backup dữ liệu",
            "File backup sẽ chứa UID, mật khẩu, 2FA, proxy và cookie. Hãy lưu file ở nơi an toàn. Tiếp tục?",
        ):
            return
        default_name = f"facebook-caretool-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.fbcarebackup"
        path = filedialog.asksaveasfilename(
            title="Lưu file backup",
            defaultextension=".fbcarebackup",
            initialfile=default_name,
            filetypes=[("Facebook Care backup", "*.fbcarebackup"), ("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            result = self.backups.export_backup(self.accounts, path)
            self.append_live_log(f"Đã backup {result['accounts']} tài khoản vào {Path(result['path']).name}.")
            messagebox.showinfo("Backup", f"Đã backup {result['accounts']} tài khoản vào:\n{result['path']}")
        except Exception as e:
            messagebox.showerror("Lỗi backup", str(e))

    def import_backup(self):
        path = filedialog.askopenfilename(
            title="Chọn file backup",
            filetypes=[("Facebook Care backup", "*.fbcarebackup"), ("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Import backup",
            "Import sẽ thêm tài khoản mới và cập nhật tài khoản trùng UID/tên từ file backup. Tiếp tục?",
        ):
            return
        try:
            result = self.backups.import_backup(path, self.accounts)
            self.accounts = result["accounts"]
            self.selected_index = None
            self.selected_accounts.clear()
            self.comment_selected_accounts.clear()
            self.save_accounts()
            self.refresh_accounts()
            self.refresh_comment_accounts()
            self.refresh_cookie_accounts()
            self.append_live_log(
                f"Đã import backup: thêm {result['added']}, cập nhật {result['updated']}, khôi phục {result['restored_cookies']} cookie."
            )
            messagebox.showinfo(
                "Import backup",
                f"Hoàn tất import.\nThêm mới: {result['added']}\nCập nhật: {result['updated']}\nCookie khôi phục: {result['restored_cookies']}",
            )
        except Exception as e:
            messagebox.showerror("Lỗi import", str(e))

    def add_account_popup(self, edit_index=None):
        popup = ctk.CTkToplevel(self); popup.title("Thêm/Sửa tài khoản"); popup.geometry("500x600"); popup.grab_set()
        current = self.accounts[edit_index] if edit_index is not None else {}
        entries = {}
        for key, label, placeholder in [
            ("raw", "Dữ liệu UID|Pass|2FA hoặc Tên", "1000...|pass|SECRET"),
            ("note", "Ghi chú", ""), ("proxy", "Proxy", "host:port hoặc host:port:user:pass"), ("cookie_file", "Cookie file", "")]:
            ctk.CTkLabel(popup, text=label).pack(pady=(12,3))
            e = ctk.CTkEntry(popup, width=390, placeholder_text=placeholder)
            e.pack(); entries[key] = e
        entries["raw"].insert(0, current.get("name", ""))
        entries["note"].insert(0, current.get("note", ""))
        entries["proxy"].insert(0, current.get("proxy", ""))
        entries["cookie_file"].insert(0, current.get("cookie_file", ""))
        status_var = ctk.StringVar(value=current.get("status", "active"))
        ctk.CTkOptionMenu(popup, width=390, variable=status_var, values=["active", "checkpoint", "cookie_error"]).pack(pady=12)
        def choose_cookie():
            path = filedialog.askopenfilename(title="Chọn cookie JSON", filetypes=[("JSON", "*.json")])
            if path:
                entries["cookie_file"].delete(0, "end"); entries["cookie_file"].insert(0, path)
        ctk.CTkButton(popup, text="Chọn cookie", command=choose_cookie).pack(pady=6)
        def save():
            try:
                raw = entries["raw"].get().strip()
                if not raw: raise ValidationError("Tên/UID không được trống.")
                uid = password = two_fa = ""; name = raw
                if "|" in raw:
                    parts = [p.strip() for p in raw.split("|")]
                    uid = parts[0]; password = parts[1] if len(parts)>1 else ""; two_fa = parts[2] if len(parts)>2 else ""; name = uid
                proxy = entries["proxy"].get().strip(); validate_proxy(proxy)
                cookie_file = validate_cookie_file(entries["cookie_file"].get().strip()) if entries["cookie_file"].get().strip() else ""
                validate_2fa_secret(two_fa)
                if not cookie_file and uid: cookie_file = self.cookies.default_cookie_path(uid)
                account = {"name": name, "uid": uid, "password": password, "two_fa": two_fa, "status": status_var.get(), "note": entries["note"].get().strip(), "proxy": proxy, "cookie_file": cookie_file, "created_at": current.get("created_at", datetime.now().strftime("%d/%m/%Y %H:%M")), "last_open": current.get("last_open", "Chưa mở"), "last_care": current.get("last_care", "Chưa nuôi")}
                if edit_index is None: self.accounts.append(account)
                else: self.accounts[edit_index] = account
                self.save_accounts(); self.refresh_accounts(); popup.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi validation", str(e))
        ctk.CTkButton(popup, text="Lưu", height=40, command=save).pack(pady=18)

    def edit_selected_account(self):
        if self.selected_index is None: return messagebox.showwarning("Thông báo", "Hãy chọn tài khoản.")
        self.add_account_popup(self.selected_index)
    def delete_selected_account(self):
        if self.selected_index is None: return messagebox.showwarning("Thông báo", "Hãy chọn tài khoản.")
        if messagebox.askyesno("Xác nhận", "Xóa tài khoản này?"):
            del self.accounts[self.selected_index]; self.selected_index=None; self.save_accounts(); self.refresh_accounts()
    def toggle_account_selection(self, idx, checked):
        self.selected_accounts.add(idx) if checked else self.selected_accounts.discard(idx)
    def select_all_filtered_accounts(self):
        for idx,_ in self.get_filtered_accounts(): self.selected_accounts.add(idx)
        self.refresh_accounts()
    def clear_selected_accounts(self): self.selected_accounts.clear(); self.refresh_accounts()

    def _start_thread(self, target, *args):
        t = threading.Thread(target=target, args=args, daemon=True)
        self.task_threads.append(t); t.start()
    def pause_tasks(self): self.control.pause(); self.append_live_log("Đã pause task.")
    def resume_tasks(self): self.control.resume(); self.append_live_log("Đã resume task.")
    def stop_tasks(self): self.control.stop(); self.append_live_log("Đã gửi lệnh stop.")

    def start_care_selected_account(self):
        if self.selected_index is None: return messagebox.showwarning("Thông báo", "Hãy chọn tài khoản.")
        self._trigger_care([self.selected_index])
    def start_care_selected_accounts(self):
        if not self.selected_accounts: return messagebox.showwarning("Thông báo", "Hãy chọn ít nhất 1 tài khoản.")
        self._trigger_care(list(self.selected_accounts))
    def _trigger_care(self, indexes):
        try:
            pause_range = validate_delay_range(self.pause_seconds_var.get())
            settings = {"newsfeed_minutes": int(self.newsfeed_minutes_var.get()), "reels_minutes": int(self.reels_minutes_var.get()), "pause_range": pause_range}
            if settings["newsfeed_minutes"] <= 0 and settings["reels_minutes"] <= 0: raise ValidationError("Cần chọn Newsfeed hoặc Reels > 0.")
            self.control.reset()
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            for idx in indexes:
                self.accounts[idx]["last_care"] = now
                self._start_thread(self._care_worker, idx, settings)
            self.save_accounts(); self.refresh_accounts(); self.append_live_log(f"Đã đưa {len(indexes)} tài khoản vào hàng chờ.")
        except Exception as e: messagebox.showerror("Lỗi", str(e))
    def _care_worker(self, idx, settings):
        try:
            self.browser_service.care_account(self.accounts[idx], settings, self.control)
        except Exception as e:
            self.after(0, lambda: self.append_live_log(f"Lỗi task: {e}"))
        finally:
            self.save_accounts()

    def open_selected_account(self):
        if self.selected_index is None: return messagebox.showwarning("Thông báo", "Hãy chọn tài khoản.")
        self.control.reset(); acc = self.accounts[self.selected_index]; acc["last_open"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.save_accounts(); self.select_account(self.selected_index); self._start_thread(self.browser_service.open_facebook, acc, self.control)

    def refresh_comment_accounts(self):
        for w in self.cmt_acc_scroll.winfo_children(): w.destroy()
        for i, acc in enumerate(self.accounts):
            v = ctk.BooleanVar(value=i in self.comment_selected_accounts)
            ctk.CTkCheckBox(self.cmt_acc_scroll, text=f"{acc.get('name','Không tên')} ({acc.get('status','active')})", variable=v, command=lambda idx=i, var=v: self.toggle_cmt_acc(idx, var.get())).pack(anchor="w", pady=3)
    def toggle_cmt_acc(self, idx, checked): self.comment_selected_accounts.add(idx) if checked else self.comment_selected_accounts.discard(idx)
    def choose_comment_image(self):
        path = filedialog.askopenfilename(title="Chọn file", filetypes=[("Media", "*.png *.jpg *.jpeg *.gif *.mp4 *.avi"), ("All", "*.*")])
        if path: self.comment_image_path = path; self.append_live_log(f"Đã chọn file: {Path(path).name}")
    def preview_spin_content(self): self.spin_preview_label.configure(text="Mẫu: " + spin_text(self.comment_content.get("1.0", "end-1c")))
    def start_comment_campaign(self):
        try:
            if not self.comment_selected_accounts: raise ValidationError("Vui lòng chọn ít nhất 1 tài khoản.")
            urls = [validate_facebook_url(u.strip()) for u in self.url_input.get("1.0", "end").splitlines() if u.strip()]
            if not urls: raise ValidationError("Vui lòng nhập URL hợp lệ.")
            raw = self.comment_content.get("1.0", "end-1c").strip()
            if not raw: raise ValidationError("Nội dung comment không được trống.")
            settings = {"delay_range": validate_delay_range(self.delay_cmt_input.get()), "limit_per_account": validate_positive_int(self.limit_cmt_input.get(), "Giới hạn comment/account"), "image_path": self.comment_image_path}
            self.control.reset()
            self._start_thread(self._comment_worker, list(self.comment_selected_accounts), urls, raw, settings)
        except Exception as e: messagebox.showerror("Lỗi", str(e))
    def _comment_worker(self, indexes, urls, raw, settings):
        try: self.comment_service.run(self.accounts, indexes, urls, raw, settings, self.control)
        except Exception as e: self.after(0, lambda: self.append_live_log(f"Chiến dịch kết thúc/lỗi: {e}"))
        finally: self.save_accounts(); self.after(0, self.refresh_history)

    def refresh_history(self):
        if not hasattr(self, "history_box"): return
        self.history_box.configure(state="normal"); self.history_box.delete("1.0", "end")
        for item in reversed(self.logs.read_recent(300)):
            self.history_box.insert("end", f"[{item.get('time')}] {item.get('status')} | {item.get('action')} | {item.get('account')} | {item.get('url')} | {item.get('error')}\n")
        self.history_box.configure(state="disabled")
    def clear_history(self):
        if messagebox.askyesno("Xác nhận", "Xóa toàn bộ lịch sử?"):
            self.logs.clear(); self.refresh_history()

    def refresh_cookie_accounts(self):
        for w in self.cookie_scroll.winfo_children(): w.destroy()
        for i, acc in enumerate(self.accounts):
            row = ctk.CTkFrame(self.cookie_scroll, fg_color="#1f2937", corner_radius=10); row.pack(fill="x", pady=5, padx=5)
            ctk.CTkLabel(row, text=acc.get("name","Không tên"), width=180, anchor="w").pack(side="left", padx=10, pady=10)
            cookie_path = acc.get("cookie_file", "")
            ctk.CTkLabel(row, text=Path(cookie_path).name if cookie_path else "Chưa có cookie", width=180).pack(side="left", padx=8)
            ctk.CTkButton(row, text="Kiểm tra", width=80, command=lambda idx=i: self.check_cookie(idx)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="Import", width=80, command=lambda idx=i: self.import_cookie(idx)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="Export", width=80, command=lambda idx=i: self.export_cookie(idx)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="Xóa cookie", width=90, fg_color="#991b1b", command=lambda idx=i: self.delete_cookie(idx)).pack(side="right", padx=5)
    def check_cookie(self, idx):
        def worker():
            try:
                ok, url = self.browser_service.check_cookie(self.accounts[idx])
                self.accounts[idx]["status"] = "active" if ok else "cookie_error"
                self.save_accounts(); self.after(0, self.refresh_cookie_accounts); self.after(0, self.refresh_accounts)
                self.after(0, lambda: messagebox.showinfo("Cookie", f"{'Sống' if ok else 'Không hợp lệ'}\n{url}"))
            except Exception as e: self.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
        self._start_thread(worker)
    def import_cookie(self, idx):
        path = filedialog.askopenfilename(title="Import cookie JSON", filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            self.accounts[idx]["cookie_file"] = self.cookies.import_cookie(path, self.accounts[idx].get("uid") or self.accounts[idx].get("name"))
            self.save_accounts(); self.refresh_cookie_accounts(); self.refresh_accounts()
        except Exception as e: messagebox.showerror("Lỗi", str(e))
    def export_cookie(self, idx):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path: return
        try: self.cookies.export_cookie(self.accounts[idx].get("cookie_file", ""), path); messagebox.showinfo("OK", "Đã export cookie.")
        except Exception as e: messagebox.showerror("Lỗi", str(e))
    def delete_cookie(self, idx):
        if messagebox.askyesno("Xác nhận", "Xóa file cookie của tài khoản này?"):
            self.cookies.delete(self.accounts[idx].get("cookie_file", "")); self.accounts[idx]["cookie_file"]=""; self.accounts[idx]["status"]="cookie_error"; self.save_accounts(); self.refresh_cookie_accounts(); self.refresh_accounts()

    def append_live_log(self, message):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self.log_lines = (self.log_lines + [line])[-120:]
        if hasattr(self, "live_log_text"):
            self.live_log_text.configure(state="normal")
            self.live_log_text.delete("1.0", "end")
            self.live_log_text.insert("end", "\n".join(self.log_lines) + "\n")
            self.live_log_text.see("end")
            self.live_log_text.configure(state="disabled")
