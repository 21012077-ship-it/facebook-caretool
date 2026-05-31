# Facebook Care Tool - Refactor

## Những phần đã thêm

- Mã hóa `accounts.json` thành `data/accounts.enc.json` bằng Fernet.
- Tự migrate từ `accounts.json` cũ sang file mã hóa, đồng thời tạo `accounts.json.bak`.
- Pause / Resume / Stop thật cho task bằng `TaskControl`.
- Tách module: `services`, `utils`, `ui`, `config.py`.
- Dùng `limit comment / tài khoản` khi phân bổ URL.
- Validation cho proxy, URL Facebook, delay, cookie JSON, 2FA secret.
- Màn `Lịch sử nuôi / thao tác` đọc từ `data/logs.jsonl`.
- Màn `Cookie/Profile`: kiểm tra cookie, import, export, xóa cookie.
- Backup/Import toàn bộ tài khoản vào một file `.fbcarebackup`, bao gồm thông tin đăng nhập, proxy và nội dung file cookie để chuyển sang máy khác.
- Logging tốt hơn vào `logs/app.log` và `data/logs.jsonl`.

## Cài đặt

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Lưu ý bảo mật

- File `data/.app_key` là khóa giải mã. Nếu mất file này thì không mở được `data/accounts.enc.json`.
- Không commit `data/`, `cookies/`, `logs/` lên Git.
- File `.fbcarebackup` chứa dữ liệu nhạy cảm (UID, mật khẩu, 2FA, proxy, cookie). Chỉ lưu/chia sẻ file này ở nơi an toàn.
- File cũ `accounts.json` sẽ được backup thành `accounts.json.bak` sau khi migrate.

## Về phần stealth / né phát hiện

Bản refactor này không bao gồm code stealth/né phát hiện. File gốc của bạn không bị chỉnh sửa; phần refactor tập trung vào bảo mật dữ liệu, quản lý task, logging, validation, lịch sử và cookie/profile.
"# facebook-caretool" 
