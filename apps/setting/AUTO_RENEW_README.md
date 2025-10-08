# HỆ THỐNG TỰ ĐỘNG GIA HẠN LICENSE (AUTO-RENEW)

## 📋 MỤC LỤC
1. [Tổng quan](#1-tổng-quan)
2. [Models - Cấu trúc dữ liệu](#2-models---cấu-trúc-dữ-liệu)
3. [Luồng hoạt động](#3-luồng-hoạt-động)
4. [API Endpoints](#4-api-endpoints)
5. [Cronjob & Background Tasks](#5-cronjob--background-tasks)
6. [Trạng thái Subscription](#6-trạng-thái-subscription)
7. [Error Handling](#7-error-handling)
8. [Testing Guide](#8-testing-guide)

---

## 1. TỔNG QUAN

Hệ thống **Auto-Renew** cho phép tự động gia hạn license Symbol khi sắp hết hạn, giúp user không bị gián đoạn dịch vụ.

### ✅ Tính năng chính:
- 🔄 Tự động gia hạn license trước khi hết hạn (grace period: 12 giờ)
- 💰 Thanh toán tự động từ ví (wallet)
- ⏸️ Tạm dừng/tiếp tục subscription bất cứ lúc nào
- 🚫 Hủy subscription
- 📊 Lịch sử attempts (thành công/thất bại)
- 🔁 Retry mechanism (3 lần, mỗi 60 phút)
- 🔔 Auto-cancel nếu ví không đủ tiền

### 🔗 Liên kết với hệ thống:
- **SeaPay**: Xử lý thanh toán, tạo license mới
- **Symbol**: Bot/Trading Signal cần gia hạn
- **Wallet**: Nguồn tiền cho auto-renew

---

## 2. MODELS - CẤU TRÚC DỮ LIỆU

### 2.1. SymbolAutoRenewSubscription

**Bảng:** `symbol_autorenew_subscriptions`

Lưu trữ thông tin đăng ký auto-renew của user cho 1 Symbol.

```python
SymbolAutoRenewSubscription
├── subscription_id: UUID (Primary Key)
├── user: ForeignKey(User)
├── symbol_id: BigInteger               # ID của Symbol cần gia hạn
├── status: VARCHAR(20)                 # pending_activation/active/paused/suspended/cancelled/completed
├── cycle_days: PositiveInteger         # Chu kỳ gia hạn (mặc định: 30 ngày)
├── price: Decimal(18,2)                # Giá mỗi lần gia hạn
├── payment_method: VARCHAR(30)         # wallet/sepay_transfer (hiện chỉ support wallet)
├── last_order: ForeignKey(PaySymbolOrder)              # Order gần nhất
├── current_license: ForeignKey(PayUserSymbolLicense)   # License hiện tại
├── next_billing_at: DateTime           # Thời điểm gia hạn tiếp theo
├── last_attempt_at: DateTime           # Lần thử gần nhất
├── last_success_at: DateTime           # Lần thành công gần nhất
├── consecutive_failures: SmallInt      # Số lần thất bại liên tiếp
├── grace_period_hours: Integer         # Thời gian trước hết hạn để gia hạn (mặc định: 12h)
├── retry_interval_minutes: Integer     # Thời gian giữa các retry (mặc định: 60 phút)
├── max_retry_attempts: SmallInt        # Số lần retry tối đa (mặc định: 3)
├── metadata: JSONField                 # Dữ liệu bổ sung
├── created_at, updated_at
```

**Unique Constraint:**
- Mỗi user chỉ có 1 subscription ACTIVE/PAUSED/PENDING cho 1 Symbol

**Indexes:**
- `(user, symbol_id)` - Tìm subscription của user
- `status` - Lọc theo trạng thái
- `next_billing_at` - Cronjob tìm subscription đến hạn

---

### 2.2. SymbolAutoRenewAttempt

**Bảng:** `symbol_autorenew_attempts`

Lưu lịch sử mỗi lần thử gia hạn (thành công hoặc thất bại).

```python
SymbolAutoRenewAttempt
├── attempt_id: UUID (Primary Key)
├── subscription: ForeignKey(SymbolAutoRenewSubscription)
├── order: ForeignKey(PaySymbolOrder)           # Order được tạo (nếu thành công)
├── status: VARCHAR(20)                         # success/failed/skipped
├── fail_reason: TEXT                           # Lý do thất bại (nếu có)
├── charged_amount: Decimal(18,2)               # Số tiền đã trừ
├── wallet_balance_snapshot: Decimal(18,2)      # Số dư ví tại thời điểm attempt
├── ran_at: DateTime                            # Thời điểm chạy
├── created_at
```

**Status:**
- `success`: Gia hạn thành công, đã tạo order + license mới
- `failed`: Thất bại (thiếu tiền, lỗi hệ thống)
- `skipped`: Bỏ qua (payment method không hợp lệ)

---

## 3. LUỒNG HOẠT ĐỘNG

### 3.1. Luồng tạo Subscription (Khi user mua license lần đầu)

```
┌─────────────────────────────────────────────────────────────┐
│  BƯỚC 1: User mua Symbol với auto_renew = true             │
│  POST /api/sepay/symbol/orders/                            │
│  {                                                          │
│    "items": [{                                              │
│      "symbol_id": 1,                                        │
│      "price": 200000,                                       │
│      "license_days": 30,                                    │
│      "auto_renew": true,           ← Bật auto-renew        │
│      "auto_renew_price": 200000,   ← Giá mỗi lần gia hạn   │
│      "auto_renew_cycle_days": 30   ← Chu kỳ gia hạn        │
│    }],                                                      │
│    "payment_method": "wallet"                               │
│  }                                                          │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  BƯỚC 2: SymbolPurchaseService.create_symbol_order()       │
│  1. Tạo PaySymbolOrder + PaySymbolOrderItem                │
│  2. Gọi SymbolAutoRenewService.sync_pending_from_order()   │
│     → Tạo SymbolAutoRenewSubscription                      │
│     → status = "pending_activation"                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  BƯỚC 3: User thanh toán thành công                        │
│  - Nếu wallet: Trả tiền ngay                               │
│  - Nếu SePay: Webhook callback                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  BƯỚC 4: SymbolPurchaseService xử lý sau thanh toán        │
│  1. Tạo PayUserSymbolLicense (license mới)                 │
│  2. Gọi SymbolAutoRenewService.activate_for_order()        │
│     → Kích hoạt subscription                               │
│     → status = "active"                                     │
│     → next_billing_at = license.end_at - 12 giờ           │
│                                                             │
│  Ví dụ:                                                     │
│  - License hết hạn: 2025-11-06 00:00:00                   │
│  - next_billing_at: 2025-11-05 12:00:00 (trừ 12h)        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  Subscription ACTIVE  │
                 │  Đợi cronjob gia hạn  │
                 └───────────────────────┘
```

---

### 3.2. Luồng Auto-Renew (Cronjob chạy định kỳ)

```
┌────────────────────────────────────────────────────────────┐
│  CRONJOB: Chạy mỗi 5-10 phút                              │
│  Gọi SymbolAutoRenewService.run_due_subscriptions()       │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  BƯỚC 1: Query subscriptions đến hạn                       │
│  SELECT * FROM symbol_autorenew_subscriptions              │
│  WHERE status = 'active'                                   │
│    AND next_billing_at <= NOW()                            │
│  ORDER BY next_billing_at                                  │
│  LIMIT 50                                                  │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  BƯỚC 2: Với mỗi subscription                              │
│                                                            │
│  2.1. Lock subscription (SELECT FOR UPDATE)                │
│  2.2. Check payment_method = "wallet"                      │
│       → Nếu không phải: SKIP                               │
│                                                            │
│  2.3. Lấy ví user (SELECT FOR UPDATE)                      │
│       → Nếu không có ví: CANCEL subscription              │
│                                                            │
│  2.4. Check số dư: wallet.balance >= subscription.price   │
│       → Nếu thiếu tiền: CANCEL subscription               │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  BƯỚC 3: Tạo Order gia hạn tự động                         │
│                                                            │
│  SymbolPurchaseService.create_symbol_order(                │
│    user=user,                                              │
│    items=[{                                                │
│      "symbol_id": subscription.symbol_id,                  │
│      "price": subscription.price,                          │
│      "license_days": subscription.cycle_days,              │
│      "auto_renew": True  ← Giữ nguyên auto-renew          │
│    }],                                                     │
│    payment_method="wallet",                                │
│    description="Auto-renew for symbol X"                   │
│  )                                                         │
│                                                            │
│  → Trừ tiền ví ngay lập tức                               │
│  → Tạo license mới (extend từ license cũ)                 │
└────────────────────────┬───────────────────────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
   THÀNH CÔNG                         THẤT BẠI
        │                                  │
        ▼                                  ▼
┌───────────────────┐            ┌──────────────────────┐
│ Tạo Attempt       │            │ Tạo Attempt          │
│ status=success    │            │ status=failed        │
│                   │            │                      │
│ Update sub:       │            │ Update sub:          │
│ - last_success_at │            │ - consecutive_failures++│
│ - consecutive_     │            │ - last_attempt_at    │
│   failures = 0    │            │                      │
│ - current_license │            │ Nếu failures >= 3:   │
│ - next_billing_at │            │   → status=suspended │
│   (license.end_at │            │   → next_billing=null│
│    - 12h)         │            │                      │
└───────────────────┘            │ Nếu failures < 3:    │
                                 │   → Retry sau 60 phút│
                                 └──────────────────────┘
```

---

### 3.3. Luồng Extend License (Gia hạn)

Khi auto-renew thành công, license được **extend** (kéo dài thời gian), không tạo license mới.

**Code:** `SymbolPurchaseService._create_symbol_licenses()` (line 403-442)

```python
# Kiểm tra xem user đã có license ACTIVE cho symbol này chưa
existing = PayUserSymbolLicense.objects.filter(
    user=order.user,
    symbol_id=item.symbol_id,
    status=LicenseStatus.ACTIVE,
).first()

if existing:
    # ✅ EXTEND license hiện tại
    if existing.end_at and end_at:
        # Lấy ngày muộn hơn
        existing.end_at = max(existing.end_at, end_at)
    elif not end_at:
        # Nếu mua lifetime → set end_at = null
        existing.end_at = None

    existing.order = order  # Link order mới
    existing.save()
else:
    # ❌ Tạo license mới (trường hợp lần đầu)
    PayUserSymbolLicense.objects.create(...)
```

**Ví dụ:**

```
License hiện tại:
- start_at: 2025-10-06 10:00:00
- end_at: 2025-11-05 10:00:00

Auto-renew tạo order mới với license_days=30

License sau extend:
- start_at: 2025-10-06 10:00:00  (không đổi)
- end_at: 2025-12-05 10:00:00    (thêm 30 ngày)
```

---

## 4. API ENDPOINTS

### 4.1. Xem danh sách subscriptions

**GET** `/api/settings/symbol/subscriptions`

Lấy tất cả subscriptions của user.

**Request:**
```http
GET /api/settings/symbol/subscriptions
Authorization: Bearer {jwt_token}
```

**Response:**
```json
[
  {
    "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
    "symbol_id": 1,
    "status": "active",
    "cycle_days": 30,
    "price": 200000.0,
    "payment_method": "wallet",
    "next_billing_at": "2025-11-05T12:00:00Z",      // 12 giờ trước hết hạn
    "last_success_at": "2025-10-06T10:00:00Z",
    "last_attempt_at": null,
    "consecutive_failures": 0,
    "grace_period_hours": 12,
    "retry_interval_minutes": 60,
    "max_retry_attempts": 3,
    "current_license_id": "def67890-e89b-12d3-a456-426614174000",
    "last_order_id": "789e0123-e89b-12d3-a456-426614174000",
    "created_at": "2025-10-06T10:00:00Z",
    "updated_at": "2025-10-06T10:00:00Z"
  }
]
```

---

### 4.2. Tạm dừng subscription

**POST** `/api/settings/symbol/subscriptions/{subscription_id}/pause`

Tạm dừng gia hạn tự động. User có thể resume sau.

**Request:**
```http
POST /api/settings/symbol/subscriptions/abc12345-e89b-12d3-a456-426614174000/pause
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
  "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
  "status": "paused",
  ...
}
```

**Lưu ý:**
- License hiện tại vẫn valid đến hết `end_at`
- Không có billing mới cho đến khi resume
- `next_billing_at` vẫn giữ nguyên

---

### 4.3. Tiếp tục subscription

**POST** `/api/settings/symbol/subscriptions/{subscription_id}/resume`

Kích hoạt lại subscription đã pause.

**Request:**
```http
POST /api/settings/symbol/subscriptions/abc12345-e89b-12d3-a456-426614174000/resume
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
  "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
  "status": "active",
  ...
}
```

**Logic đặc biệt:**
- Check số dư ví trước khi resume
- Nếu thiếu tiền → Auto-cancel luôn, không cho resume

---

### 4.4. Hủy subscription

**POST** `/api/settings/symbol/subscriptions/{subscription_id}/cancel`

Hủy vĩnh viễn subscription.

**Request:**
```http
POST /api/settings/symbol/subscriptions/abc12345-e89b-12d3-a456-426614174000/cancel
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
  "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
  "status": "cancelled",
  "next_billing_at": null,
  "current_license_id": null,
  ...
}
```

**Lưu ý:**
- `next_billing_at` = null
- `current_license_id` = null
- License hiện tại vẫn valid đến hết hạn, nhưng không tự động gia hạn
- User phải mua lại từ đầu nếu muốn tiếp tục

---

### 4.5. Xem lịch sử attempts

**GET** `/api/settings/symbol/subscriptions/{subscription_id}/attempts`

Lấy lịch sử các lần thử gia hạn (thành công/thất bại).

**Request:**
```http
GET /api/settings/symbol/subscriptions/abc12345-e89b-12d3-a456-426614174000/attempts?limit=20
Authorization: Bearer {jwt_token}
```

**Response:**
```json
[
  {
    "attempt_id": "111e1111-e89b-12d3-a456-426614174000",
    "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
    "status": "success",
    "fail_reason": "",
    "charged_amount": 200000.0,
    "wallet_balance_snapshot": 500000.0,
    "order_id": "789e0123-e89b-12d3-a456-426614174000",
    "ran_at": "2025-10-06T10:00:00Z"
  },
  {
    "attempt_id": "222e2222-e89b-12d3-a456-426614174000",
    "subscription_id": "abc12345-e89b-12d3-a456-426614174000",
    "status": "failed",
    "fail_reason": "Insufficient balance: requires 200000, has 50000",
    "charged_amount": null,
    "wallet_balance_snapshot": 50000.0,
    "order_id": null,
    "ran_at": "2025-09-06T10:00:00Z"
  }
]
```

---

## 5. CRONJOB & BACKGROUND TASKS

### 5.1. Setup Cronjob

Cần chạy cronjob định kỳ để xử lý auto-renew:

**Cách 1: Django Management Command**

```python
# apps/setting/management/commands/run_autorenew.py

from django.core.management.base import BaseCommand
from apps.setting.services.subscription_service import SymbolAutoRenewService

class Command(BaseCommand):
    help = 'Run auto-renew for due subscriptions'

    def handle(self, *args, **options):
        service = SymbolAutoRenewService()
        result = service.run_due_subscriptions(limit=50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed: {result['processed']}, "
                f"Success: {result['success']}, "
                f"Failed: {result['failed']}, "
                f"Skipped: {result['skipped']}"
            )
        )
```

**Chạy:**
```bash
python manage.py run_autorenew
```

---

**Cách 2: Celery Task (Khuyến nghị cho production)**

```python
# apps/setting/tasks.py

from celery import shared_task
from apps.setting.services.subscription_service import SymbolAutoRenewService

@shared_task
def run_autorenew_subscriptions():
    service = SymbolAutoRenewService()
    result = service.run_due_subscriptions(limit=50)
    return result
```

**Celery Beat Schedule:**
```python
# config/settings.py

CELERY_BEAT_SCHEDULE = {
    'run-autorenew-every-5-minutes': {
        'task': 'apps.setting.tasks.run_autorenew_subscriptions',
        'schedule': 300,  # 5 phút
    },
}
```

---

**Cách 3: Linux Cron**

```bash
# /etc/crontab hoặc crontab -e

# Chạy mỗi 5 phút
*/5 * * * * cd /path/to/project && python manage.py run_autorenew >> /var/log/autorenew.log 2>&1
```

---

### 5.2. Monitoring & Alerting

**Metrics cần theo dõi:**

1. **Success Rate:**
   ```sql
   SELECT
     COUNT(CASE WHEN status = 'success' THEN 1 END) * 100.0 / COUNT(*) as success_rate
   FROM symbol_autorenew_attempts
   WHERE ran_at >= NOW() - INTERVAL '24 hours';
   ```

2. **Subscriptions bị suspended:**
   ```sql
   SELECT COUNT(*) FROM symbol_autorenew_subscriptions
   WHERE status = 'suspended';
   ```

3. **Subscriptions sắp đến hạn (trong 1 giờ tới):**
   ```sql
   SELECT COUNT(*) FROM symbol_autorenew_subscriptions
   WHERE status = 'active'
     AND next_billing_at <= NOW() + INTERVAL '1 hour';
   ```

---

## 6. TRẠNG THÁI SUBSCRIPTION

### 6.1. Lifecycle của Subscription

```
┌──────────────────┐
│ pending_activation│ ← Vừa tạo, chờ order đầu tiên paid
└────────┬─────────┘
         │ Order paid
         ▼
┌──────────────────┐
│      active      │ ← Đang hoạt động, auto-renew bật
└────┬────┬────┬───┘
     │    │    │
     │    │    └──────────────┐
     │    │                   │
     │    │ User pause        │ Thiếu tiền/lỗi >= 3 lần
     │    ▼                   ▼
     │ ┌────────┐      ┌─────────────┐
     │ │ paused │      │  suspended  │
     │ └───┬────┘      └──────┬──────┘
     │     │ Resume           │
     │     │                  │ Admin fix
     │     └──────────────────┘
     │
     │ User cancel
     ▼
┌──────────────────┐
│    cancelled     │ ← Đã hủy vĩnh viễn
└──────────────────┘

┌──────────────────┐
│    completed     │ ← License lifetime, không cần renew nữa
└──────────────────┘
```

### 6.2. Chi tiết các trạng thái

| Status | Mô tả | next_billing_at | Cronjob xử lý |
|--------|-------|----------------|---------------|
| `pending_activation` | Mới tạo, chờ order đầu tiên paid | null | ❌ Không |
| `active` | Đang hoạt động | Not null | ✅ Có |
| `paused` | User tạm dừng | Giữ nguyên | ❌ Không |
| `suspended` | Thất bại >= 3 lần | null | ❌ Không |
| `cancelled` | User hủy | null | ❌ Không |
| `completed` | License lifetime | null | ❌ Không |

---

## 7. ERROR HANDLING

### 7.1. Xử lý thiếu tiền (Insufficient Balance)

**Khi detect thiếu tiền:**

1. Tạo `SymbolAutoRenewAttempt` với:
   - `status = "failed"`
   - `fail_reason = "Insufficient balance: requires X, has Y"`
   - `wallet_balance_snapshot = Y`

2. Update subscription:
   - `status = "cancelled"`
   - `next_billing_at = null`
   - `consecutive_failures = 0` (reset vì đây là cancel, không phải retry)

3. **KHÔNG retry** - Cancel ngay lập tức

**Rationale:** Nếu ví thiếu tiền, rất khó có khả năng trong 1 giờ tới sẽ có tiền. User phải tự nạp tiền và resume.

---

### 7.2. Xử lý lỗi hệ thống (System Errors)

**Các lỗi khác (không phải thiếu tiền):**

1. Tạo `SymbolAutoRenewAttempt` với:
   - `status = "failed"`
   - `fail_reason = "Error message"`

2. Update subscription:
   - `consecutive_failures += 1`
   - `last_attempt_at = now`

3. **Retry logic:**
   - Nếu `consecutive_failures < 3`:
     - `next_billing_at = now + 60 minutes`
     - Cronjob sẽ retry sau 60 phút

   - Nếu `consecutive_failures >= 3`:
     - `status = "suspended"`
     - `next_billing_at = null`
     - Dừng auto-renew, cần admin can thiệp

---

### 7.3. Skip Payment Method không hợp lệ

**Hiện tại chỉ support `payment_method = "wallet"`**

Nếu subscription có `payment_method != "wallet"`:

1. Tạo `SymbolAutoRenewAttempt` với:
   - `status = "skipped"`
   - `fail_reason = "Auto-renew currently requires wallet payment"`

2. Update subscription:
   - `next_billing_at = now + 60 minutes`
   - Tiếp tục skip trong các lần chạy tiếp theo

**Rationale:** Để lại khả năng mở rộng cho SePay auto-renew sau này.

---

## 8. TESTING GUIDE

### 8.1. Test Manual với Django Shell

```python
python manage.py shell

from django.contrib.auth import get_user_model
from apps.setting.services.subscription_service import SymbolAutoRenewService
from apps.seapay.models import PayWallet
from decimal import Decimal

User = get_user_model()
service = SymbolAutoRenewService()

# Lấy user test
user = User.objects.get(email='test@example.com')

# Xem subscriptions
subs = service.list_user_subscriptions(user)
print(subs)

# Test run auto-renew
result = service.run_due_subscriptions(limit=10)
print(result)
# {'processed': 2, 'success': 1, 'failed': 1, 'skipped': 0}
```

---

### 8.2. Test Case: Đủ tiền, gia hạn thành công

**Setup:**
```python
# Nạp ví 500k
wallet = PayWallet.objects.get(user=user)
wallet.balance = Decimal('500000')
wallet.save()

# Tạo subscription sắp đến hạn
from apps.setting.models import SymbolAutoRenewSubscription
from django.utils import timezone
from datetime import timedelta

sub = SymbolAutoRenewSubscription.objects.create(
    user=user,
    symbol_id=1,
    status='active',
    cycle_days=30,
    price=Decimal('200000'),
    payment_method='wallet',
    next_billing_at=timezone.now() - timedelta(hours=1),  # Đã quá hạn 1 giờ
)
```

**Chạy:**
```python
result = service.run_due_subscriptions()
print(result)
# {'processed': 1, 'success': 1, 'failed': 0, 'skipped': 0}

# Check kết quả
sub.refresh_from_db()
print(sub.status)  # active
print(sub.consecutive_failures)  # 0
print(sub.last_success_at)  # Vừa update

# Check license mới
from apps.seapay.models import PayUserSymbolLicense
license = PayUserSymbolLicense.objects.filter(user=user, symbol_id=1).first()
print(license.end_at)  # Đã extend thêm 30 ngày
```

---

### 8.3. Test Case: Thiếu tiền, auto-cancel

**Setup:**
```python
# Ví chỉ còn 50k
wallet.balance = Decimal('50000')
wallet.save()

# Subscription cần 200k
sub.next_billing_at = timezone.now() - timedelta(hours=1)
sub.save()
```

**Chạy:**
```python
result = service.run_due_subscriptions()
print(result)
# {'processed': 1, 'success': 0, 'failed': 1, 'skipped': 0}

# Check kết quả
sub.refresh_from_db()
print(sub.status)  # cancelled (không phải suspended!)
print(sub.next_billing_at)  # None

# Check attempt
from apps.setting.models import SymbolAutoRenewAttempt
attempt = SymbolAutoRenewAttempt.objects.filter(subscription=sub).last()
print(attempt.status)  # failed
print(attempt.fail_reason)  # Insufficient balance: requires 200000, has 50000
print(attempt.wallet_balance_snapshot)  # 50000
```

---

### 8.4. Test Case: Lỗi hệ thống, retry 3 lần

**Simulate bằng cách mock exception:**

```python
# Patch service để raise exception
from unittest.mock import patch

with patch.object(
    service,
    '_create_renewal_order',
    side_effect=Exception("Database connection error")
):
    # Lần 1
    result = service.run_due_subscriptions()
    sub.refresh_from_db()
    print(sub.consecutive_failures)  # 1
    print(sub.status)  # active

    # Lần 2
    result = service.run_due_subscriptions()
    sub.refresh_from_db()
    print(sub.consecutive_failures)  # 2
    print(sub.status)  # active

    # Lần 3
    result = service.run_due_subscriptions()
    sub.refresh_from_db()
    print(sub.consecutive_failures)  # 3
    print(sub.status)  # suspended (đã vượt max_retry_attempts)
    print(sub.next_billing_at)  # None
```

---

## 9. BEST PRACTICES

### 9.1. Cho User

✅ **Nên:**
- Đảm bảo ví luôn có đủ tiền trước `next_billing_at`
- Kiểm tra subscriptions định kỳ qua API
- Pause subscription khi không cần dùng tạm thời
- Cancel nếu không dùng nữa (tiết kiệm tiền)

❌ **Không nên:**
- Để ví cạn tiền → Auto-cancel subscription
- Quên mất subscription đang chạy

---

### 9.2. Cho Developer

✅ **Nên:**
- Chạy cronjob mỗi 5-10 phút
- Monitor success rate hàng ngày
- Alert khi có subscriptions bị suspended
- Log đầy đủ để debug
- Test kỹ trước khi deploy

❌ **Không nên:**
- Chạy cronjob quá dày (< 1 phút) → Tốn tài nguyên
- Quên handle edge cases (license lifetime, thiếu tiền, ...)
- Skip transaction atomic → Dữ liệu inconsistent

---

## 10. TROUBLESHOOTING

### 10.1. Subscription không tự động gia hạn

**Check list:**

1. ✅ Cronjob có chạy không?
   ```bash
   tail -f /var/log/autorenew.log
   ```

2. ✅ Subscription status = "active"?
   ```sql
   SELECT * FROM symbol_autorenew_subscriptions WHERE subscription_id = '...';
   ```

3. ✅ `next_billing_at` đã quá giờ hiện tại chưa?
   ```sql
   SELECT next_billing_at, NOW() FROM symbol_autorenew_subscriptions WHERE ...;
   ```

4. ✅ Ví có đủ tiền không?
   ```sql
   SELECT balance FROM pay_wallets WHERE user_id = ...;
   ```

5. ✅ Check attempts gần nhất:
   ```sql
   SELECT * FROM symbol_autorenew_attempts
   WHERE subscription_id = '...'
   ORDER BY ran_at DESC LIMIT 5;
   ```

---

### 10.2. Subscription bị suspended

**Nguyên nhân:**
- Thất bại >= 3 lần liên tiếp (không phải thiếu tiền)

**Cách fix:**

1. Kiểm tra lý do thất bại:
   ```sql
   SELECT fail_reason FROM symbol_autorenew_attempts
   WHERE subscription_id = '...' AND status = 'failed'
   ORDER BY ran_at DESC LIMIT 3;
   ```

2. Fix lỗi (ví dụ: lỗi database, lỗi Symbol không tồn tại, ...)

3. Resume subscription:
   ```python
   service.resume_subscription(subscription_id, user)
   ```

4. Hoặc update status thủ công:
   ```sql
   UPDATE symbol_autorenew_subscriptions
   SET status = 'active',
       consecutive_failures = 0,
       next_billing_at = license.end_at - INTERVAL '12 hours'
   WHERE subscription_id = '...';
   ```

---

### 10.3. License không extend sau khi gia hạn thành công

**Check:**

1. Order có tạo thành công không?
   ```sql
   SELECT * FROM pay_symbol_orders WHERE description LIKE '%Auto-renew%';
   ```

2. License có được tạo không?
   ```sql
   SELECT * FROM pay_user_symbol_licenses WHERE order_id = '...';
   ```

3. License có link đến subscription không?
   ```sql
   SELECT subscription_id FROM pay_user_symbol_licenses WHERE license_id = '...';
   ```

---

## 11. LIÊN HỆ & HỖ TRỢ

- **Code location:** `apps/setting/services/subscription_service.py`
- **Models:** `apps/setting/models.py`
- **API:** `apps/setting/api.py`

---

**Phiên bản:** 1.0.0
**Cập nhật lần cuối:** 2025-10-06
**Tác giả:** Development Team
