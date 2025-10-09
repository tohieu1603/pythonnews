# Auto Trading / Auto-Renew Guide

Tài liệu này mô tả chi tiết cách bật “tự động giao dịch” cho quyền truy cập symbol. Chức năng thực chất là auto-renew: hệ thống tự tạo đơn hàng và trừ ví khi license sắp hết hạn.

## 1. Tổng quan kiến trúc
- Người dùng mua symbol qua API `/api/sepay/symbol/orders/`. Mỗi item có thể bật `auto_renew`.
- Khi order được thanh toán, service `SymbolAutoRenewService` (apps/setting) tạo bản ghi `SymbolAutoRenewSubscription` liên kết với license (`PayUserSymbolLicense`).
- Scheduler định kỳ gọi `SymbolAutoRenewService.run_due_subscriptions()` để kiểm tra `next_billing_at`. Nếu đến hạn:
  - Trừ tiền ví (`PayWallet`), tạo order mới, gia hạn license.
  - Log kết quả vào `SymbolAutoRenewAttempt`.
  - Nếu ví thiếu tiền, subscription bị hủy (status `cancelled`) hoặc chuyển `suspended`.
- Người dùng quản lý subscription qua router `/api/settings/symbol/...`.

> Hiện tại auto-renew chỉ hỗ trợ trừ tiền từ ví (`payment_method="wallet"`). Nếu thiếu tiền, hệ thống dừng subscription và yêu cầu user nạp ví/đăng ký lại.

## 2. Chuẩn bị
1. **User & JWT**: Đăng nhập để lấy access token (`Authorization: Bearer <token>`).
2. **Nạp ví** (nếu cần):
   - `POST /api/sepay/wallet/topup/`
   - Body:
     ```json
     {
       "amount": "200000",
       "currency": "VND",
       "bank_code": "BIDV"
     }
     ```
   - Hệ thống trả về QR/ thông tin chuyển khoản để nạp tiền vào ví nội bộ.

3. **Kiểm tra ví**:
   - `GET /api/sepay/wallet/`
   - Đảm bảo `balance` đủ cho kỳ gia hạn đầu tiên.

## 3. Bật tự động giao dịch khi mua symbol

### Endpoint tạo order
- **POST** `/api/sepay/symbol/orders/`
- **Body** (`CreateSymbolOrderRequest`):
  ```json
  {
    "payment_method": "wallet",
    "items": [
      {
        "symbol_id": 1001,
        "price": "150000",
        "license_days": 30,
        "auto_renew": true,
        "auto_renew_price": "135000",
        "auto_renew_cycle_days": 30,
        "metadata": {
          "note": "Theo dõi khung ngày"
        }
      }
    ],
    "description": "Mua gói 30 ngày + auto renew"
  }
  ```
  - `auto_renew`: bắt buộc đặt `true` để bật auto trading.
  - `auto_renew_price`: giá sẽ trừ cho các lần gia hạn. Nếu bỏ trống, dùng `price`.
  - `auto_renew_cycle_days`: số ngày giữa các lần gia hạn (mặc định theo `license_days` hoặc 30).
  - `payment_method`: nên để `wallet` vì auto-renew chỉ xử lý ví.

- **Response** (`CreateSymbolOrderResponse`):
  ```json
  {
    "order_id": "a7f9d6c0-6c6e-4bf3-9f1a-10d598c7a8da",
    "total_amount": "150000.00",
    "status": "paid",
    "payment_method": "wallet",
    "items": [
      {
        "symbol_id": 1001,
        "price": "150000.00",
        "license_days": 30,
        "auto_renew": true,
        "auto_renew_price": "135000.00",
        "auto_renew_cycle_days": 30,
        "metadata": {
          "note": "Theo dõi khung ngày"
        }
      }
    ],
    "created_at": "2024-05-16T09:30:12Z",
    "message": "Order processed successfully.",
    "insufficient_balance": false
  }
  ```
  - Nếu ví không đủ tiền: `insufficient_balance=true`. User cần nạp ví và thanh toán qua `/api/sepay/symbol/orders/{order_id}/pay-sepay` hoặc `/pay-wallet`.

### Kết quả phía sau
- License (`PayUserSymbolLicense`) được tạo/ cập nhật `end_at`.
- Subscription (`SymbolAutoRenewSubscription`):
  - `status`: `active`
  - `price`: `auto_renew_price` hoặc `price`
  - `cycle_days`: `auto_renew_cycle_days` hoặc `license_days`
  - `next_billing_at`: `license.end_at - grace_period_hours`

