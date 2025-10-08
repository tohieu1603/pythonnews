# Togogo Analysis - Stock Analysis API

Dự án phân tích chứng khoán sử dụng Django + Django Ninja với cơ sở dữ liệu PostgreSQL.

## 📋 Mục lục
.\cloudflared.exe --config C:\Users\ADMIN\.cloudflared\config_payment.yaml tunnel run
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [🧪 Hướng dẫn Test API với Postman](#hướng-dẫn-test-api-với-postman)
  - [Thiết lập môi trường](#thiết-lập-môi-trường)
  - [Authentication](#authentication)
  - [Luồng 1: Payment Intent & Wallet](#luồng-1-payment-intent--wallet)
  - [Luồng 2: Wallet Topup với SePay](#luồng-2-wallet-topup-với-sepay)
  - [Luồng 3: Mua Symbol với Wallet](#luồng-3-mua-symbol-với-wallet)gunicorn config.wsgi:application
```

---

# 🧪 Hướng dẫn Test API với Postman

## Thiết lập môi trường

### 1. Cài đặt và chạy server

```bash
# Kích hoạt virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Chạy migrations
python manage.py migrate

# Tạo superuser (nếu chưa có)
python manage.py createsuperuser

# Chạy server
python manage.py runserver
```

Server sẽ chạy tại: `http://localhost:8000`

### 2. Tạo Postman Environment

Trong Postman, tạo Environment mới với tên `PyNews Local` và các biến sau:

| Variable | Initial Value | Current Value |
|----------|---------------|---------------|
| `base_url` | `http://localhost:8000` | `http://localhost:8000` |
| `access_token` | | (sẽ được tự động cập nhật) |
| `user_email` | `admin@example.com` | `admin@example.com` |
| `user_password` | `admin123` | `admin123` |
| `order_id` | | (sẽ được lưu từ response) |
| `payment_intent_id` | | (sẽ được lưu từ response) |

## Authentication

### 🔑 Đăng nhập và lấy token

**Request:**
```http
POST {{base_url}}/api/auth/login
Content-Type: application/json

{
  "email": "{{user_email}}",
  "password": "{{user_password}}"
}
```

**Response mẫu:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User"
  }
}
```

**Postman Test Script (thêm vào tab Tests):**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.environment.set("access_token", response.access_token);
    console.log("✅ Token saved to environment");
}

pm.test("Login successful", function () {
    pm.response.to.have.status(200);
    pm.expect(pm.response.json()).to.have.property("access_token");
});
```

## Luồng 1: Payment Intent & Wallet

### 1.1 Kiểm tra thông tin ví

**Request:**
```http
GET {{base_url}}/api/sepay/wallet
Authorization: Bearer {{access_token}}
```

**Response mẫu:**
```json
{
  "wallet_id": "123e4567-e89b-12d3-a456-426614174000",
  "balance": 1000000.0,
  "currency": "VND",
  "status": "active",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

### 1.2 Tạo Payment Intent

**Request:**
```http
POST {{base_url}}/api/sepay/create-intent
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "purpose": "test_payment",
  "amount": 50000,
  "currency": "VND",
  "expires_in_minutes": 30,
  "return_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel",
  "metadata": {
    "test": true,
    "user_id": "{{user_id}}"
  }
}
```

**Response mẫu:**
```json
{
  "intent_id": "8d82f801-9646-4904-b1ce-4480254216a7",
  "order_code": "PAY_416ADF59_1758594862",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=50000&des=PAY_416ADF59_1758594862&template=compact",
  "transfer_content": "PAY_416ADF59_1758594862",
  "amount": 50000,
  "status": "pending",
  "expires_at": "2025-01-01T01:00:00Z"
}
```

**Postman Test Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.environment.set("payment_intent_id", response.intent_id);
    pm.environment.set("order_code", response.order_code);
    console.log("✅ Payment intent created: " + response.intent_id);
}

pm.test("Payment intent created successfully", function () {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    pm.expect(response).to.have.property("intent_id");
    pm.expect(response).to.have.property("qr_code_url");
    pm.expect(response.status).to.equal("pending");
});
```

### 1.3 Kiểm tra trạng thái Payment Intent

**Request:**
```http
GET {{base_url}}/api/sepay/intent/{{payment_intent_id}}
Authorization: Bearer {{access_token}}
```

## Luồng 2: Wallet Topup với SePay

### 2.1 Tạo yêu cầu nạp tiền

**Request:**
```http
POST {{base_url}}/api/sepay/wallet/topup/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "amount": 100000,
  "currency": "VND",
  "bank_code": "BIDV",
  "expires_in_minutes": 30
}
```

**Response mẫu:**
```json
{
  "intent_id": "topup-12345",
  "order_code": "TOPUP_789123_456",
  "amount": 100000,
  "currency": "VND",
  "status": "pending",
  "qr_image_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=100000&des=TOPUP_789123_456&template=compact",
  "account_number": "96247CISI1",
  "account_name": "PHAM VAN A",
  "transfer_content": "TOPUP_789123_456",
  "bank_code": "BIDV",
  "expires_at": "2025-01-01T01:00:00Z",
  "message": "Topup request created successfully. Please scan QR code to complete payment."
}
```

### 2.2 Kiểm tra trạng thái nạp tiền

**Request:**
```http
GET {{base_url}}/api/sepay/wallet/topup/{{intent_id}}/status
Authorization: Bearer {{access_token}}
```

### 2.3 Mô phỏng SePay Webhook (cho testing)

**Request:**
```http
POST {{base_url}}/api/sepay/wallet/webhook/sepay
Content-Type: application/json

{
  "id": "test_webhook_123",
  "gateway": "BIDV",
  "transactionDate": "2025-01-01 10:00:00",
  "accountNumber": "96247CISI1",
  "subAccount": null,
  "code": "FT25001123456789",
  "content": "TOPUP_789123_456",
  "transferType": "in",
  "description": "Chuyen tien den 96247CISI1",
  "transferAmount": 100000,
  "referenceCode": "FT25001123456789",
  "accumulated": 1000000
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "payment_id": "payment_123",
  "processed_at": "2025-01-01T10:00:00Z"
}
```

## Luồng 3: Mua Symbol với Wallet

### 3.1 Tạo đơn hàng với đủ số dư ví

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 671,
      "price": 50000,
      "license_days": 30,
      "metadata": {
        "symbol_name": "VIC",
        "package": "premium"
      }
    }
  ],
  "payment_method": "wallet",
  "description": "Mua quyền truy cập symbol VIC 30 ngày"
}
```

**Response mẫu (Thanh toán thành công ngay):**
```json
{
  "order_id": "d8269f0c-ff80-4a9e-abe7-e9e29e172dd4",
  "total_amount": 50000,
  "status": "paid",
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 671,
      "price": 50000,
      "license_days": 30,
      "metadata": {
        "symbol_name": "VIC",
        "package": "premium"
      }
    }
  ],
  "created_at": "2025-01-01T10:00:00Z",
  "message": "Order paid successfully with wallet. Balance deducted: 50000 VND"
}
```

**Postman Test Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.environment.set("order_id", response.order_id);
    console.log("✅ Order created: " + response.order_id);
}

pm.test("Wallet payment successful", function () {
    pm.response.to.have.status(200);
    const response = pm.response.json();
    pm.expect(response.payment_method).to.equal("wallet");
    pm.expect(response.status).to.equal("paid");
});
```

