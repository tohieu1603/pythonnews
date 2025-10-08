# HƯỚNG DẪN TEST SEAPAY API VỚI POSTMAN

## 📋 MỤC LỤC
1. [Chuẩn bị môi trường](#1-chuẩn-bị-môi-trường)
2. [Setup Postman Collection](#2-setup-postman-collection)
3. [Authentication - Lấy JWT Token](#3-authentication---lấy-jwt-token)
4. [Test Wallet & Top-up](#4-test-wallet--top-up)
5. [Test Symbol Purchase](#5-test-symbol-purchase)
6. [Test License Management](#6-test-license-management)
7. [Test Webhook](#7-test-webhook)
8. [Automation Scripts](#8-automation-scripts)
9. [Test Scenarios](#9-test-scenarios)

---

## 1. CHUẨN BỊ MÔI TRƯỜNG

### 1.1. Yêu cầu
- ✅ Postman Desktop hoặc Postman Web
- ✅ Backend server đang chạy tại `http://localhost:8000`
- ✅ Database đã migrate
- ✅ Có tài khoản user để test

### 1.2. Kiểm tra server
```bash
# Terminal
python manage.py runserver

# Truy cập API docs
http://localhost:8000/api/docs
```

---

## 2. SETUP POSTMAN COLLECTION

### Bước 1: Tạo Collection mới
1. Mở Postman
2. Click **New** → **Collection**
3. Đặt tên: `SeaPay API`

### Bước 2: Thêm Variables
Click vào Collection → Tab **Variables**

| Variable | Type | Initial Value | Current Value |
|----------|------|--------------|---------------|
| base_url | default | `http://localhost:8000` | `http://localhost:8000` |
| jwt_token | default | (để trống) | (để trống) |
| intent_id | default | (để trống) | (để trống) |
| order_id | default | (để trống) | (để trống) |
| symbol_id | default | `1` | `1` |

### Bước 3: Tạo Environment (Optional)
Nếu test nhiều môi trường:

**Local Environment:**
- `base_url`: `http://localhost:8000`

**Staging Environment:**
- `base_url`: `https://staging.yourdomain.com`

**Production Environment:**
- `base_url`: `https://api.yourdomain.com`

---

## 3. AUTHENTICATION - LẤY JWT TOKEN

### 📌 Request 1: Login để lấy token

**Method:** `POST`
**URL:** `{{base_url}}/api/auth/login`

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response mẫu:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Tests Script (tự động lưu token):**
```javascript
pm.test("Login successful", function() {
    pm.response.to.have.status(200);
});

pm.test("Save JWT token", function() {
    const response = pm.response.json();
    pm.expect(response).to.have.property("access_token");
    pm.collectionVariables.set("jwt_token", response.access_token);
    console.log("✅ Token saved:", response.access_token.substring(0, 20) + "...");
});
```

---

## 4. TEST WALLET & TOP-UP

### 📌 Request 2: Xem thông tin ví

**Method:** `GET`
**URL:** `{{base_url}}/api/seapay/wallet/`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Response mẫu:**
```json
{
  "wallet_id": "123e4567-e89b-12d3-a456-426614174000",
  "balance": 0.0,
  "currency": "VND",
  "status": "active",
  "created_at": "2024-11-15T00:00:00Z",
  "updated_at": "2024-11-15T00:00:00Z"
}
```

**Tests:**
```javascript
pm.test("Wallet exists", function() {
    pm.response.to.have.status(200);
    const wallet = pm.response.json();
    pm.expect(wallet).to.have.property("wallet_id");
    pm.expect(wallet).to.have.property("balance");
});
```

---

### 📌 Request 3: Tạo yêu cầu nạp tiền

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/wallet/topup/`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "amount": 100000,
  "currency": "VND",
  "bank_code": "BIDV",
  "expires_in_minutes": 60
}
```

**Response mẫu:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "TOPUP1699999999ABCD1234",
  "amount": 100000,
  "currency": "VND",
  "status": "processing",
  "qr_image_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=100000&des=TOPUP1699999999ABCD1234&template=compact",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=100000&des=TOPUP1699999999ABCD1234&template=compact",
  "account_number": "96247CISI1",
  "account_name": "BIDV Account",
  "transfer_content": "TOPUP1699999999ABCD1234",
  "bank_code": "BIDV",
  "expires_at": "2024-11-15T10:30:00Z",
  "message": "Topup request created successfully. Please scan the QR code to complete payment."
}
```

**Tests:**
```javascript
pm.test("Topup request created", function() {
    pm.response.to.have.status(200);
});

pm.test("Save intent_id", function() {
    const response = pm.response.json();
    pm.expect(response).to.have.property("intent_id");
    pm.collectionVariables.set("intent_id", response.intent_id);
    console.log("✅ Intent ID:", response.intent_id);
    console.log("📱 QR Code:", response.qr_code_url);
    console.log("💬 Transfer content:", response.transfer_content);
});
```

**🔔 Lưu ý:** Copy `qr_code_url` và mở trong browser để xem QR code, hoặc copy `transfer_content` để chuyển khoản thủ công.

---

### 📌 Request 4: Kiểm tra trạng thái nạp tiền

**Method:** `GET`
**URL:** `{{base_url}}/api/seapay/wallet/topup/{{intent_id}}/status`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Response mẫu (đang chờ):**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "TOPUP1699999999ABCD1234",
  "amount": 100000,
  "status": "processing",
  "is_expired": false,
  "qr_image_url": "https://qr.sepay.vn/...",
  "account_number": "96247CISI1",
  "account_name": "BIDV Account",
  "transfer_content": "TOPUP1699999999ABCD1234",
  "bank_code": "BIDV",
  "expires_at": "2024-11-15T10:30:00Z",
  "payment_id": null,
  "provider_payment_id": null,
  "balance_before": null,
  "balance_after": null,
  "completed_at": null,
  "message": "Topup status: processing"
}
```

**Response mẫu (hoàn thành):**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "TOPUP1699999999ABCD1234",
  "amount": 100000,
  "status": "succeeded",
  "is_expired": false,
  "payment_id": "456e7890-e89b-12d3-a456-426614174000",
  "provider_payment_id": "123456789",
  "balance_before": 0,
  "balance_after": 100000,
  "completed_at": "2024-11-15T09:35:00Z",
  "message": "Topup status: succeeded"
}
```

**Tests:**
```javascript
pm.test("Get topup status", function() {
    pm.response.to.have.status(200);
    const status = pm.response.json();
    console.log("💰 Status:", status.status);
    console.log("💵 Amount:", status.amount);

    if (status.status === "succeeded") {
        console.log("✅ Payment completed!");
        console.log("💰 Balance: " + status.balance_before + " → " + status.balance_after);
    }
});
```

---

### 📌 Request 5: Mock Webhook để test (Development only)

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/webhook/`

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "id": 123456789,
  "gateway": "BIDV",
  "transactionDate": "2024-11-15 09:35:00",
  "accountNumber": "96247CISI1",
  "subAccount": "",
  "code": "VCB",
  "content": "TOPUP1699999999ABCD1234",
  "transferType": "in",
  "transferAmount": 100000,
  "referenceCode": "FT24315123456",
  "description": "Transfer",
  "accumulated": 0
}
```

**⚠️ Quan trọng:** Thay `content` bằng `order_code` từ Request 3

**Response:**
```json
{
  "status": "success",
  "message": "OK",
  "payment_id": "456e7890-e89b-12d3-a456-426614174000",
  "processed_at": "2024-11-15T09:35:00Z"
}
```

**Tests:**
```javascript
pm.test("Webhook processed", function() {
    pm.response.to.have.status(200);
    const result = pm.response.json();
    pm.expect(result.status).to.eql("success");
    console.log("✅ Webhook processed:", result.message);
});
```

**Sau khi chạy webhook → Chạy lại Request 2 để xem balance đã tăng!**

---

## 5. TEST SYMBOL PURCHASE

### 📌 Request 6: Tạo đơn mua Symbol (Wallet)

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/symbol/orders/`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30,
      "metadata": {"note": "Test purchase"},
      "auto_renew": false,
      "auto_renew_price": null,
      "auto_renew_cycle_days": null
    }
  ],
  "payment_method": "wallet",
  "description": "Mua bot VN30 - Test"
}
```

**Response (thành công - đủ tiền):**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 50000.00,
  "status": "paid",
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30,
      "symbol_name": "VN30 Trading Bot",
      "metadata": {"note": "Test purchase"},
      "auto_renew": false,
      "auto_renew_price": null,
      "auto_renew_cycle_days": null
    }
  ],
  "created_at": "2024-11-15T09:40:00Z",
  "message": "Order processed successfully.",
  "payment_intent_id": null,
  "qr_code_url": null,
  "deep_link": null
}
```

**Response (thiếu tiền - trả về đơn pending):**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 50000.00,
  "status": "pending_payment",
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30,
      "symbol_name": "VN30 Trading Bot",
      "metadata": {},
      "auto_renew": false
    }
  ],
  "created_at": "2024-11-15T09:40:00Z",
  "message": "Số dư ví không đủ. Thiếu 30,000 VND. Vui lòng chọn thanh toán bằng SePay.",
  "payment_intent_id": null,
  "qr_code_url": null,
  "deep_link": null,
  "insufficient_balance": true,
  "wallet_balance": 20000,
  "shortage": 30000
}
```

**🎯 Frontend xử lý khi insufficient_balance = true:**
- Hiển thị modal/dialog với thông báo thiếu tiền
- Nút **Hủy đơn**: DELETE order hoặc để pending
- Nút **Thanh toán ngay**: Gọi `POST /symbol/order/{order_id}/pay-sepay` để lấy QR code

**Tests:**
```javascript
pm.test("Order created", function() {
    pm.response.to.have.status(200);
    const response = pm.response.json();

    pm.expect(response).to.have.property("order_id");
    pm.collectionVariables.set("order_id", response.order_id);

    console.log("✅ Order ID:", response.order_id);
    console.log("📊 Status:", response.status);
    console.log("💰 Total amount:", response.total_amount);

    if (response.insufficient_balance) {
        console.log("⚠️  Insufficient balance!");
        console.log("💵 Wallet balance:", response.wallet_balance);
        console.log("❌ Shortage:", response.shortage);
        console.log("💡 Next: Call /symbol/order/{order_id}/pay-sepay to get QR code");
    } else {
        console.log("✅ Order paid successfully!");
    }
});
```

---

### 📌 Request 7: Tạo đơn mua Symbol (SePay Transfer)

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/symbol/orders/`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30,
      "metadata": {},
      "auto_renew": false
    }
  ],
  "payment_method": "sepay_transfer",
  "description": "Mua bằng SePay"
}
```

**Response:**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 50000.00,
  "status": "pending_payment",
  "payment_method": "sepay_transfer",
  "items": [...],
  "created_at": "2024-11-15T09:40:00Z",
  "message": "Order created successfully. Complete payment via SePay.",
  "payment_intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "qr_code_url": "https://qr.sepay.vn/...",
  "deep_link": "https://sepay.vn/payment?..."
}
```