## 4. Quản lý subscription (API `/api/settings/...`)

| Method | Path | Mô tả | Body |
| ------ | ---- | ----- | ---- |
| `POST` | `/api/settings/symbol/subscriptions/enable` | Bật/khởi tạo auto-renew cho một symbol | `EnableAutoRenewRequest` |
| `GET` | `/api/settings/symbol/subscriptions` | List tất cả auto-renew | - |
| `POST` | `/api/settings/symbol/subscriptions/{subscription_id}/pause` | Tạm dừng trừ tiền | - |
| `POST` | `/api/settings/symbol/subscriptions/{subscription_id}/resume` | Mở lại auto-renew (chỉ khi ví đủ tiền) | - |
| `POST` | `/api/settings/symbol/subscriptions/{subscription_id}/cancel` | Hủy hoàn toàn (không tự động gia hạn nữa) | - |
| `GET` | `/api/settings/symbol/subscriptions/{subscription_id}/attempts?limit=20` | Xem lịch sử chạy auto-renew | - |

### Bật auto-renew qua API riêng
- **POST** `/api/settings/symbol/subscriptions/enable`
- **Body** (`EnableAutoRenewRequest`):
  ```json
  {
    "symbol_id": 1001,
    "price": "135000",
    "cycle_days": 30,
    "payment_method": "wallet",
    "grace_period_hours": 12,
    "retry_interval_minutes": 60,
    "max_retry_attempts": 3
  }
  ```
  - `symbol_id` (bắt buộc): symbol đã mua và còn license active.
  - `price` (tùy chọn): nếu bỏ trống, hệ thống lấy `auto_renew_price`/`price` từ order gần nhất.
  - `cycle_days` (tùy chọn): chu kỳ gia hạn; mặc định ưu tiên `auto_renew_cycle_days` rồi `license_days`, cuối cùng là 30.
  - `payment_method`: hiện chỉ hỗ trợ `"wallet"`.
  - `grace_period_hours`: số giờ trước `end_at` sẽ trigger auto-renew (mặc định 12).
  - `retry_interval_minutes`, `max_retry_attempts`: cấu hình retry khi ví thiếu tiền/lỗi khác (mặc định 60 phút, 3 lần).
- **Response**: `SymbolAutoRenewSubscriptionResponse` như các endpoint khác (trả về subscription đã bật).
- Điều kiện:
  - User phải có license `ACTIVE` (không lifetime) cho `symbol_id`.
  - Ví phải tồn tại; số dư chỉ được kiểm tra lúc chạy batch.

### Response mẫu (GET list)
```json
[
  {
    "subscription_id": "0ab5fb7a-3ca7-4c89-9bd2-8d94fae3cb9e",
    "symbol_id": 1001,
    "status": "active",
    "cycle_days": 30,
    "price": "135000.00",
    "payment_method": "wallet",
    "next_billing_at": "2024-06-14T09:30:00Z",
    "last_success_at": "2024-05-15T09:30:12Z",
    "last_attempt_at": null,
    "consecutive_failures": 0,
    "grace_period_hours": 12,
    "retry_interval_minutes": 60,
    "max_retry_attempts": 3,
    "current_license_id": "64d1b7ff-1c4e-435b-8afe-c5bffb7088b5",
    "last_order_id": "a7f9d6c0-6c6e-4bf3-9f1a-10d598c7a8da",
    "created_at": "2024-05-15T09:30:12Z",
    "updated_at": "2024-05-15T09:30:12Z"
  }
]
```

### Attempt history
```json
[
  {
    "attempt_id": "91db04ae-4a99-46d1-87f1-59adf83fb19a",
    "subscription_id": "0ab5fb7a-3ca7-4c89-9bd2-8d94fae3cb9e",
    "status": "success",
    "charged_amount": "135000.00",
    "wallet_balance_snapshot": "940000.00",
    "order_id": "79ae18ca-12cb-4512-bf4b-4d1d58d8cb3b",
    "fail_reason": null,
    "ran_at": "2024-06-14T09:30:02Z"
  }
]
```
- Nếu ví không đủ tiền, `status="failed"` + `fail_reason="Insufficient balance..."`. Subscription chuyển `cancelled` ngay lập tức.
- Nếu lỗi khác (ví dụ tạo order thất bại), hệ thống sẽ retry sau `retry_interval_minutes` cho tới khi đạt `max_retry_attempts`. Quá số lần -> `status="suspended"` và cần user resume.

## 5. Scheduler / batch chạy auto-renew
Hệ thống chưa có management command sẵn; bạn cần tự lên lịch gọi service:

### Ví dụ chạy bằng `python manage.py shell`
```bash
python manage.py shell -c "from apps.setting.services.subscription_service import SymbolAutoRenewService; print(SymbolAutoRenewService().run_due_subscriptions(limit=50))"
```

### Gợi ý cron (mỗi 15 phút)
```
*/15 * * * * /path/to/venv/bin/python /path/to/manage.py shell -c "from apps.setting.services.subscription_service import SymbolAutoRenewService; SymbolAutoRenewService().run_due_subscriptions(limit=100)"
```

### Celery/Celery Beat (pseudo-code)
```python
@app.task
def run_auto_trading_batch(limit=100):
    from apps.setting.services.subscription_service import SymbolAutoRenewService
    service = SymbolAutoRenewService()
    summary = service.run_due_subscriptions(limit=limit)
    logger.info("Auto renew batch result: %s", summary)
```

Kết quả `run_due_subscriptions`:
```json
{
  "processed": 10,
  "success": 9,
  "failed": 1,
  "skipped": 0
}
```
- `skipped`: subscription có `payment_method` khác `wallet`.

## 6. Các API bổ trợ
- **Kiểm tra license hiện tại**: `GET /api/sepay/symbol/{symbol_id}/access`
  - Response nếu còn hạn:
    ```json
    {
      "has_access": true,
      "license_id": "64d1b7ff-1c4e-435b-8afe-c5bffb7088b5",
      "symbol_id": 1001,
      "start_at": "2024-05-15T09:30:12Z",
      "end_at": "2024-06-14T09:30:12Z",
      "is_lifetime": false,
      "expires_soon": false
    }
    ```
- **Lịch sử license**: `GET /api/sepay/symbol/licenses?page=1&limit=20`
- **Lịch sử đơn symbol**: `GET /api/sepay/symbol/orders/history?limit=20`

## 7. Data model & trạng thái
- `SymbolAutoRenewSubscription.status`:
  - `pending_activation`: đợi order thanh toán xong.
  - `active`: đang theo dõi và sẽ tự gia hạn.
  - `paused`: tạm dừng (không trừ tiền cho tới khi resume).
  - `suspended`: quá số lần retry thất bại; cần xử lý thủ công và resume.
  - `cancelled`: dừng hẳn, cần đăng ký lại bằng order mới.
  - `completed`: license trọn đời (không cần gia hạn).
- `SymbolAutoRenewAttempt.status`: `success | failed | skipped`.
- `next_billing_at` = thời điểm chạy auto-renew tiếp theo (đã trừ đi `grace_period_hours`). Nếu license trọn đời (`end_at=null`), subscription chuyển `completed`.

## 8. Quy trình test bằng Postman
1. Lấy token -> set header `Authorization`.
2. `POST /api/sepay/wallet/topup/` (nếu cần).
3. `POST /api/sepay/symbol/orders/` (set `auto_renew=true`).
4. `GET /api/settings/symbol/subscriptions` kiểm tra subscription.
5. Nếu muốn bật lại auto renew cho symbol đã mua nhưng chưa bật, gọi `POST /api/settings/symbol/subscriptions/enable`.
6. Giả lập đến hạn: chỉnh `next_billing_at` trong DB hoặc chờ đến hạn.
7. Chạy script `run_due_subscriptions`. Kiểm tra:
   - Ví bị trừ (`GET /api/sepay/wallet/`).
   - License gia hạn (`GET /api/sepay/symbol/{symbol_id}/access`).
   - Attempt log (`GET /api/settings/symbol/subscriptions/{subscription_id}/attempts`).

## 9. Lưu ý vận hành
- Nhớ bật mail/notification để báo user khi auto-renew fail (hiện chưa có, nên tích hợp thêm webhook/notification service).
- Khi thay đổi giá bán hoặc chu kỳ, order mới với `auto_renew` sẽ cập nhật subscription (`price`, `cycle_days`).
- Nếu muốn tạm thời ngừng auto trading (ví dụ thị trường biến động), gọi API `pause`; khi resume hệ thống kiểm tra ví đủ tiền trước khi đặt lại `active`.
- Theo dõi log dưới logger `app.autorenew` để nắm kết quả từng batch.

---

Với hướng dẫn này, bạn có thể bật/tắt tự động giao dịch (auto-renew) cho từng symbol, nắm được toàn bộ endpoints liên quan và biết cách vận hành scheduler đảm bảo license được gia hạn đúng hạn. Chúc bạn triển khai thành công!