### 3.2 Tạo đơn hàng với số dư ví không đủ

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 672,
      "price": 5000000,
      "license_days": 30
    }
  ],
  "payment_method": "wallet",
  "description": "Test insufficient wallet balance"
}
```

**Response mẫu (Pending payment):**
```json
{
  "order_id": "ad822aec-ecc4-4ce3-806f-bf685e393b72",
  "total_amount": 5000000,
  "status": "pending_payment",
  "payment_method": "wallet",
  "items": [...],
  "created_at": "2025-01-01T10:00:00Z",
  "message": "Order created but insufficient wallet balance. Please topup your wallet first."
}
```

### 3.3 Thanh toán pending order bằng ví (sau khi topup)

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/{{order_id}}/pay-wallet
Authorization: Bearer {{access_token}}
```

## Luồng 4: Mua Symbol với SePay

### 4.1 Tạo đơn hàng với SePay payment

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 673,
      "price": 75000,
      "license_days": 30,
      "metadata": {
        "symbol_name": "VNM",
        "package": "standard"
      }
    }
  ],
  "payment_method": "sepay_transfer",
  "description": "Mua quyền truy cập symbol VNM với SePay"
}
```

**Response mẫu (Tự động tạo QR):**
```json
{
  "order_id": "21c5ce33-6eb4-440a-9828-64087ead7017",
  "total_amount": 75000,
  "status": "pending_payment",
  "payment_method": "sepay_transfer",
  "items": [...],
  "created_at": "2025-01-01T10:00:00Z",
  "message": "Order created with SePay payment. Scan QR code to pay 75000 VND",
  "payment_intent_id": "8d82f801-9646-4904-b1ce-4480254216a7",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=75000&des=PAY_416ADF59_1758594862&template=compact",
  "deep_link": "https://sepay.vn/payment?acc=96247CISI1&bank=BIDV&amount=75000&des=PAY_416ADF59_1758594862"
}
```

### 4.2 Tạo SePay payment cho existing order

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/{{order_id}}/pay-sepay
Authorization: Bearer {{access_token}}
```