**Tests:**
```javascript
pm.test("Order created with SePay", function() {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    pm.collectionVariables.set("order_id", response.order_id);
    console.log("✅ Order ID:", response.order_id);
    console.log("📱 QR Code:", response.qr_code_url);
});
```

---

### 📌 Request 8: Thanh toán ngay khi thiếu tiền (Nút "Thanh toán ngay")

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/symbol/order/{{order_id}}/pay-sepay`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Mô tả:**
- API này dùng khi user ấn nút **"Thanh toán ngay"** sau khi tạo đơn wallet nhưng thiếu tiền
- Tạo payment intent SePay để thanh toán **toàn bộ số tiền đơn hàng** (không phải chỉ phần thiếu)
- User quét QR → Thanh toán → Webhook → Order chuyển sang paid → Tạo license

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "amount": 50000,
  "currency": "VND",
  "expires_at": "2024-11-15T10:40:00Z",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=50000&des=PAY_A1B2C3D4_1699999999&template=compact",
  "message": "Payment intent created successfully."
}
```

**Tests:**
```javascript
pm.test("Payment intent created", function() {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    console.log("✅ Intent ID:", response.intent_id);
    console.log("📱 QR Code:", response.qr_code_url);
    console.log("💰 Amount to pay:", response.amount);
    console.log("📝 Order code:", response.order_code);
});
```

