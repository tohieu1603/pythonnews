# Notification Module Guide

Tài liệu này mô tả chi tiết luồng cài đặt và vận hành hệ thống thông báo (`apps/notification`). Đọc kỹ trước khi tích hợp để nắm được kiến trúc, dữ liệu, endpoints và các tác vụ hỗ trợ.

## 1. Tổng quan
- Module quản lý thông báo đa kênh (Telegram, Zalo OA, Email) cho nền tảng PyNews.
- Hỗ trợ nhiều loại sự kiện nghiệp vụ: tín hiệu chứng khoán (TradingView), thanh toán, đơn hàng, nhắc hết hạn license,...
- Sử dụng Django Ninja để mở các REST endpoints cho client, đồng thời cung cấp webhook công khai cho TradingView.
- Tách các lớp xử lý theo mô hình *router → schema → service → repository/model* để dễ mở rộng và test.

## 2. Kiến trúc & thành phần chính
- **Models** (`apps/notification/models.py`)
  - `UserEndpoint`: sổ địa chỉ notification của từng user.
  - `NotificationEvent`: hàng đợi sự kiện nghiệp vụ.
  - `NotificationDelivery`: nhật ký gửi theo từng endpoint/kênh.
  - `WebhookLog`: lưu toàn bộ request/response webhook (TradingView, custom).
- **Repositories** (`apps/notification/repositories/notification_repository.py`): gom toàn bộ thao tác DB (query/update).
- **Services**
  - `EndpointService`: CRUD và verify endpoint.
  - `NotificationService`: tạo và xử lý event → phát sinh deliveries.
  - `DeliveryService`: gửi thông báo, retry, gửi pending.
  - `notification_utils`: workflow đặc thù cho tín hiệu chứng khoán, truy xuất license.
- **Handlers** (`apps/notification/services/handlers.py`): adapter cụ thể cho Telegram/Zalo/Email, định dạng nội dung.
- **Routers** (`apps/notification/routers/*.py`): cung cấp API cho app và webhook.
- **Management commands** (`apps/notification/management/commands`): automation gửi/gỡ lỗi.

Sơ đồ luồng điển hình:
1. Sự kiện phát sinh (ví dụ TradingView webhook hoặc tác vụ nội bộ) tạo `NotificationEvent`.
2. `NotificationService.process_event` sinh `NotificationDelivery` cho tất cả `UserEndpoint` đã `verified=True`.
3. `DeliveryService` lấy từng delivery, gọi handler theo `channel` và cập nhật `DeliveryStatus`.
4. `WebhookLog` ghi nhận request/response khi đến từ webhook bên ngoài.

## 3. Mô hình dữ liệu
- **UserEndpoint**
  - Khóa chính `endpoint_id` (UUID), thuộc về `user`.
  - `channel`: `telegram` | `zalo` | `email`.
  - `address`: chat_id (Telegram), user_id (Zalo OA) hoặc email.
  - `details`: JSON bổ sung (VD: username, OA id).
  - `verification_code`: mã OTP 6 chữ số được gửi tới email (nếu channel là email).
  - `verification_expires_at`: thời gian hết hạn mã (mặc định 2 phút sau khi gửi).
  - `is_primary`: đánh dấu endpoint mặc định cho mỗi channel.
  - `verified`: chỉ những endpoint được xác thực mới nhận thông báo.
- **NotificationEvent**
  - Lưu sự kiện nghiệp vụ, liên kết `user`, `event_type` (tham khảo `AppEventType`).
  - `payload`: JSON lưu dữ liệu render nội dung.
  - `processed`: tránh xử lý trùng.
- **NotificationDelivery**
  - Một bản ghi cho mỗi endpoint/kênh.
  - Thông tin `status` (xem `DeliveryStatus`), `sent_at`, `response_raw`, `error_message`.
- **WebhookLog**
  - Ghi nhận `source`, `symbol`, payload gốc, `status_code`, `users_notified`, thông tin lỗi/response.

## 4. Các hằng số domain
- `NotificationChannel`: `telegram`, `zalo`, `email`.
- `AppEventType` hiện hỗ trợ:  
  `symbol_signal`, `payment_success`, `payment_failed`, `order_created`, `order_filled`, `subscription_expiring`.