### 4.3 Tạo topup SePay cho order (khi ví không đủ)

**Request:**
```http
POST {{base_url}}/api/sepay/symbol/order/{{order_id}}/topup-sepay
Authorization: Bearer {{access_token}}
```

## Luồng 5: SePay Webhook Testing

### 5.1 Mô phỏng payment callback thành công

**Request:**
```http
POST {{base_url}}/api/sepay/callback
Content-Type: application/json

{
  "id": "test_payment_123",
  "gateway": "BIDV",
  "transactionDate": "2025-01-01 10:00:00",
  "accountNumber": "96247CISI1",
  "subAccount": null,
  "code": "FT25001987654321",
  "content": "PAY_416ADF59_1758594862",
  "transferType": "in",
  "description": "Chuyen tien thanh toan don hang",
  "transferAmount": 75000,
  "referenceCode": "FT25001987654321"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Payment processed successfully",
  "payment_intent_id": "8d82f801-9646-4904-b1ce-4480254216a7",
  "order_id": "21c5ce33-6eb4-440a-9828-64087ead7017",
  "amount": 75000,
  "processed_at": "2025-01-01T10:00:00Z"
}
```

### 5.2 Kiểm tra order status sau callback

**Request:**
```http
GET {{base_url}}/api/sepay/symbol/orders/history?page=1&limit=10
Authorization: Bearer {{access_token}}
```

**Response sẽ show order status = "paid":**
```json
{
  "results": [
    {
      "order_id": "21c5ce33-6eb4-440a-9828-64087ead7017",
      "total_amount": 75000,
      "status": "paid",
      "payment_method": "sepay_transfer",
      "created_at": "2025-01-01T10:00:00Z",
      "paid_at": "2025-01-01T10:01:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

## Kiểm tra quyền truy cập và licenses

### 6.1 Kiểm tra quyền truy cập symbol

**Request:**
```http
GET {{base_url}}/api/sepay/symbol/671/access
Authorization: Bearer {{access_token}}
```

**Response mẫu:**
```json
{
  "has_access": true,
  "symbol_id": 671,
  "symbol_name": "VIC",
  "license_id": "123e4567-e89b-12d3-a456-426614174000",
  "expires_at": "2025-02-01T10:00:00Z",
  "days_remaining": 30,
  "is_active": true
}
```

### 6.2 Lấy danh sách tất cả licenses

**Request:**
```http
GET {{base_url}}/api/sepay/symbol/licenses?page=1&limit=10
Authorization: Bearer {{access_token}}
```

**Response mẫu:**
```json
[
  {
    "license_id": "123e4567-e89b-12d3-a456-426614174000",
    "symbol_id": 671,
    "symbol_name": "VIC",
    "license_days": 30,
    "expires_at": "2025-02-01T10:00:00Z",
    "is_active": true,
    "created_at": "2025-01-01T10:00:00Z",
    "order_id": "d8269f0c-ff80-4a9e-abe7-e9e29e172dd4"
  }
]
```

## 📋 Postman Collection Template

### Pre-request Script (Collection level)

```javascript
// Auto-refresh token if needed
const token = pm.environment.get("access_token");
if (!token) {
    console.log("🔄 No token found, attempting login...");
    
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/api/auth/login",
        method: 'POST',
        header: {
            'Content-Type': 'application/json',
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                email: pm.environment.get("user_email"),
                password: pm.environment.get("user_password")
            })
        }
    }, function (err, res) {
        if (res && res.code === 200) {
            const token = res.json().access_token;
            pm.environment.set("access_token", token);
            console.log("✅ Auto-login successful");
        } else {
            console.error("❌ Auto-login failed");
        }
    });
}
```

### Test Script Template (cho mỗi request)

```javascript
// Kiểm tra response status
pm.test("Status code is success", function () {
    pm.response.to.have.status(200);
});