---

### 📌 Request 8b: Top-up số tiền thiếu vào ví (Alternative)

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/symbol/order/{{order_id}}/topup-sepay`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Mô tả:**
- API này nạp **chỉ số tiền còn thiếu** vào ví
- Sau khi nạp xong → Tự động trừ tiền ví để thanh toán đơn

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "amount": 30000,
  "currency": "VND",
  "expires_at": "2024-11-15T10:40:00Z",
  "qr_code_url": "https://qr.sepay.vn/...",
  "message": "Create a SePay top-up for 30,000 VND to finish the order."
}
```

---

### 📌 Request 9: Thanh toán đơn bằng ví

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/symbol/order/{{order_id}}/pay-wallet`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Response:**
```json
{
  "success": true,
  "message": "Payment processed successfully",
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "amount_charged": 50000,
  "wallet_balance_after": 50000,
  "licenses_created": 1,
  "subscriptions_updated": 0
}
```

**Tests:**
```javascript
pm.test("Payment successful", function() {
    pm.response.to.have.status(200);
    const result = pm.response.json();
    pm.expect(result.success).to.be.true;
    console.log("✅ Payment successful!");
    console.log("💰 Balance after:", result.wallet_balance_after);
    console.log("🎫 Licenses created:", result.licenses_created);
});
```

---

### 📌 Request 10: Lịch sử đơn hàng

**Method:** `GET`
**URL:** `{{base_url}}/api/seapay/symbol/orders/history/?page=1&limit=10&status=paid`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Query Parameters:**
- `page`: 1
- `limit`: 10
- `status`: paid (hoặc pending_payment, failed, cancelled)

**Response:**
```json
{
  "results": [
    {
      "order_id": "789e0123-e89b-12d3-a456-426614174000",
      "total_amount": 50000,
      "status": "paid",
      "payment_method": "wallet",
      "description": "Mua bot VN30",
      "items": [
        {
          "symbol_id": 1,
          "symbol_name": "VN30 Trading Bot",
          "price": 50000,
          "license_days": 30,
          "metadata": {}
        }
      ],
      "created_at": "2024-11-15T09:40:00Z",
      "updated_at": "2024-11-15T09:40:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 10,
  "total_pages": 1
}
```

---

## 6. TEST LICENSE MANAGEMENT

### 📌 Request 11: Kiểm tra quyền truy cập Symbol

**Method:** `GET`
**URL:** `{{base_url}}/api/seapay/symbol/{{symbol_id}}/access`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Response (có quyền):**
```json
{
  "has_access": true,
  "license_id": "abc12345-e89b-12d3-a456-426614174000",
  "start_at": "2024-11-15T09:40:00Z",
  "end_at": "2024-12-15T09:40:00Z",
  "is_lifetime": false,
  "expires_soon": false
}
```

**Response (không có quyền):**
```json
{
  "has_access": false,
  "reason": "No active license found"
}
```

**Tests:**
```javascript
pm.test("Check access", function() {
    pm.response.to.have.status(200);
    const access = pm.response.json();

    if (access.has_access) {
        console.log("✅ Has access to symbol");
        console.log("🎫 License ID:", access.license_id);
        console.log("📅 Valid until:", access.end_at || "Lifetime");
    } else {
        console.log("❌ No access:", access.reason);
    }
});
```

---

### 📌 Request 12: Danh sách license của user

**Method:** `GET`
**URL:** `{{base_url}}/api/seapay/symbol/licenses?page=1&limit=20`

**Headers:**
```
Authorization: Bearer {{jwt_token}}
```

**Response:**
```json
[
  {
    "license_id": "abc12345-e89b-12d3-a456-426614174000",
    "symbol_id": 1,
    "status": "active",
    "start_at": "2024-11-15T09:40:00Z",
    "end_at": "2024-12-15T09:40:00Z",
    "is_lifetime": false,
    "is_active": true,
    "order_id": "789e0123-e89b-12d3-a456-426614174000",
    "created_at": "2024-11-15T09:40:00Z"
  },
  {
    "license_id": "def67890-e89b-12d3-a456-426614174000",
    "symbol_id": 2,
    "status": "active",
    "start_at": "2024-11-01T00:00:00Z",
    "end_at": null,
    "is_lifetime": true,
    "is_active": true,
    "order_id": "111e2222-e89b-12d3-a456-426614174000",
    "created_at": "2024-11-01T00:00:00Z"
  }
]
```

---

## 7. TEST WEBHOOK

### 📌 Request 13: Test Webhook với order_code khác nhau

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/webhook/`

**Headers:**
```
Content-Type: application/json
```

**Test Case 1: Wallet Topup**
```json
{
  "id": 123456789,
  "gateway": "BIDV",
  "transactionDate": "2024-11-15 09:35:00",
  "accountNumber": "96247CISI1",
  "content": "TOPUP1699999999ABCD1234",
  "transferType": "in",
  "transferAmount": 100000,
  "referenceCode": "FT24315123456"
}
```

**Test Case 2: Symbol Purchase Payment**
```json
{
  "id": 987654321,
  "gateway": "BIDV",
  "transactionDate": "2024-11-15 09:40:00",
  "accountNumber": "96247CISI1",
  "content": "PAY_A1B2C3D4_1699999999",
  "transferType": "in",
  "transferAmount": 50000,
  "referenceCode": "FT24315123457"
}
```

---

### 📌 Request 14: Fallback Callback (Legacy)

**Method:** `POST`
**URL:** `{{base_url}}/api/seapay/callback`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "content": "PAY_A1B2C3D4_1699999999",
  "transferAmount": 50000,
  "transferType": "in",
  "referenceCode": "FT24315123456"
}
```

---

## 8. AUTOMATION SCRIPTS

### 8.1. Collection Pre-request Script

Thêm vào Collection level (Settings → Pre-request Scripts):

```javascript
// Auto add Authorization header if token exists
const token = pm.collectionVariables.get("jwt_token");
if (token && !pm.request.url.includes("/login")) {
    pm.request.headers.add({
        key: "Authorization",
        value: `Bearer ${token}`
    });
}

// Log request details
console.log("📤 Request:", pm.request.method, pm.request.url.toString());
```

### 8.2. Collection Tests Script

Thêm vào Collection level (Settings → Tests):

```javascript
// Log response status
console.log("📥 Response:", pm.response.code, pm.response.status);

// Pretty print response if JSON
if (pm.response.headers.get("Content-Type").includes("application/json")) {
    try {
        const response = pm.response.json();
        console.log("📦 Response body:", JSON.stringify(response, null, 2));
    } catch(e) {
        console.log("⚠️  Could not parse JSON");
    }
}

// Check for errors
if (pm.response.code >= 400) {
    console.log("❌ Error response:", pm.response.text());
}
```

### 8.3. Individual Request Scripts

**Login Request - Tests:**
```javascript
pm.test("Login successful", function() {
    pm.response.to.have.status(200);
});

pm.test("Save JWT token", function() {
    const response = pm.response.json();
    pm.expect(response).to.have.property("access_token");
    pm.collectionVariables.set("jwt_token", response.access_token);
    console.log("✅ Token saved");
});
```

**Create Topup - Tests:**
```javascript
pm.test("Topup created", function() {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    pm.collectionVariables.set("intent_id", response.intent_id);
    console.log("✅ Intent ID:", response.intent_id);
    console.log("💬 Transfer content:", response.transfer_content);
});
```

**Create Order - Tests:**
```javascript
pm.test("Order created", function() {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    pm.collectionVariables.set("order_id", response.order_id);
    console.log("✅ Order ID:", response.order_id);
    console.log("📊 Status:", response.status);
});
```

---

## 9. TEST SCENARIOS

### 9.1. Scenario 1: Complete Wallet Topup Flow

**Bước 1:** Login → Lưu token
**Bước 2:** Get Wallet → Check balance = 0
**Bước 3:** Create Topup → Lưu intent_id
**Bước 4:** Mock Webhook → Send payment
**Bước 5:** Check Topup Status → Verify succeeded
**Bước 6:** Get Wallet → Check balance tăng

**Runner Settings:**
- Iterations: 1
- Delay: 500ms giữa các request

---

### 9.2. Scenario 2: Purchase Symbol with Wallet

**Bước 1:** Login
**Bước 2:** Create Topup 200000 VND
**Bước 3:** Mock Webhook
**Bước 4:** Check Wallet → Balance = 200000
**Bước 5:** Create Symbol Order (wallet, 50000) → Success
**Bước 6:** Check Wallet → Balance = 150000
**Bước 7:** Check Symbol Access → has_access = true
**Bước 8:** Get Licenses → Verify license created

---

### 9.3. Scenario 3: Purchase with Insufficient Balance

**Bước 1:** Login
**Bước 2:** Get Wallet → Balance = 20000
**Bước 3:** Create Order 50000 → Error "Insufficient balance"
**Bước 4:** Topup for Order → Get QR code
**Bước 5:** Mock Webhook
**Bước 6:** Check wallet → Auto payment → Order paid

---

### 9.4. Scenario 4: SePay Transfer Purchase

**Bước 1:** Login
**Bước 2:** Create Order (sepay_transfer) → Get QR
**Bước 3:** Mock Webhook with order_code
**Bước 4:** Check Order History → Status = paid
**Bước 5:** Check Access → has_access = true

---

## 10. POSTMAN RUNNER

### 10.1. Chạy toàn bộ Collection

1. Click Collection → **Run**
2. Chọn requests cần chạy
3. Set **Delay**: 500ms
4. Click **Run SeaPay API**

### 10.2. Xuất kết quả

1. Sau khi chạy → Click **Export Results**
2. Format: JSON
3. Lưu file để share với team

### 10.3. CI/CD Integration (Newman)

```bash
# Install Newman
npm install -g newman

# Export Collection từ Postman
# Export Environment từ Postman

# Run tests
newman run SeaPay_API.postman_collection.json \
  -e Local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export results.json
```

---

## 11. TROUBLESHOOTING POSTMAN

### 11.1. Lỗi thường gặp

**❌ Error: "Unauthorized"**
```
Nguyên nhân: Token hết hạn hoặc chưa login
Giải pháp: Chạy lại Login request
```

**❌ Error: "intent_id is not defined"**
```
Nguyên nhân: Chưa lưu intent_id từ request trước
Giải pháp: Kiểm tra Tests script đã save biến chưa
```

**❌ Error: "Connection refused"**
```
Nguyên nhân: Server không chạy
Giải pháp: python manage.py runserver
```

### 11.2. Debug Tips

1. **Console Log:** View → Show Postman Console (Ctrl+Alt+C)
2. **Variables:** Hover vào `{{variable}}` để xem giá trị
3. **Request History:** Sidebar → History
4. **Response Time:** Tab Statistics trong response

---

## 12. EXPORT/IMPORT COLLECTION

### Export Collection
1. Collection → 3 dots → Export
2. Chọn Collection v2.1
3. Save file: `SeaPay_API.postman_collection.json`

### Import Collection
1. Import → Upload file
2. Hoặc drag & drop file vào Postman

### Share với team
1. Collection → Share
2. Hoặc export file gửi qua Slack/Email
3. Include Environment file nếu cần

---

## 📚 TÀI LIỆU THAM KHẢO

- [Postman Documentation](https://learning.postman.com/)
- [Newman CLI](https://github.com/postmanlabs/newman)
- [SeaPay API Docs](http://localhost:8000/api/docs)
- [SeaPay README](./README.md)

---

**Phiên bản**: 1.0.0
**Cập nhật**: 2024-11-15
**Tác giả**: Development Team

🎯 **Happy Testing!**