- `DeliveryStatus`: `queued`, `sending`, `sent`, `failed`, `retrying`.
- `WebhookSource`: `tradingview`, `custom`.

## 5. Cấu hình & biến môi trường
Đặt trong `.env` hoặc settings tương ứng:
- `TELEGRAM_BOT_TOKEN`: token bot Telegram.
- `ZALO_OA_ACCESS_TOKEN`: access token Official Account Zalo.
- `DEFAULT_FROM_EMAIL`: email nguồn gửi.
- `JWT_SECRET`, `JWT_ALGORITHM`: decode token cho các endpoint yêu cầu auth.
- Các biến khác của dự án (DB, Redis...) tùy theo môi trường triển khai.

Bật logging Django để xem namespace `app` cho thông tin gửi/ retry.

## 6. Luồng TradingView webhook → gửi thông báo
1. TradingView POST JSON tới `POST /notifications/webhook/tradingview` (không cần auth).
2. Router xác thực schema (`TradingViewWebhookSchema`) và kiểm tra symbol trong DB (`apps.stock.models.Symbol`).
3. Lưu log tạm thời, đẩy metadata sang `https://backtest.togogo.vn/api/v10/BackTest/wh`.
4. Gọi `send_symbol_signal_to_subscribers`:
   - `get_users_with_active_license` lọc user có license ACTIVE trong `apps.seapay.models.PayUserSymbolLicense`.
   - Với mỗi user: gọi `send_symbol_signal_notification` → `NotificationService.create_and_process_event`.
   - Service tạo `NotificationEvent` + các `NotificationDelivery` (chỉ cho endpoints đã verified).
   - `DeliveryService.send_pending_deliveries` gửi ngay qua handler tương ứng.
5. Kết quả (count success/fail) ghi vào `WebhookLog`.

Nếu symbol không tồn tại: trả HTTP 404 và log thất bại.

## 7. API nội bộ (Auth: Bearer JWT hoặc cookie `access_token`)

### 7.1 Endpoint quản lý địa chỉ thông báo (`apps/notification/routers/endpoint_router.py`)
| Method | Path | Mô tả | Payload | Ghi chú |
| ------ | ---- | ----- | ------- | ------- |
| `GET` | `/notifications/endpoints` | Danh sách endpoints của user hiện tại | - | Trả `List[UserEndpointSchema]` |
| `POST` | `/notifications/endpoints` | Tạo endpoint mới | `UserEndpointCreateSchema` | Nếu `is_primary=True` sẽ unset cái cũ cùng channel |
| `GET` | `/notifications/endpoints/{endpoint_id}` | Lấy chi tiết 1 endpoint | - | 404 nếu không thuộc user |
| `PATCH` | `/notifications/endpoints/{endpoint_id}` | Cập nhật endpoint | `UserEndpointUpdateSchema` | Cho phép đổi `is_primary`, `verified`, `details` |
| `DELETE` | `/notifications/endpoints/{endpoint_id}` | Xóa endpoint | - | 204 khi thành công |
| `POST` | `/notifications/endpoints/{endpoint_id}/verify` | Xác thực endpoint | `VerifyEndpointSchema` | `auto_verify=True` dùng cho Telegram khi bot nhận `/start`; OTP logic còn TODO |

#### Chi tiết endpoints quản lý địa chỉ

**GET /notifications/endpoints**  
- Auth: bắt buộc header `Authorization: Bearer <access_token>` hoặc cookie `access_token`.  
- Query params: không có.  
- Response: mảng các object có cấu trúc:
  ```json
  {
    "endpoint_id": "0cf293e8-9176-4f4e-9937-6b062c4dba9e",
    "channel": "telegram",
    "address": "123456789",
    "details": {"username": "pynews-bot"},
    "is_primary": true,
    "verified": true,
    "created_at": "2024-05-16T03:07:20Z"
  }
  ```