// Kiểm tra response structure
pm.test("Response has valid structure", function () {
    const response = pm.response.json();
    pm.expect(response).to.be.an('object');
});

// Log response for debugging
console.log("📋 Response:", pm.response.json());

// Save important data to environment
if (pm.response.code === 200) {
    const response = pm.response.json();
    
    // Save order_id if present
    if (response.order_id) {
        pm.environment.set("order_id", response.order_id);
    }
    
    // Save payment_intent_id if present
    if (response.payment_intent_id) {
        pm.environment.set("payment_intent_id", response.payment_intent_id);
    }
}
```

## 🐛 Troubleshooting

### Lỗi thường gặp:

1. **401 Unauthorized**: Token hết hạn hoặc không hợp lệ
   - Chạy lại request login
   - Kiểm tra biến `access_token` trong environment

2. **404 Not Found**: Order/Symbol không tồn tại
   - Kiểm tra `order_id` hoặc `symbol_id` 
   - Đảm bảo đã tạo order trước khi test

3. **400 Bad Request**: Dữ liệu request không hợp lệ
   - Kiểm tra JSON format
   - Validate required fields

4. **500 Internal Server Error**: Lỗi server
   - Kiểm tra logs server
   - Đảm bảo database đang chạy

### Debug tips:

- Sử dụng Console trong Postman để xem logs
- Kiểm tra tab Tests để xem test results
- Monitor Variables tab để tracking saved data
- Use {{variable}} syntax để reference environment variables

## 📊 Expected Test Results

Sau khi chạy full test suite, bạn sẽ có:

1. ✅ User đã login và có token
2. ✅ Wallet đã được tạo và có số dư
3. ✅ Payment intents đã được tạo thành công
4. ✅ Orders đã được tạo với cả 2 payment methods
5. ✅ Wallet payments processed ngay lập tức (nếu đủ tiền)
6. ✅ SePay QR codes được generate
7. ✅ Webhooks processed và order status updated
8. ✅ Licenses được tạo sau successful payment
9. ✅ User có quyền access các symbols đã mua

Chúc bạn testing thành công! 🚀  - [Luồng 4: Mua Symbol với SePay](#luồng-4-mua-symbol-với-sepay)
  - [Luồng 5: SePay Webhook Testing](#luồng-5-sepay-webhook-testing)

## Cấu trúc dự án

```
TogogoAnalysis/
├── api/                        # API configuration
│   ├── __init__.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── main.py                 # Main API instance
│   ├── middleware.py
│   └── router.py
├── apps/                       # Django apps
│   └── stock/                  # Stock analysis app
│       ├── __init__.py
│       ├── api.py              # Stock API endpoints
│       ├── apps.py             # App configuration
│       ├── filters.py
│       ├── models.py           # Database models
│       ├── schemas.py          # Pydantic schemas
│       ├── services.py         # Business logic
│       ├── utils.py
│       ├── migrations/         # Database migrations
│       └── tests/              # Unit tests
├── config/                     # Django configuration
│   ├── __init__.py
│   ├── asgi.py                 # ASGI configuration
│   ├── urls.py                 # URL routing
│   ├── wsgi.py                 # WSGI configuration
│   └── settings/
│       ├── __init__.py
│       ├── base.py             # Base settings
│       ├── development.py      # Development settings
│       └── production.py       # Production settings
├── core/                       # Core utilities
├── database/                   # Database utilities
├── manage.py                   # Django management script
├── requirement.txt             # Python dependencies
└── .env                        # Environment variables
```

## Yêu cầu hệ thống

- Python 3.8+
- PostgreSQL 12+
- pip

## Cài đặt và cấu hình

### 1. Clone repository

```bash
git clone <repository-url>
cd TogogoAnalysis
```

### 2. Tạo virtual environment (khuyến nghị)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirement.txt
```

