# APPS/SETTING - HỆ THỐNG CÀI ĐẶT & AUTO-RENEW

## 📋 Tổng quan

Module **setting** quản lý:
- ⚙️ Key-value settings (system-wide và per-user)
- 🔄 **Auto-Renew Subscriptions** - Tự động gia hạn license Symbol

---

## 🚀 Quick Start

### 1. Xem subscriptions của user

```bash
GET /api/settings/symbol/subscriptions
Authorization: Bearer {jwt_token}
```

### 2. Tạo subscription (tự động khi mua Symbol với auto_renew=true)

```json
POST /api/sepay/symbol/orders/
{
  "items": [{
    "symbol_id": 1,
    "price": 200000,
    "license_days": 30,
    "auto_renew": true,              // ← Bật auto-renew
    "auto_renew_price": 200000,      // ← Giá mỗi lần gia hạn
    "auto_renew_cycle_days": 30      // ← Chu kỳ gia hạn
  }],
  "payment_method": "wallet"
}
```

### 3. Quản lý subscription

```bash
# Tạm dừng
POST /api/settings/symbol/subscriptions/{id}/pause

# Tiếp tục
POST /api/settings/symbol/subscriptions/{id}/resume

# Hủy
POST /api/settings/symbol/subscriptions/{id}/cancel

# Xem lịch sử attempts
GET /api/settings/symbol/subscriptions/{id}/attempts?limit=20
```

---

## ⚙️ Setup Cronjob

**Option 1: Django Command**
```bash
*/5 * * * * cd /path/to/project && python manage.py run_autorenew
```

**Option 2: Celery (Khuyến nghị)**
```python
# Chạy mỗi 5 phút
CELERY_BEAT_SCHEDULE = {
    'autorenew': {
        'task': 'apps.setting.tasks.run_autorenew_subscriptions',
        'schedule': 300,
    },
}
```

---

## 📊 Models

### SymbolAutoRenewSubscription
Lưu thông tin đăng ký auto-renew.

**Key fields:**
- `status`: pending_activation/active/paused/suspended/cancelled/completed
- `next_billing_at`: Thời điểm gia hạn tiếp theo (12 giờ trước hết hạn)
- `price`: Giá mỗi lần gia hạn
- `cycle_days`: Chu kỳ (mặc định: 30 ngày)

### SymbolAutoRenewAttempt
Lưu lịch sử mỗi lần thử gia hạn.

**Status:**
- `success`: Thành công
- `failed`: Thất bại (thiếu tiền, lỗi hệ thống)
- `skipped`: Bỏ qua (payment method không hợp lệ)

---

## 🔄 Luồng Auto-Renew

```
1. User mua license với auto_renew=true
   → Tạo SymbolAutoRenewSubscription (pending_activation)

2. Thanh toán thành công
   → Kích hoạt subscription (active)
   → Set next_billing_at = license.end_at - 12 giờ

3. Cronjob chạy định kỳ (mỗi 5 phút)
   → Tìm subscriptions đến hạn
   → Check số dư ví
   → Tạo order gia hạn tự động
   → Extend license

4. Xử lý lỗi:
   - Thiếu tiền: Cancel ngay, không retry
   - Lỗi khác: Retry 3 lần (mỗi 60 phút)
   - Thất bại >= 3 lần: Suspended
```

---

## 📖 Tài liệu chi tiết

Xem: [AUTO_RENEW_README.md](./AUTO_RENEW_README.md)

Bao gồm:
- ✅ Chi tiết models và fields
- ✅ Luồng xử lý đầy đủ với sơ đồ
- ✅ API endpoints & examples
- ✅ Error handling strategies
- ✅ Testing guide với code examples
- ✅ Troubleshooting common issues
- ✅ Best practices

---

## 🎯 Use Cases

### User muốn dùng lâu dài
```
→ Bật auto_renew khi mua
→ Đảm bảo ví luôn có tiền
→ License tự động gia hạn, không bị gián đoạn
```

### User muốn dùng tạm thời
```
→ Không bật auto_renew
→ Hoặc pause subscription khi không cần
→ Resume khi cần dùng lại
```

### User muốn dừng hẳn
```
→ Cancel subscription
→ License hiện tại vẫn valid đến hết hạn
→ Phải mua lại nếu muốn tiếp tục
```

---

## 🔔 Monitoring

**Metrics quan trọng:**

```sql
-- Success rate trong 24h
SELECT
  COUNT(CASE WHEN status = 'success' THEN 1 END) * 100.0 / COUNT(*) as success_rate
FROM symbol_autorenew_attempts
WHERE ran_at >= NOW() - INTERVAL '24 hours';

-- Subscriptions bị suspended (cần attention)
SELECT COUNT(*) FROM symbol_autorenew_subscriptions
WHERE status = 'suspended';

-- Subscriptions sắp đến hạn (trong 1 giờ tới)
SELECT COUNT(*) FROM symbol_autorenew_subscriptions
WHERE status = 'active'
  AND next_billing_at <= NOW() + INTERVAL '1 hour';
```

---

## ⚠️ Important Notes

1. **Chỉ support wallet payment** - SePay auto-renew chưa implement
2. **Grace period: 12 giờ** - Gia hạn trước 12 giờ trước hết hạn
3. **Retry: 3 lần, mỗi 60 phút** - Sau 3 lần thất bại → Suspended
4. **Thiếu tiền → Cancel ngay** - Không retry, user phải tự nạp tiền
5. **License extend, không tạo mới** - Kéo dài `end_at` của license hiện tại

---

## 🔗 Liên kết

- **SeaPay Module:** [../seapay/README.md](../seapay/README.md)
- **Auto-Renew Chi tiết:** [AUTO_RENEW_README.md](./AUTO_RENEW_README.md)

---

**Version:** 1.0.0
**Last Updated:** 2025-10-06