**POST /notifications/endpoints**  
- Body (`UserEndpointCreateSchema`):  
  - `channel` *(string, bắt buộc)*: `telegram` \| `zalo` \| `email`.  
  - `address` *(string, bắt buộc)*: chat_id Telegram, user_id Zalo hoặc email.  
  - `details` *(object, tùy chọn)*: thông tin phụ, ví dụ `{ "note": "OA vip" }`.  
  - `is_primary` *(bool, mặc định false)*: đánh dấu endpoint mặc định của channel.  
- Response 201:
  ```json
  {
    "endpoint_id": "706e4398-1374-4e52-b005-f62aec0f2f1e",
    "channel": "telegram",
    "address": "123456789",
    "details": {"note": "OA vip"},
    "is_primary": true,
    "verified": false,
    "created_at": "2024-05-16T09:12:33Z"
  }
  ```
- Response 400 nếu trùng `channel + address` hoặc lỗi khác (trả `{ "error": "<message>" }`).
- **Lưu ý**: nếu `channel=email`, hệ thống tự động gửi mã xác thực 6 chữ số tới địa chỉ email; mã chỉ hiệu lực 2 phút. Endpoint giữ trạng thái `verified=false` cho tới khi xác thực thành công.

**GET /notifications/endpoints/{endpoint_id}**  
- Path param: `endpoint_id` (UUID).  
- Response 200: giống schema `UserEndpointSchema`.  
- Lỗi 404: `{ "detail": "Not Found" }`.

**PATCH /notifications/endpoints/{endpoint_id}**  
- Body (`UserEndpointUpdateSchema`): tất cả optional.  
  - `is_primary` *(bool)*: nếu true sẽ unset các endpoint khác cùng channel.  
  - `verified` *(bool)*: chỉ nên dùng bởi admin; người dùng không thể set `true` cho kênh email.  
  - `details` *(object)*: ghi đè thông tin phụ.  
- Response 200: endpoint đã cập nhật.  
- Response 400: `{ "error": "Endpoint not found" }` hoặc thông báo phù hợp.

**DELETE /notifications/endpoints/{endpoint_id}**  
- Response 204: không có body.  
- Response 404: `{ "error": "Endpoint not found" }`.

- **POST /notifications/endpoints/{endpoint_id}/verify**  
  - Body (`VerifyEndpointSchema`):  
    - `auto_verify` *(bool, mặc định false)*: set true khi bot Telegram đã nhận `/start`. Không áp dụng cho email.  
    - `verification_code` *(string, tùy chọn)*: dùng cho luồng OTP; **bắt buộc đối với email**.  
  - Response 200: endpoint đã `verified=true`. Với email, mã hợp lệ sẽ được xoá sau khi xác thực thành công.  
  - Response 400 (một số tình huống phổ biến):  
    - `{ "error": "verification_code is required" }` khi thiếu mã OTP và `auto_verify=false`.  
    - `{ "error": "Verification code has expired. Please request a new code." }` nếu quá 2 phút.  
    - `{ "error": "Email endpoint requires verification code" }` nếu cố gắng auto-verify cho email.  
    - `{ "error": "Invalid verification code" }` khi nhập sai mã.  
- Response 404: `{ "error": "Endpoint not found" }`.

**Lưu ý**: Service ngăn tạo trùng (`channel + address`), và tự động unset `is_primary` của channel khi cập nhật.

#### Luồng xác thực email chi tiết

1. **Tạo endpoint email**  
   - Client gọi `POST /notifications/endpoints` với `channel="email"` và `address` là email hợp lệ.  
   - Backend lưu endpoint với `verified=false`, sinh mã OTP 6 chữ số, set `verification_expires_at = now + 2 phút`.  
   - Email chứa mã OTP gửi tới địa chỉ vừa đăng ký. Tên người gửi dùng `DEFAULT_FROM_EMAIL`.  
   - Response trả về endpoint (như ví dụ bên trên) để phía client biết `endpoint_id`.

2. **Hướng dẫn người dùng nhập OTP**  
   - UI nên yêu cầu người dùng nhập mã 6 chữ số vừa nhận.  
   - Lưu ý: mã hết hạn sau 120 giây; nếu hết hạn cần tạo endpoint lại (hoặc gọi API resend khi được hỗ trợ).