### 4. Cấu hình PostgreSQL

#### Cài đặt PostgreSQL:
- Windows: Tải từ https://www.postgresql.org/download/windows/
- Mac: `brew install postgresql`
- Ubuntu: `sudo apt-get install postgresql postgresql-contrib`

#### Tạo database:
```sql
-- Kết nối vào PostgreSQL với user postgres
psql -U postgres

-- Tạo database
CREATE DATABASE hieu;
-- hoặc thay đổi tên database trong file .env

-- Tạo user (tùy chọn)
CREATE USER your_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE hieu TO your_user;
```

### 5. Cấu hình environment variables

Tạo file `.env` trong thư mục root:

```env
DJANGO_SETTINGS_MODULE=config.settings.development

# Database Configuration
DB_NAME=hieu
DB_USER=postgres
DB_PASSWORD=123456789
DB_HOST=localhost
DB_PORT=5432

# Security (cho production)
SECRET_KEY=your-secret-key-here
DEBUG=True
```

**Lưu ý:** Thay đổi các thông số database cho phù hợp với cấu hình PostgreSQL của bạn.

## Database Migration

### 1. Tạo migrations

```bash
# Tạo migrations cho tất cả apps
python manage.py makemigrations

# Tạo migrations cho app cụ thể
python manage.py makemigrations stock
```

### 2. Áp dụng migrations

```bash
# Áp dụng tất cả migrations
python manage.py migrate

# Kiểm tra trạng thái migrations
python manage.py showmigrations
```

### 3. Kiểm tra database connection

```bash
# Kiểm tra cấu hình database
python manage.py check --database default

# Kết nối trực tiếp đến database
python manage.py dbshell
```

## Chạy server

### Development server

```bash
# Chạy development server
python manage.py runserver

# Chạy trên port khác
python manage.py runserver 8080

# Chạy trên IP khác
python manage.py runserver 0.0.0.0:8000
```

Server sẽ chạy tại: http://127.0.0.1:8000/

### API Documentation

- Swagger UI: http://127.0.0.1:8000/api/docs
- OpenAPI Schema: http://127.0.0.1:8000/api/openapi.json

## API Endpoints

### Authentication API

- `POST /api/auth/login` - Đăng nhập
- `POST /api/auth/register` - Đăng ký
- `POST /api/auth/refresh` - Refresh token

### Stock API

- `POST /api/stocks/industries` - Lấy danh sách ngành
- `POST /api/stocks/symbols` - Lấy danh sách mã chứng khoán
- `GET /api/stocks/companies/` - Lấy danh sách công ty
- `POST /api/stocks/companies/` - Tạo công ty mới

### Financial Calculation API

- `GET /api/calculate/incomes/{symbol_id}` - Lấy báo cáo kết quả kinh doanh
- `GET /api/calculate/cash-flows/{symbol_id}` - Lấy báo cáo lưu chuyển tiền tệ
- `GET /api/calculate/balance-sheets/{symbol_id}` - Lấy bảng cân đối kế toán

### Payment & Symbol Purchase API

- `GET /api/sepay/wallet` - Lấy thông tin ví
- `POST /api/sepay/symbol/order/create` - Tạo đơn hàng mua symbol
- `POST /api/sepay/symbol/order/{order_id}/pay-wallet` - Thanh toán bằng ví
- `POST /api/sepay/symbol/order/{order_id}/pay-sepay` - Tạo QR SePay
- `GET /api/sepay/symbol/licenses` - Lấy danh sách license đã mua

## API Testing với Postman

### 1. Setup Environment

Tạo Postman Environment với các biến:

```json
{
  "base_url": "http://localhost:8000",
  "access_token": "",
  "user_email": "test@example.com",
  "user_password": "testpass123"
}
```

### 2. Authentication Flow

#### Login để lấy token
```http
POST {{base_url}}/api/auth/login
Content-Type: application/json

{
  "email": "{{user_email}}",
  "password": "{{user_password}}"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Postman Test Script (lưu token tự động):**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.environment.set("access_token", response.access_token);
}
```

### 3. Symbol Purchase Testing

#### 3.1 Kiểm tra số dư ví
```http
GET {{base_url}}/api/sepay/wallet
Authorization: Bearer {{access_token}}
```

**Response:**
```json
{
  "user_id": 2,
  "balance": 900.0,
  "currency": "VND",
  "status": "active",
  "created_at": "2025-01-01T10:00:00Z"
}
```

#### 3.2 Test Case 1: Wallet Payment (Đủ tiền)
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 671,
      "price": 500,
      "license_days": 30,
      "metadata": {}
    }
  ],
  "payment_method": "wallet",
  "description": "Test wallet payment - sufficient balance"
}
```

**Expected Response (Thanh toán ngay):**
```json
{
  "order_id": "d8269f0c-ff80-4a9e-abe7-e9e29e172dd4",
  "total_amount": 500,
  "status": "paid",
  "payment_method": "wallet",
  "items": [...],
  "created_at": "2025-01-01T10:00:00Z",
  "message": "Order created successfully. Total: 500 VND"
}
```

#### 3.3 Test Case 2: Wallet Payment (Không đủ tiền)
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 671,
      "price": 10000,
      "license_days": 30
    }
  ],
  "payment_method": "wallet",
  "description": "Test wallet payment - insufficient balance"
}
```

**Expected Response (Pending):**
```json
{
  "order_id": "ad822aec-ecc4-4ce3-806f-bf685e393b72",
  "total_amount": 10000,
  "status": "pending_payment",
  "payment_method": "wallet",
  "message": "Order created successfully. Total: 10000 VND"
}
```

#### 3.4 Test Case 3: SePay Payment (Tự động tạo QR)
```http
POST {{base_url}}/api/sepay/symbol/order/create
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "items": [
    {
      "symbol_id": 671,
      "price": 5000,
      "license_days": 30
    }
  ],
  "payment_method": "sepay_transfer",
  "description": "Test SePay payment with auto QR"
}
```

**Expected Response (Pending + QR Code):**
```json
{
  "order_id": "21c5ce33-6eb4-440a-9828-64087ead7017",
  "total_amount": 5000,
  "status": "pending_payment",
  "payment_method": "sepay_transfer",
  "items": [...],
  "created_at": "2025-01-01T10:00:00Z",
  "message": "Order created with SePay payment. Scan QR code to pay 5000 VND",
  "payment_intent_id": "8d82f801-9646-4904-b1ce-4480254216a7",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=5000&des=PAY_416ADF59_1758594862&template=compact",
  "deep_link": "https://sepay.vn/payment?acc=96247CISI1&bank=BIDV&amount=5000&des=PAY_416ADF59_1758594862"
}
```

#### 3.5 Lấy danh sách licenses đã mua
```http
GET {{base_url}}/api/sepay/symbol/licenses?page=1&page_size=10
Authorization: Bearer {{access_token}}
```