3. **Xác thực mã OTP**  
   - Client gọi `POST /notifications/endpoints/{endpoint_id}/verify` với body:
     ```json
     {
       "auto_verify": false,
       "verification_code": "123456"
     }
     ```
   - Backend kiểm tra:
     - Endpoint tồn tại, thuộc user hiện tại và chưa verified.
     - Có mã (`verification_code`) và thời gian hết hạn (`verification_expires_at`) đã lưu.
     - `timezone.now()` chưa vượt quá `verification_expires_at`.
     - Mã khớp giá trị 6 chữ số đã cấp.
   - Nếu hợp lệ: set `verified=true`, xoá mã OTP và thời gian hết hạn rồi trả endpoint đã xác thực.  
   - Nếu sai mã hoặc quá hạn: trả 400 với thông báo cụ thể như trên.

4. **Sau xác thực**  
   - Endpoint email đủ điều kiện nhận notification khi các sự kiện được phát sinh.  
   - Dữ liệu OTP bị xoá để tránh tái sử dụng.  
   - Nếu người dùng muốn thay đổi email hoặc thêm email mới, cần lặp lại luồng xác thực.

> Hiện tại chưa có endpoint riêng để resend OTP; cách nhanh nhất là xóa endpoint và tạo lại hoặc implement thêm router riêng khi cần.

##### Test nhanh bằng Postman

1. **Chuẩn bị token**: đăng nhập qua API hiện có để lấy JWT `access_token`. Gán vào header `Authorization: Bearer <token>`.
2. **Tạo endpoint email**  
   - Method: `POST`  
   - URL: `http://localhost:8000/notifications/endpoints`  
   - Headers: `Content-Type: application/json`, `Authorization: Bearer ...`  
   - Body (raw JSON):
     ```json
     {
       "channel": "email",
       "address": "user@example.com",
       "is_primary": true
     }
     ```
   - Response 201 sẽ trả `endpoint_id`. Hệ thống gửi OTP về `user@example.com`.
3. **Xác thực OTP**  
   - Method: `POST`  
   - URL: `http://localhost:8000/notifications/endpoints/{endpoint_id}/verify`  
   - Body:
     ```json
     {
       "auto_verify": false,
       "verification_code": "123456"
     }
     ```
   - Response 200 trả endpoint với `verified=true`. Nếu OTP sai hoặc hết hạn sẽ nhận lỗi 400 với message tương ứng.

Khi cần debug việc gửi mail, hãy đảm bảo `.env` đã cấu hình `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`. Log của Django (logger `app`) sẽ in chi tiết lỗi nếu không gửi được email.

### 7.2 Endpoint truy vấn sự kiện (`apps/notification/routers/event_router.py`)
| Method | Path | Mô tả | Ghi chú |
| ------ | ---- | ----- | ------- |
| `GET` | `/notifications/events?limit=50&offset=0` | Danh sách event của user | Trả `NotificationEventSchema` |
| `GET` | `/notifications/events/{event_id}` | Chi tiết 1 event | 404 nếu không thuộc user |
| `GET` | `/notifications/events/{event_id}/deliveries` | Danh sách deliveries của event | Trả `NotificationDeliverySchema` |
| `POST` | `/notifications/test-send` | Endpoint test nội bộ | Truyền `event_type` (query) và `payload` (body JSON). Tạo event và gửi ngay. |
| `GET` | `/notifications/tradingview-signals?symbol=VNM` | Liệt kê events TradingView | Lọc theo symbol (payload.symbol) nếu cần |

#### Chi tiết endpoints sự kiện

**GET /notifications/events**  
- Query params:
  - `limit` *(int, mặc định 50, max nên giữ <200)*.
  - `offset` *(int, mặc định 0)*.  
- Response: danh sách `NotificationEventSchema`:
  ```json
  {
    "event_id": "01fe50c4-9d6a-43f0-921d-2f88f7afcead",
    "event_type": "symbol_signal",
    "subject_id": "7a38c6b4-082c-49f7-abe7-8381a8550810",
    "payload": {
      "symbol": "VNM",
      "signal_type": "buy",
      "price": "82000",
      "timestamp": "2024-01-01 09:15:00"
    },
    "created_at": "2024-05-16T03:09:12Z",
    "processed": true
  }
  ```

**GET /notifications/events/{event_id}**  
- Path param: `event_id` (UUID).  
- Response: 200 với schema ở trên, 404 nếu user không sở hữu.

**GET /notifications/events/{event_id}/deliveries**  
- Trả danh sách `NotificationDeliverySchema`:
  ```json
  {
    "delivery_id": "86b4e9ad-7a53-4c5c-b783-4548e5ad1a0e",
    "channel": "telegram",
    "status": "sent",
    "sent_at": "2024-05-16T03:09:15Z",
    "error_message": null
  }
  ```

**POST /notifications/test-send**  
- Query param: `event_type` (string, sử dụng một trong `AppEventType`).  
- Body: object tự do `{...}` sẽ map vào `payload`. Ví dụ:
  ```json
  {
    "symbol": "VNM",
    "signal_type": "buy",
    "price": "82000",
    "timestamp": "2024-01-01 09:15:00",
    "description": "Break MA50"
  }
  ```
- Response 200:
  ```json
  {
    "event_id": "6c6ee691-7425-4b4f-9c7d-96adfdf596fa",
    "deliveries_created": 3,
    "deliveries_sent": 2
  }
  ```
- Response 400: `{ "error": "<message>" }` khi thiếu endpoint hoặc lỗi xử lý.

**GET /notifications/tradingview-signals**  
- Query params:
  - `symbol` *(string, optional)*: lọc theo payload.symbol (case-insensitive).  
  - `limit`, `offset`: giống `/notifications/events`.  
- Response: danh sách events `symbol_signal` cho tất cả user (route dùng auth, chỉ nên cấp quyền cho admin).

### 7.3 Webhook (`apps/notification/routers/webhook_router.py`)
- `POST /notifications/webhook/tradingview`  
  - **Auth**: none.  
  - **Body**: `TradingViewWebhookSchema` (JSON). Các trường chính:
    | Field | Kiểu | Bắt buộc | Mô tả |
    | ----- | ---- | -------- | ----- |
    | `Type` | string | ✔ | `BUY` hoặc `SELL` |
    | `TransId` | integer | ✔ | ID giao dịch từ TradingView |
    | `Action` | string | ✔ | `Open`, `Close`, ... |
    | `botName` | string | ✔ | Tên bot thông báo |
    | `Symbol` | string | ✔ | Mã chứng khoán (VD: `VNM`) |
    | `Price` | float | ✔ | Giá tại thời điểm tín hiệu |
    | `CheckDate` | integer | ✔ | UNIX timestamp (ms) |
    | Các trường tùy chọn khác: `MaxPrice`, `MinPrice`, `TP`, `SL`, `ExitPrice`, `Direction`, `PositionSize`, `Profit`, `MaxDrawdown`, `TradeDuration`, `WinLossStatus`, `DistanceToSL`, `DistanceToTP`, `VolatilityAdjustedProfit`. |
  - **Ví dụ request**:
    ```json
    {
      "Type": "BUY",
      "TransId": 1000234,
      "Action": "Open",
      "botName": "TV Momentum Bot",
      "Symbol": "VNM",
      "Price": 82150.5,
      "CheckDate": 1715843580000,
      "TP": 84000,
      "SL": 79000,
      "Direction": "Long",
      "Profit": 2.4,
      "WinLossStatus": "OPEN"
    }
    ```
  - **Response 200**: `{success, symbol, signal_type, total_users, sent_count, failed_count, message}`.  
  - **Response 404**: nếu symbol không tồn tại.  
  - **Response 400**: lỗi xử lý chung (kèm log trong `WebhookLog`).  
  - Ghi log cả request và phản hồi, thuận tiện để audit hoặc debug webhook.

## 8. Services & business flow
- **EndpointService**
  - `list_endpoints`, `create_endpoint`, `update_endpoint`, `delete_endpoint`, `verify_endpoint`.
  - Kiểm tra tồn tại trước khi tạo, đảm bảo unique (`user + channel + address`).