**Response:**
```json
{
  "items": [
    {
      "license_id": "123e4567-e89b-12d3-a456-426614174000",
      "symbol_id": 671,
      "symbol_name": "AAA",
      "license_days": 30,
      "expires_at": "2025-02-01T10:00:00Z",
      "is_active": true,
      "created_at": "2025-01-01T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

### 4. Financial Data Testing

#### 4.1 Lấy báo cáo tài chính
```http
GET {{base_url}}/api/calculate/incomes/671
Authorization: Bearer {{access_token}}
```

#### 4.2 Kiểm tra quyền truy cập symbol
```http
GET {{base_url}}/api/sepay/symbol/671/access-check
Authorization: Bearer {{access_token}}
```

**Response:**
```json
{
  "has_access": true,
  "symbol_id": 671,
  "symbol_name": "AAA",
  "license_expires_at": "2025-02-01T10:00:00Z",
  "days_remaining": 30
}
```

### 5. Postman Collection Export

Để import collection vào Postman:

1. Tạo new collection: "Symbol Purchase API"
2. Add các requests trên
3. Setup Pre-request Scripts cho authentication
4. Setup Tests để validate responses

**Pre-request Script (Global):**
```javascript
// Auto-login if token expired
if (!pm.environment.get("access_token")) {
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/api/auth/login",
        method: 'POST',
        header: {
            'Content-Type': 'application/json',
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                email: pm.environment.get("user_email"),
                password: pm.environment.get("user_password")
            })
        }
    }, function (err, res) {
        if (res.code === 200) {
            const token = res.json().access_token;
            pm.environment.set("access_token", token);
        }
    });
}
```

**Test Script Template:**
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has required fields", function () {
    const response = pm.response.json();
    pm.expect(response).to.have.property("order_id");
    pm.expect(response).to.have.property("status");
    pm.expect(response).to.have.property("total_amount");
});

pm.test("Payment method logic works correctly", function () {
    const response = pm.response.json();
    if (response.payment_method === "sepay_transfer") {
        pm.expect(response).to.have.property("qr_code_url");
        pm.expect(response).to.have.property("payment_intent_id");
    }
});
```

## Quản lý dữ liệu

### Tạo superuser

```bash
python manage.py createsuperuser
```

### Django Admin

Truy cập Django Admin tại: http://127.0.0.1:8000/admin/

### Import dữ liệu mẫu

```bash
# Load fixtures (nếu có)
python manage.py loaddata database/fixtures/initial_data.json
```

## Testing

```bash
# Chạy tất cả tests
python manage.py test

# Chạy tests cho app cụ thể
python manage.py test apps.stock

# Chạy với coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

## Troubleshooting

### Lỗi kết nối PostgreSQL

1. **Kiểm tra PostgreSQL service đang chạy:**
   ```bash
   # Windows
   net start postgresql-x64-14
   
   # Linux
   sudo systemctl start postgresql
   sudo systemctl status postgresql
   ```

2. **Kiểm tra thông tin kết nối trong .env**

3. **Test kết nối manually:**
   ```bash
   psql -h localhost -U postgres -d hieu
   ```

### Lỗi migrations

1. **Reset migrations (cẩn thận - sẽ mất dữ liệu):**
   ```bash
   # Xóa migration files
   find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
   find . -path "*/migrations/*.pyc" -delete
   
   # Tạo lại migrations
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Fake migrations:**
   ```bash
   python manage.py migrate --fake-initial
   ```

### Lỗi import modules

1. **Kiểm tra PYTHONPATH:**
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Kiểm tra DJANGO_SETTINGS_MODULE:**
   ```bash
   export DJANGO_SETTINGS_MODULE=config.settings.development
   ```

## Production Deployment

### Environment setup

```env
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
SECRET_KEY=your-very-secure-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=production_db_name
DB_USER=production_user
DB_PASSWORD=secure_password
DB_HOST=your-db-host
DB_PORT=5432
```

### Collect static files

```bash
python manage.py collectstatic
```

### Use production WSGI/ASGI server

```bash
# Gunicorn example
pip install gunicorn
gunicorn config.wsgi:application

# Uvicorn for ASGI
pip install uvicorn
uvicorn config.asgi:application
```

## Đóng góp

1. Fork repository
2. Tạo feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push branch: `git push origin feature/new-feature`
5. Tạo Pull Request

## License

[Thêm thông tin license nếu cần]

## Support

Nếu có vấn đề, vui lòng tạo issue trên GitHub hoặc liên hệ team phát triển.