- **NotificationService**
  - `create_event`: tạo record `NotificationEvent`.
  - `process_event`: lấy endpoints đã verified, tạo `NotificationDelivery`, đánh dấu `processed`.
  - `create_and_process_event`: helper tạo + process liền, trả về `(event, deliveries_count)`.
  - `get_user_events`, `get_event_deliveries`.
- **DeliveryService**
  - `send_delivery`: chọn handler theo channel, gọi API tương ứng.
  - `send_pending_deliveries`: duyệt tất cả deliveries `QUEUED`.
  - `retry_failed_deliveries`: đặt trạng thái `retrying` rồi gửi lại.
  - Ghi nhận phản hồi (status, lỗi, response) trong `NotificationDelivery`.
- **Handlers**  
  - `TelegramHandler`: call `https://api.telegram.org/bot{token}/sendMessage` (`parse_mode=HTML`).
  - `ZaloHandler`: call `https://openapi.zalo.me/v3.0/oa/message/cs`.
  - `EmailHandler`: dùng `django.core.mail.send_mail`.
  - Mỗi handler định dạng message theo `event_type`.

## 9. Management commands
| Command | Mục đích | Ví dụ |
| ------- | -------- | ----- |
| `python manage.py create_test_endpoint --user-id 1 --channel telegram --address 123 --verified` | Tạo nhanh endpoint test | Hữu ích để thử luồng gửi thủ công |
| `python manage.py send_pending_notifications --limit 100` | Gửi các deliveries đang `queued` | Dùng chạy cron/Celery |
| `python manage.py retry_failed_notifications --limit 100` | Retry deliveries `failed` | Thường kết hợp monitoring |

Nhớ migrate trước khi dùng: `python manage.py migrate apps.notification`.

## 10. Kiểm thử nhanh
1. **Chuẩn bị user & endpoint**: tạo user, chạy `create_test_endpoint` (hoặc POST `/notifications/endpoints`), set `verified=True`.
2. **Test luồng gửi**: gọi `POST /notifications/test-send` với payload ví dụ:
   ```json
   {
     "event_type": "symbol_signal",
     "payload": {
       "symbol": "VNM",
       "signal_type": "buy",
       "price": "82000",
       "timestamp": "2024-01-01 09:15:00",
       "description": "Mua vượt kháng cự"
     }
   }
   ```
3. **Kiểm tra kết quả**: 
   - Bảng `pay_notification_events`, `pay_notification_deliveries`.
   - Log console (`logger.info` namespace `app`).
   - Kênh Telegram/Zalo/Email nhận tin.
   - Với kênh email, đảm bảo endpoint đã xác thực bằng mã OTP (mã hết hạn sau 2 phút) trước khi kỳ vọng nhận mail sự kiện.
4. **Webhook scenario**: dùng `curl` gửi request JSON giả TradingView đến `/notifications/webhook/tradingview`, đối chiếu `WebhookLog`.

## 11. Các lưu ý mở rộng
- **Xác thực endpoint**: logic OTP chưa hoàn thiện (đã đánh dấu TODO); hiện tại `auto_verify=True` được dùng cho Telegram khi người dùng start bot.
- **Hiệu năng gửi hàng loạt**: hiện tại gửi tuần tự trong process; cân nhắc tích hợp Celery/ task queue nếu sản lượng lớn.
- **An toàn webhook**: router chưa kiểm tra chữ ký/secret; nên bổ sung khi đưa vào production.
- **Giám sát**: theo dõi bảng `NotificationDelivery` để biết trạng thái, sử dụng command `retry_failed_notifications` theo lịch.
- **Mở rộng kênh**: thêm handler mới → cập nhật `NotificationChannel`, implement class mới kế thừa `NotificationHandler`, map trong `HANDLERS`.

---

### Tài liệu liên quan
- `api/router.py`: tích hợp router notifications vào Ninja API (prefix `/notifications/`).
- `apps/notification/migrations/0002_webhooklog.py`: migration tạo bảng `WebhookLog`.
- `core/jwt_auth.py`: middleware xác thực JWT qua header hoặc cookie.

Tuân thủ tài liệu này để triển khai và debug hệ thống thông báo một cách nhất quán.
