# HƯỚNG DẪN HỆ THỐNG SEAPAY - THANH TOÁN & QUẢN LÝ VÍ

## 📋 MỤC LỤC
1. [Tổng quan](#1-tổng-quan)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Models - Cấu trúc dữ liệu](#3-models---cấu-trúc-dữ-liệu)
4. [API Endpoints](#4-api-endpoints)
5. [Luồng xử lý nghiệp vụ](#5-luồng-xử-lý-nghiệp-vụ)
6. [Hướng dẫn Test với Postman](#6-hướng-dẫn-test-với-postman)
7. [Webhook & Callback](#7-webhook--callback)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. TỔNG QUAN

Hệ thống **SeaPay** là một module thanh toán tích hợp với cổng thanh toán **SePay**, hỗ trợ:
- ✅ Nạp tiền vào ví điện tử (Wallet Top-up)
- ✅ Thanh toán mua quyền truy cập Symbol (Bot/Trading Signal)
- ✅ Quản lý ví người dùng với Ledger (Sổ cái)
- ✅ Webhook xử lý tự động từ SePay
- ✅ QR Code thanh toán qua ngân hàng
- ✅ Tự động gia hạn license (Auto-renew)

### Công nghệ sử dụng
- **Backend**: Django + Django Ninja (REST API)
- **Payment Gateway**: SePay (VietQR)
- **Database**: PostgreSQL (với UUID primary keys)
- **Authentication**: JWT Token

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1. Cấu trúc thư mục
```
apps/seapay/
├── api.py                          # API endpoints (Router)
├── models.py                       # Database models
├── schemas.py                      # Request/Response schemas
├── repositories/
│   ├── __init__.py
│   └── payment_repository.py       # Data access layer
├── services/
│   ├── __init__.py
│   ├── payment_service.py          # Payment business logic
│   ├── wallet_service.py           # Wallet operations
│   ├── wallet_topup_service.py     # Topup workflows
│   ├── sepay_client.py             # SePay API client
│   └── symbol_purchase_service.py  # Symbol purchase logic
└── utils/
    └── signature.py                # Signature verification
```

### 2.2. Kiến trúc 3 tầng (Layered Architecture)
```
┌─────────────────────────────────────┐
│    API Layer (api.py)              │  ← Nhận request, trả response
├─────────────────────────────────────┤
│    Service Layer (services/)        │  ← Business logic, workflows
├─────────────────────────────────────┤
│    Repository Layer (repositories/) │  ← Database operations
├─────────────────────────────────────┤
│    Models Layer (models.py)         │  ← ORM, Database schema
└─────────────────────────────────────┘
```

---

## 3. MODELS - CẤU TRÚC DỮ LIỆU

### 3.1. PayWallet - Ví điện tử
```python
PayWallet
├── id: UUID (Primary Key)
├── user: ForeignKey(User)
├── balance: Decimal(18,2)      # Số dư hiện tại
├── currency: VARCHAR(10)       # VND/USD
├── status: VARCHAR(20)         # active/suspended
├── created_at, updated_at
```

### 3.2. PayPaymentIntent - Yêu cầu thanh toán
```python
PayPaymentIntent
├── intent_id: UUID (Primary Key)
├── user: ForeignKey(User)
├── order: ForeignKey(PaySymbolOrder, nullable)
├── purpose: VARCHAR(20)        # wallet_topup/order_payment/symbol_purchase
├── amount: Decimal(18,2)
├── status: VARCHAR(30)         # requires_payment_method/processing/succeeded/failed
├── order_code: VARCHAR(255) UNIQUE  # Nội dung chuyển khoản
├── reference_code: VARCHAR(255)     # Mã tham chiếu từ ngân hàng
├── qr_code_url: TEXT           # Link QR code
├── deep_link: TEXT             # Deep link mobile
├── expires_at: DateTime        # Thời hạn thanh toán
├── metadata: JSONField
├── created_at, updated_at
```

### 3.3. PayPaymentAttempt - Lần thử thanh toán
```python
PayPaymentAttempt
├── attempt_id: UUID (Primary Key)
├── intent: ForeignKey(PayPaymentIntent)
├── status: VARCHAR(30)
├── bank_code: VARCHAR(10)          # BIDV/VCB/MB...
├── account_number: VARCHAR(50)     # STK nhận tiền
├── account_name: VARCHAR(255)      # Tên TK
├── transfer_content: TEXT          # Nội dung CK
├── transfer_amount: Decimal(18,2)
├── qr_image_url: TEXT              # URL ảnh QR
├── qr_svg: TEXT                    # SVG QR code
├── expires_at: DateTime
├── metadata: JSONField
```

### 3.4. PayPayment - Thanh toán
```python
PayPayment
├── payment_id: UUID (Primary Key)
├── user: ForeignKey(User)
├── order: ForeignKey(PaySymbolOrder, nullable)
├── intent: ForeignKey(PayPaymentIntent, nullable)
├── amount: Decimal(18,2)
├── status: VARCHAR(30)
├── provider_payment_id: VARCHAR(255)  # ID giao dịch SePay
├── message: TEXT
├── metadata: JSONField
```

### 3.5. PayWalletLedger - Sổ cái ví
```python
PayWalletLedger
├── ledger_id: UUID (Primary Key)
├── wallet: ForeignKey(PayWallet)
├── tx_type: VARCHAR(20)        # deposit/purchase/refund/withdrawal
├── amount: Decimal(18,2)       # Luôn dương
├── is_credit: Boolean          # true=cộng, false=trừ
├── balance_before: Decimal(18,2)
├── balance_after: Decimal(18,2)
├── order: ForeignKey(PaySymbolOrder, nullable)
├── payment: ForeignKey(PayPayment, nullable)
├── note: TEXT
├── metadata: JSONField
├── created_at
```

### 3.6. PaySymbolOrder - Đơn hàng mua Symbol
```python
PaySymbolOrder
├── order_id: UUID (Primary Key)
├── user: ForeignKey(User)
├── total_amount: Decimal(18,2)
├── status: VARCHAR(20)         # pending_payment/paid/failed/cancelled
├── payment_method: VARCHAR(20) # wallet/sepay_transfer
├── description: TEXT
├── payment_intent: ForeignKey(PayPaymentIntent, nullable)
├── created_at, updated_at
```

### 3.7. PaySymbolOrderItem - Chi tiết đơn hàng
```python
PaySymbolOrderItem
├── order_item_id: UUID (Primary Key)
├── order: ForeignKey(PaySymbolOrder)
├── symbol_id: BigInteger       # ID của Symbol
├── price: Decimal(18,2)
├── license_days: Integer       # Số ngày license (null=lifetime)
├── auto_renew: Boolean         # Tự động gia hạn
├── auto_renew_price: Decimal(18,2)
├── cycle_days_override: Integer
├── metadata: JSONField
```

### 3.8. PayUserSymbolLicense - License người dùng
```python
PayUserSymbolLicense
├── license_id: UUID (Primary Key)
├── user: ForeignKey(User)
├── symbol_id: BigInteger
├── order: ForeignKey(PaySymbolOrder, nullable)
├── subscription: ForeignKey(SymbolAutoRenewSubscription, nullable)
├── status: VARCHAR(20)         # active/expired/suspended/revoked
├── start_at: DateTime
├── end_at: DateTime            # null = lifetime
├── created_at
```

### 3.9. PayBankTransaction - Giao dịch ngân hàng
```python
PayBankTransaction
├── sepay_tx_id: BigInteger (Primary Key)
├── transaction_date: DateTime
├── account_number: VARCHAR(50)
├── amount_in: Decimal(20,2)
├── amount_out: Decimal(20,2)
├── content: TEXT              # Nội dung CK (chứa order_code)
├── reference_number: VARCHAR(100)
├── bank_code: VARCHAR(10)
├── intent: ForeignKey(PayPaymentIntent, nullable)
├── attempt: ForeignKey(PayPaymentAttempt, nullable)
├── payment: ForeignKey(PayPayment, nullable)
```

### 3.10. PaySepayWebhookEvent - Webhook từ SePay
```python
PaySepayWebhookEvent
├── webhook_event_id: UUID (Primary Key)
├── sepay_tx_id: BigInteger UNIQUE
├── received_at: DateTime
├── payload: JSONField          # Lưu nguyên webhook payload
├── processed: Boolean
├── process_error: TEXT
```

---

## 4. API ENDPOINTS

### 4.1. Payment Intent APIs

#### **POST** `/api/seapay/create-intent`
Tạo payment intent mới

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Request Body:**
```json
{
  "purpose": "wallet_topup",
  "amount": 100000,
  "currency": "VND",
  "expires_in_minutes": 60,
  "return_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel",
  "metadata": {}
}
```

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=100000&des=PAY_A1B2C3D4_1699999999&template=compact",
  "transfer_content": "PAY_A1B2C3D4_1699999999",
  "amount": 100000,
  "status": "requires_payment_method",
  "expires_at": "2024-11-15T10:30:00Z"
}
```

#### **GET** `/api/seapay/intent/{intent_id}`
Lấy chi tiết payment intent

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "amount": 100000.0,
  "status": "succeeded",
  "purpose": "wallet_topup",
  "expires_at": "2024-11-15T10:30:00Z",
  "is_expired": false,
  "created_at": "2024-11-15T09:30:00Z",
  "updated_at": "2024-11-15T09:35:00Z"
}
```

---

### 4.2. Wallet APIs

#### **GET** `/api/seapay/wallet/`
Lấy thông tin ví

**Response:**
```json
{
  "wallet_id": "123e4567-e89b-12d3-a456-426614174000",
  "balance": 500000.0,
  "currency": "VND",
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-11-15T09:35:00Z"
}
```

---

### 4.3. Wallet Top-up APIs

#### **POST** `/api/seapay/wallet/topup/`
Tạo yêu cầu nạp tiền vào ví

**Request Body:**
```json
{
  "amount": 100000,
  "currency": "VND",
  "bank_code": "BIDV",
  "expires_in_minutes": 60
}
```

**Response:**
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

#### **GET** `/api/seapay/wallet/topup/{intent_id}/status`
Kiểm tra trạng thái nạp tiền

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "TOPUP1699999999ABCD1234",
  "amount": 100000,
  "status": "succeeded",
  "is_expired": false,
  "qr_image_url": "https://qr.sepay.vn/...",
  "account_number": "96247CISI1",
  "account_name": "BIDV Account",
  "transfer_content": "TOPUP1699999999ABCD1234",
  "bank_code": "BIDV",
  "expires_at": "2024-11-15T10:30:00Z",
  "payment_id": "456e7890-e89b-12d3-a456-426614174000",
  "provider_payment_id": "123456789",
  "balance_before": 400000,
  "balance_after": 500000,
  "completed_at": "2024-11-15T09:35:00Z",
  "message": "Topup status: succeeded"
}
```

---

### 4.4. Symbol Purchase APIs

#### **POST** `/api/seapay/symbol/orders/`
Tạo đơn hàng mua Symbol

**Request Body:**
```json
{
  "items": [
    {
      "symbol_id": 1,
      "price": 200000,
      "license_days": 30,
      "metadata": {},
      "auto_renew": false,
      "auto_renew_price": null,
      "auto_renew_cycle_days": null
    }
  ],
  "payment_method": "wallet",
  "description": "Mua bot trading VN30"
}
```

**Response (Wallet - đủ tiền):**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 200000.00,
  "status": "paid",
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 1,
      "price": 200000,
      "license_days": 30,
      "symbol_name": "VN30 Trading Bot",
      "metadata": {},
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

**Response (Wallet - Thiếu tiền):**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 200000.00,
  "status": "pending_payment",
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 1,
      "price": 200000,
      "license_days": 30,
      "symbol_name": "VN30 Trading Bot",
      "metadata": {},
      "auto_renew": false
    }
  ],
  "created_at": "2024-11-15T09:40:00Z",
  "message": "Số dư ví không đủ. Thiếu 150,000 VND. Vui lòng chọn thanh toán bằng SePay.",
  "payment_intent_id": null,
  "qr_code_url": null,
  "deep_link": null,
  "insufficient_balance": true,
  "wallet_balance": 50000,
  "shortage": 150000
}
```

**🎯 Xử lý Frontend khi `insufficient_balance = true`:**

1. **Hiển thị Dialog/Modal** với thông tin:
   - Số dư hiện tại: `wallet_balance`
   - Cần thanh toán: `total_amount`
   - Thiếu: `shortage`

2. **Hai nút lựa chọn:**
   - **Nút "Hủy"**: Đóng dialog, giữ order ở trạng thái `pending_payment`
   - **Nút "Thanh toán ngay"**: Gọi `POST /api/seapay/symbol/order/{order_id}/pay-sepay` → Nhận QR code SePay

**Response (SePay Transfer):**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 200000.00,
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

#### **GET** `/api/seapay/symbol/orders/history/`
Lịch sử đơn hàng

**Query Params:**
- `page`: int (default: 1)
- `limit`: int (default: 20, max: 100)
- `status`: string (optional: pending_payment/paid/failed/cancelled)

**Response:**
```json
{
  "results": [
    {
      "order_id": "789e0123-e89b-12d3-a456-426614174000",
      "total_amount": 200000,
      "status": "paid",
      "payment_method": "wallet",
      "description": "Mua bot trading VN30",
      "items": [...],
      "created_at": "2024-11-15T09:40:00Z",
      "updated_at": "2024-11-15T09:40:00Z"
    }
  ],
  "total": 10,
  "page": 1,
  "limit": 20,
  "total_pages": 1
}
```

#### **POST** `/api/seapay/symbol/order/{order_id}/pay-wallet`
Thanh toán đơn hàng bằng ví

**Response:**
```json
{
  "success": true,
  "message": "Payment processed successfully",
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "amount_charged": 200000,
  "wallet_balance_after": 300000,
  "licenses_created": 1,
  "subscriptions_updated": 0
}
```

#### **POST** `/api/seapay/symbol/order/{order_id}/pay-sepay`
⭐ **API cho nút "Thanh toán ngay"** - Tạo payment intent SePay thanh toán trực tiếp đơn hàng

**Use case:**
- User tạo đơn wallet nhưng thiếu tiền → Response có `insufficient_balance: true`
- Frontend hiển thị nút **"Thanh toán ngay"**
- User click → Gọi API này → Nhận QR code SePay
- Thanh toán **toàn bộ số tiền đơn hàng** (không phải chỉ phần thiếu)

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "amount": 200000,
  "currency": "VND",
  "expires_at": "2024-11-15T10:40:00Z",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=200000&des=PAY_A1B2C3D4_1699999999&template=compact",
  "message": "Payment intent created successfully."
}
```

**Luồng xử lý:**
```
User quét QR → Chuyển khoản 200,000 VND
→ Webhook → Order chuyển sang "paid"
→ Tạo license ngay lập tức
```

#### **POST** `/api/seapay/symbol/order/{order_id}/topup-sepay`
💰 **API alternative** - Tạo top-up ví với số tiền còn thiếu

**Use case:**
- User muốn nạp tiền vào ví trước, sau đó tự động thanh toán đơn
- Chỉ nạp **số tiền còn thiếu** (không phải toàn bộ đơn hàng)
- Sau khi nạp xong → Hệ thống tự động trừ tiền ví

**Response:**
```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1699999999",
  "amount": 150000,
  "currency": "VND",
  "expires_at": "2024-11-15T10:40:00Z",
  "qr_code_url": "https://qr.sepay.vn/...",
  "message": "Create a SePay top-up for 150,000 VND to finish the order."
}
```

**Luồng xử lý:**
```
User quét QR → Nạp 150,000 vào ví
→ Webhook → Wallet balance tăng
→ Tự động trừ tiền thanh toán đơn
→ Order chuyển "paid" → Tạo license
```

**📊 So sánh:**
| | `/pay-sepay` | `/topup-sepay` |
|---|---|---|
| **Mục đích** | Thanh toán trực tiếp đơn hàng | Nạp ví rồi auto thanh toán |
| **Số tiền QR** | Toàn bộ đơn (200k) | Chỉ phần thiếu (150k) |
| **Tiền đi đâu** | Trực tiếp thanh toán | Vào ví → Trừ ví |
| **Nên dùng khi** | User cần thanh toán nhanh | User muốn nạp ví dùng lâu dài |
```

---

### 4.5. License APIs

#### **GET** `/api/seapay/symbol/{symbol_id}/access`
Kiểm tra quyền truy cập Symbol

**Response:**
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

#### **GET** `/api/seapay/symbol/licenses`
Danh sách license của user

**Query Params:**
- `page`: int (default: 1)
- `limit`: int (default: 20)

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
  }
]
```

---

### 4.6. Payment History API

#### **GET** `/api/seapay/payments/user`
Lịch sử thanh toán

**Query Params:**
- `page`: int (default: 1)
- `limit`: int (default: 10)
- `search`: string (optional)
- `status`: string (default: succeeded)
- `purpose`: string (optional)

**Response:**
```json
{
  "total": 15,
  "page": 1,
  "page_size": 10,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "date_joined": "2024-01-01T00:00:00Z"
  },
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "order_code": "PAY_A1B2C3D4_1699999999",
      "reference_code": "FT24315123456",
      "amount": 100000,
      "status": "succeeded",
      "purpose": "wallet_topup",
      "provider": "sepay",
      "created_at": "2024-11-15T09:35:00Z",
      "user_id": 1
    }
  ]
}
```

---

## 5. LUỒNG XỬ LÝ NGHIỆP VỤ

### 5.1. Luồng Nạp Ví (Wallet Top-up)

```
1. User tạo yêu cầu top-up
   POST /api/seapay/wallet/topup/
   └→ WalletTopupService.create_topup_intent()
      └→ Tạo PayPaymentIntent (purpose=wallet_topup)
      └→ Generate order_code: TOPUP{timestamp}{random}

2. Tạo Payment Attempt & QR Code
   └→ WalletTopupService.create_payment_attempt()
      └→ SepayClient.create_qr_code()
      └→ Tạo PayPaymentAttempt với QR code URL

3. User quét QR và chuyển khoản
   └→ Ngân hàng → SePay → Webhook

4. Xử lý Webhook
   POST /api/seapay/webhook/
   └→ PaymentService.process_sepay_webhook()
      └→ Lưu PaySepayWebhookEvent
      └→ Match order_code → PayPaymentIntent
      └→ Validate amount
      └→ Tạo PayPayment (status=succeeded)

5. Cập nhật Wallet
   └→ WalletTopupService.finalize_topup()
      └→ Tạo PayWalletLedger (tx_type=deposit, is_credit=true)
      └→ Cập nhật PayWallet.balance

6. Polling status (optional)
   GET /api/seapay/wallet/topup/{intent_id}/status
```

### 5.2. Luồng Mua Symbol bằng Ví

```
1. User tạo đơn hàng
   POST /api/seapay/symbol/orders/
   payment_method: "wallet"
   └→ SymbolPurchaseService.create_symbol_order()
      └→ Tạo PaySymbolOrder (status=pending_payment)
      └→ Tạo PaySymbolOrderItem cho từng item

2. Kiểm tra số dư ví
   └→ if balance >= total_amount:
      └→ _process_immediate_wallet_payment()
         └→ Tạo PayWalletLedger (tx_type=purchase, is_credit=false)
         └→ Trừ tiền ví
         └→ Update order.status = paid
         └→ Tạo PayUserSymbolLicense

   └→ else:
      └→ Raise ValueError("Insufficient balance")
```

### 5.3. Luồng Mua Symbol bằng SePay

```
1. User tạo đơn hàng
   POST /api/seapay/symbol/orders/
   payment_method: "sepay_transfer"
   └→ Tạo PaySymbolOrder
   └→ Tạo PayPaymentIntent (purpose=symbol_purchase)
   └→ Trả về QR code cho user

2. User thanh toán → Webhook
   POST /api/seapay/webhook/
   └→ PaymentService.process_sepay_webhook()
      └→ Match order_code → Intent
      └→ Tạo PayPayment
      └→ _process_symbol_order_payment()
         └→ Update order.status = paid
         └→ Tạo PayUserSymbolLicense
```

### 5.4. Luồng Mua Symbol khi thiếu tiền - LUỒNG HOÀN CHỈNH

#### 📌 Tổng quan logic

Khi user chọn thanh toán bằng **Wallet** nhưng số dư không đủ, hệ thống thực hiện:

1. ✅ **KHÔNG** raise error như trước (không trả về HTTP 400)
2. ✅ Tạo đơn hàng với status = `pending_payment`
3. ✅ Trả về response đặc biệt với flag `insufficient_balance: true`
4. ✅ Frontend nhận được response → Hiển thị dialog cho user lựa chọn
5. ✅ User có 2 lựa chọn xử lý (xem bên dưới)

---

#### 🔍 Chi tiết luồng xử lý Backend

**File:** [symbol_purchase_service.py:119-137](apps/seapay/services/symbol_purchase_service.py#L119-L137)

```python
if payment_method == PaymentMethod.WALLET:
    wallet = PayWallet.objects.filter(user=user).first()
    if not wallet:
        raise ValueError("User wallet not found")

    # Đủ tiền → Thanh toán ngay lập tức
    if wallet.balance >= total_amount:
        return self._process_immediate_wallet_payment(order, wallet)

    # ⚠️ KHÔNG ĐỦ TIỀN → Trả về dict thông báo (KHÔNG raise error)
    shortage = total_amount - wallet.balance
    return {
        "order": order,                       # Đơn đã tạo (status: pending_payment)
        "insufficient_balance": True,         # Flag để Frontend check
        "wallet_balance": wallet.balance,     # Số dư hiện tại
        "total_amount": total_amount,         # Tổng tiền đơn hàng
        "shortage": shortage,                 # Số tiền còn thiếu
        "message": f"Số dư ví không đủ. Thiếu {shortage:,.0f} VND. Vui lòng chọn thanh toán bằng SePay."
    }
```

**Kết quả:**
- Đơn hàng đã được tạo trong database với `status = "pending_payment"`
- Order items đã được lưu đầy đủ
- User có thể quay lại thanh toán sau

---

#### 📱 Response API khi thiếu tiền

**Endpoint:** `POST /api/seapay/symbol/orders/`

**Request:**
```json
{
  "items": [
    {
      "symbol_id": 1,
      "price": 200000,
      "license_days": 30
    }
  ],
  "payment_method": "wallet",
  "description": "Mua bot VN30"
}
```

**Response khi thiếu tiền:**
```json
{
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "total_amount": 200000.00,
  "status": "pending_payment",                      // ← Đơn đang chờ thanh toán
  "payment_method": "wallet",
  "items": [
    {
      "symbol_id": 1,
      "price": 200000,
      "license_days": 30,
      "symbol_name": "VN30 Trading Bot"
    }
  ],
  "created_at": "2025-10-06T10:00:00Z",
  "message": "Số dư ví không đủ. Thiếu 150,000 VND. Vui lòng chọn thanh toán bằng SePay.",

  // 🔑 Fields đặc biệt để Frontend xử lý
  "insufficient_balance": true,                     // ← Kiểm tra flag này!
  "wallet_balance": 50000,                          // Số dư hiện tại
  "shortage": 150000,                               // Còn thiếu bao nhiêu

  "payment_intent_id": null,                        // Chưa có intent
  "qr_code_url": null,                              // Chưa có QR
  "deep_link": null
}
```

---

#### 🎯 LỰA CHỌN 1: Thanh toán trực tiếp bằng SePay (Khuyến nghị)

**Use case:** User muốn thanh toán ngay lập tức toàn bộ đơn hàng qua SePay

**Luồng:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  BƯỚC 1: User tạo đơn với payment_method = "wallet"                │
│  POST /api/seapay/symbol/orders/                                    │
│  → Backend check: balance (50k) < total (200k)                      │
│  → Trả về: insufficient_balance = true                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BƯỚC 2: Frontend hiển thị Dialog                                   │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  ⚠️  Số dư ví không đủ                                   │      │
│  │                                                           │      │
│  │  Số dư hiện tại:  50,000 VND                             │      │
│  │  Cần thanh toán: 200,000 VND                             │      │
│  │  Còn thiếu:      150,000 VND                             │      │
│  │                                                           │      │
│  │  ┌─────────┐          ┌──────────────────────┐          │      │
│  │  │   Hủy   │          │  Thanh toán ngay ✓   │          │      │
│  │  └─────────┘          └──────────────────────┘          │      │
│  └──────────────────────────────────────────────────────────┘      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
        ┌────────────────────┴─────────────────────┐
        │                                          │
    User Hủy                            User click "Thanh toán ngay"
        │                                          │
        ▼                                          ▼
  Đóng dialog                     ┌─────────────────────────────────────┐
  Giữ order                       │  BƯỚC 3: Gọi API thanh toán         │
  pending_payment                 │  POST /api/seapay/symbol/order/     │
                                  │       {order_id}/pay-sepay          │
                                  │                                     │
                                  │  Backend:                           │
                                  │  1. Tạo PayPaymentIntent            │
                                  │     purpose = "order_payment"       │
                                  │     amount = 200,000 (toàn bộ đơn)  │
                                  │  2. Update order.payment_intent     │
                                  │  3. Trả về QR code SePay            │
                                  └────────────┬────────────────────────┘
                                               │
                                               ▼
                                  ┌─────────────────────────────────────┐
                                  │  BƯỚC 4: Hiển thị QR code           │
                                  │  - User quét QR                     │
                                  │  - Chuyển khoản 200,000 VND         │
                                  │  - Nội dung CK: PAY_xxx_timestamp   │
                                  └────────────┬────────────────────────┘
                                               │
                                               ▼
                                  ┌─────────────────────────────────────┐
                                  │  BƯỚC 5: Webhook từ SePay           │
                                  │  POST /api/seapay/webhook/          │
                                  │                                     │
                                  │  Backend xử lý:                     │
                                  │  1. Match order_code → Intent       │
                                  │  2. Tạo PayPayment (succeeded)      │
                                  │  3. Intent → Order (qua order field)│
                                  │  4. Update order.status = "paid"    │
                                  │  5. Tạo PayUserSymbolLicense        │
                                  │  6. Kích hoạt auto-renew (nếu có)  │
                                  └────────────┬────────────────────────┘
                                               │
                                               ▼
                                  ┌─────────────────────────────────────┐
                                  │  ✅ HOÀN THÀNH                       │
                                  │  - User nhận license ngay lập tức   │
                                  │  - Có thể truy cập Symbol           │
                                  └─────────────────────────────────────┘
```

**API Call:**

```http
POST /api/seapay/symbol/order/{order_id}/pay-sepay
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "intent_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_code": "PAY_A1B2C3D4_1728216000",
  "amount": 200000,                              // ← Toàn bộ đơn hàng
  "currency": "VND",
  "expires_at": "2025-10-06T11:00:00Z",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=200000&des=PAY_A1B2C3D4_1728216000",
  "message": "Payment intent created successfully."
}
```

**✅ Ưu điểm:**
- Đơn giản nhất cho user
- Thanh toán 1 lần → Nhận license ngay
- Không cần quản lý số dư ví
- Xử lý webhook trực tiếp → order paid

**❌ Nhược điểm:**
- Phải trả toàn bộ tiền đơn (không chỉ phần thiếu)
- Tiền không vào ví (không dùng được cho đơn sau)

---

#### 💰 LỰA CHỌN 2: Top-up ví rồi tự động thanh toán

**Use case:** User muốn nạp tiền vào ví, sau đó hệ thống tự động trừ tiền thanh toán đơn

**Luồng:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  BƯỚC 1-2: Giống lựa chọn 1 (Dialog hiển thị)                      │
│  Nhưng user click nút khác: "Nạp tiền vào ví" (nếu có)             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                ┌─────────────────────────────────────┐
                │  BƯỚC 3: Gọi API topup              │
                │  POST /api/seapay/symbol/order/     │
                │       {order_id}/topup-sepay        │
                │                                     │
                │  Backend:                           │
                │  1. Tính shortage = 200k - 50k      │
                │                   = 150,000 VND     │
                │  2. Tạo PayPaymentIntent            │
                │     purpose = "wallet_topup"        │
                │     amount = 150,000 (chỉ phần thiếu)│
                │     metadata.order_id = order_id    │ ← Liên kết đơn
                │  3. Trả về QR code                  │
                └────────────┬────────────────────────┘
                             │
                             ▼
                ┌─────────────────────────────────────┐
                │  BƯỚC 4: User quét QR, CK 150k      │
                └────────────┬────────────────────────┘
                             │
                             ▼
                ┌─────────────────────────────────────────────────────────┐
                │  BƯỚC 5: Webhook từ SePay                               │
                │  POST /api/seapay/webhook/                              │
                │                                                         │
                │  Backend xử lý:                                         │
                │  1. Match order_code → Intent (purpose=wallet_topup)    │
                │  2. Ghi ledger: deposit +150k                          │
                │  3. Wallet: 50k → 200k                                 │
                │  4. Check metadata.order_id → Tìm thấy đơn hàng!      │
                │  5. Gọi _process_topup_and_auto_payment()              │
                │     a. Check wallet.balance >= order.total_amount      │
                │     b. Ghi ledger: purchase -200k                      │
                │     c. Wallet: 200k → 0k                               │
                │     d. Update order.status = "paid"                    │
                │     e. Tạo PayUserSymbolLicense                        │
                └────────────┬────────────────────────────────────────────┘
                             │
                             ▼
                ┌─────────────────────────────────────┐
                │  ✅ HOÀN THÀNH                       │
                │  - Ví đã nạp +150k                  │
                │  - Đơn tự động thanh toán -200k     │
                │  - User nhận license                │
                │  - Ví còn 0 VND                     │
                └─────────────────────────────────────┘
```

**API Call:**

```http
POST /api/seapay/symbol/order/{order_id}/topup-sepay
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "intent_id": "456e7890-e89b-12d3-a456-426614174000",
  "order_code": "TOPUP1728216000ABCD1234",
  "amount": 150000,                              // ← Chỉ phần thiếu
  "currency": "VND",
  "expires_at": "2025-10-06T11:00:00Z",
  "qr_code_url": "https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount=150000&des=TOPUP1728216000ABCD1234",
  "message": "Create a SePay top-up for 150,000 VND to finish the order."
}
```

**Code xử lý webhook:**

```python
# File: apps/seapay/services/symbol_purchase_service.py:360-401

@transaction.atomic
def _process_topup_and_auto_payment(self, payment, order_id: str):
    """Xử lý sau khi top-up thành công, tự động thanh toán đơn"""
    order = PaySymbolOrder.objects.select_for_update().get(order_id=order_id)
    wallet = PayWallet.objects.select_for_update().get(user=order.user)

    # Check lại số dư sau khi nạp
    if wallet.balance < order.total_amount:
        return {"success": False, "message": "Wallet balance still insufficient after top-up."}

    # Tự động trừ tiền ví
    ledger_entry = PayWalletLedger.objects.create(
        wallet=wallet,
        tx_type=WalletTxType.PURCHASE,
        amount=order.total_amount,
        is_credit=False,                       # Trừ tiền
        balance_before=wallet.balance,
        balance_after=wallet.balance - order.total_amount,
        order_id=order.order_id,
        note=f"Auto-payment after top-up for order {order.order_id}",
    )
    wallet.balance = ledger_entry.balance_after
    wallet.save()

    # Cập nhật order → paid
    order.status = OrderStatus.PAID
    order.save()

    # Tạo license
    licenses_created = self._create_symbol_licenses(order)

    return {"success": True, "message": "Top-up completed and order paid"}
```

**✅ Ưu điểm:**
- Chỉ nạp số tiền còn thiếu (tiết kiệm nếu đã có một phần)
- Tiền vào ví → Có thể dùng cho lần mua sau
- Logic rõ ràng: Nạp ví → Trừ ví

**❌ Nhược điểm:**
- Phức tạp hơn (2 bước: nạp + trừ)
- Nhiều transaction hơn
- Nếu có lỗi giữa chừng, cần xử lý rollback

---

#### 📊 So sánh 2 lựa chọn

| Tiêu chí | Thanh toán trực tiếp (`/pay-sepay`) | Top-up ví (`/topup-sepay`) |
|----------|-------------------------------------|----------------------------|
| **Số tiền QR** | Toàn bộ đơn hàng (200k) | Chỉ phần thiếu (150k) |
| **Tiền đi đâu** | Trực tiếp thanh toán đơn (không vào ví) | Nạp vào ví → Tự động trừ ví |
| **Wallet Ledger** | Không tạo (không dùng ví) | Tạo 2 records: +150k (deposit), -200k (purchase) |
| **Độ phức tạp** | Đơn giản (1 bước) | Phức tạp (2 bước: nạp + trừ) |
| **Purpose Intent** | `order_payment` | `wallet_topup` với metadata.order_id |
| **Use case** | Thanh toán nhanh, không quan tâm số dư ví | Muốn duy trì số dư ví cho sau này |
| **Webhook xử lý** | `process_sepay_payment_completion()` | `_process_topup_and_auto_payment()` |
| **Khuyến nghị** | ⭐ Dùng cho hầu hết trường hợp | Dùng khi user thường xuyên mua |

---

#### 🔧 Code Implementation

**File chính:** [symbol_purchase_service.py](apps/seapay/services/symbol_purchase_service.py)

**Các methods quan trọng:**

1. **`create_symbol_order()`** (line 38-140)
   - Tạo đơn hàng
   - Check wallet balance
   - Return dict với `insufficient_balance: true` nếu thiếu tiền

2. **`create_sepay_payment_intent()`** (line 287-321)
   - API endpoint: `/symbol/order/{id}/pay-sepay`
   - Purpose: `ORDER_PAYMENT`
   - Amount: Toàn bộ đơn hàng

3. **`create_sepay_topup_for_insufficient_order()`** (line 194-238)
   - API endpoint: `/symbol/order/{id}/topup-sepay`
   - Purpose: `WALLET_TOPUP`
   - Amount: Chỉ phần thiếu
   - metadata.order_id: Link đến order

4. **`_process_topup_and_auto_payment()`** (line 360-401)
   - Tự động xử lý sau khi top-up xong
   - Trừ tiền ví
   - Chuyển order → paid
   - Tạo license

---

#### ⚠️ Lưu ý quan trọng

1. **Đơn hàng luôn được tạo:** Dù thiếu tiền hay không, order vẫn được lưu vào DB với status `pending_payment`

2. **Không mất dữ liệu:** User có thể quay lại thanh toán sau, hoặc admin có thể check order pending

3. **Frontend PHẢI check flag:** `insufficient_balance === true` để hiển thị UI phù hợp

4. **Order có thể thanh toán nhiều lần:** Nếu user không thanh toán, có thể gọi lại `/pay-sepay` để tạo intent mới

5. **Expire handling:** Payment intent có thời gian hết hạn (mặc định 60 phút). Sau đó user phải tạo intent mới.

6. **Idempotency:** Webhook xử lý idempotent bằng `sepay_tx_id` để tránh xử lý trùng

---

## 6. HƯỚNG DẪN TEST VỚI POSTMAN

### 6.1. Chuẩn bị

#### Bước 1: Tạo Collection trong Postman
1. Mở Postman
2. New Collection → Đặt tên "SeaPay API"
3. Variables → Thêm:
   - `base_url`: `http://localhost:8000`
   - `jwt_token`: (để trống, sẽ update sau)

#### Bước 2: Lấy JWT Token
**Request: Login**
```
POST {{base_url}}/api/auth/login
Content-Type: application/json

Body:
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "..."
}
```

→ Copy `access_token` → Set vào Collection Variables `jwt_token`

---

### 6.2. Test Nạp Ví (Wallet Top-up)

#### Test 1: Tạo yêu cầu nạp tiền
```
POST {{base_url}}/api/seapay/wallet/topup/
Authorization: Bearer {{jwt_token}}
Content-Type: application/json

Body:
{
  "amount": 100000,
  "currency": "VND",
  "bank_code": "BIDV",
  "expires_in_minutes": 60
}
```

**Kết quả mong đợi:**
- Status: 200 OK
- Response có `qr_code_url`, `order_code`, `intent_id`
- Lưu `intent_id` để test tiếp

#### Test 2: Kiểm tra trạng thái top-up
```
GET {{base_url}}/api/seapay/wallet/topup/{{intent_id}}/status
Authorization: Bearer {{jwt_token}}
```

**Kết quả:**
- Status pending: `"status": "processing"`
- Sau khi webhook: `"status": "succeeded"`

#### Test 3: Xem số dư ví
```
GET {{base_url}}/api/seapay/wallet/
Authorization: Bearer {{jwt_token}}
```

**Kết quả:**
```json
{
  "wallet_id": "...",
  "balance": 100000.0,
  "currency": "VND",
  "status": "active"
}
```

---

### 6.3. Test Mua Symbol

#### Test 4: Tạo đơn mua symbol bằng ví
```
POST {{base_url}}/api/seapay/symbol/orders/
Authorization: Bearer {{jwt_token}}
Content-Type: application/json

Body:
{
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30,
      "metadata": {"note": "Test purchase"},
      "auto_renew": false
    }
  ],
  "payment_method": "wallet",
  "description": "Mua bot test"
}
```

**Kết quả khi đủ tiền:**
- `"status": "paid"`
- `"message": "Order processed successfully."`

**Kết quả khi thiếu tiền:**
- Status: 400
- Error: "Insufficient wallet balance. You need X more VND..."

#### Test 5: Top-up khi thiếu tiền
```
POST {{base_url}}/api/seapay/symbol/order/{{order_id}}/topup-sepay
Authorization: Bearer {{jwt_token}}
```

**Kết quả:**
- QR code để top-up số tiền còn thiếu
- `"amount"`: số tiền cần nạp thêm

#### Test 6: Tạo đơn SePay Transfer
```
POST {{base_url}}/api/seapay/symbol/orders/
Authorization: Bearer {{jwt_token}}
Content-Type: application/json

Body:
{
  "items": [
    {
      "symbol_id": 1,
      "price": 50000,
      "license_days": 30
    }
  ],
  "payment_method": "sepay_transfer",
  "description": "Mua bằng SePay"
}
```

**Kết quả:**
- `"status": "pending_payment"`
- `"qr_code_url"`: Link QR thanh toán
- `"payment_intent_id"`: ID intent

#### Test 7: Lịch sử đơn hàng
```
GET {{base_url}}/api/seapay/symbol/orders/history/?page=1&limit=10&status=paid
Authorization: Bearer {{jwt_token}}
```

---

### 6.4. Test License

#### Test 8: Kiểm tra quyền truy cập Symbol
```
GET {{base_url}}/api/seapay/symbol/1/access
Authorization: Bearer {{jwt_token}}
```

**Kết quả có license:**
```json
{
  "has_access": true,
  "license_id": "...",
  "start_at": "2024-11-15T09:40:00Z",
  "end_at": "2024-12-15T09:40:00Z",
  "is_lifetime": false,
  "expires_soon": false
}
```

#### Test 9: Danh sách license
```
GET {{base_url}}/api/seapay/symbol/licenses?page=1&limit=20
Authorization: Bearer {{jwt_token}}
```

---

### 6.5. Test Payment Intent

#### Test 10: Tạo payment intent
```
POST {{base_url}}/api/seapay/create-intent
Authorization: Bearer {{jwt_token}}
Content-Type: application/json

Body:
{
  "purpose": "wallet_topup",
  "amount": 200000,
  "currency": "VND",
  "expires_in_minutes": 60
}
```

#### Test 11: Lấy chi tiết intent
```
GET {{base_url}}/api/seapay/intent/{{intent_id}}
Authorization: Bearer {{jwt_token}}
```

#### Test 12: Lịch sử thanh toán
```
GET {{base_url}}/api/seapay/payments/user?page=1&limit=10&status=succeeded
Authorization: Bearer {{jwt_token}}
```

---

### 6.6. Test Webhook (Mock SePay)

#### Test 13: Gửi webhook callback
```
POST {{base_url}}/api/seapay/webhook/
Content-Type: application/json

Body:
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

**Kết quả:**
```json
{
  "status": "success",
  "message": "OK",
  "payment_id": "...",
  "processed_at": "2024-11-15T09:35:00Z"
}
```

#### Test 14: Fallback callback
```
POST {{base_url}}/api/seapay/callback
Content-Type: application/json

Body:
{
  "content": "PAY_A1B2C3D4_1699999999",
  "transferAmount": 100000,
  "transferType": "in",
  "referenceCode": "FT24315123456"
}
```

---

### 6.7. Postman Scripts (Automation)

#### Pre-request Script (Auto set token)
```javascript
// Collection level
const token = pm.collectionVariables.get("jwt_token");
if (token) {
    pm.request.headers.add({
        key: "Authorization",
        value: `Bearer ${token}`
    });
}
```

#### Tests Script (Auto save intent_id)
```javascript
// Cho request POST /wallet/topup/
pm.test("Status is 200", function() {
    pm.response.to.have.status(200);
});

pm.test("Response has intent_id", function() {
    const response = pm.response.json();
    pm.expect(response).to.have.property("intent_id");
    pm.collectionVariables.set("intent_id", response.intent_id);
});
```

---

## 7. WEBHOOK & CALLBACK

### 7.1. Cấu hình SePay Webhook

**Webhook URL:** `https://yourdomain.com/api/seapay/webhook/`

**Payload mẫu từ SePay:**
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

### 7.2. Xử lý Webhook

```python
# apps/seapay/api.py
@router.post("/webhook/", response=SepayWebhookResponse)
def sepay_webhook(request: HttpRequest, payload: SepayWebhookRequest):
    result = payment_service.process_sepay_webhook(payload.dict())
    status = "success" if result.get("success") else "error"
    return SepayWebhookResponse(
        status=status,
        message=result.get("message", ""),
        payment_id=result.get("payment_id"),
        processed_at=timezone.now().isoformat(),
    )
```

### 7.3. Logic xử lý

1. **Lưu webhook event** → `PaySepayWebhookEvent` (idempotent bằng `sepay_tx_id`)
2. **Parse content** → Tìm `PayPaymentIntent` bằng `order_code`
3. **Validate amount** → So sánh `transferAmount` với `intent.amount`
4. **Tạo Payment** → `PayPayment` (status=succeeded)
5. **Xử lý theo purpose:**
   - `wallet_topup` → Ghi `PayWalletLedger`, cộng tiền ví
   - `order_payment` → Chuyển order sang `paid`, tạo license

### 7.4. Idempotency

- Webhook events được lưu với `sepay_tx_id` UNIQUE
- Nếu trùng → Skip xử lý, trả về success
- Intent đã `succeeded` → Không xử lý lại

---

## 8. TROUBLESHOOTING

### 8.1. Lỗi thường gặp

#### Lỗi: "Payment intent not found"
```
Nguyên nhân: order_code không khớp
Giải pháp:
- Kiểm tra content chuyển khoản chính xác
- Không có khoảng trắng, ký tự đặc biệt
- SePay có thể bỏ dấu "_" → Hệ thống có logic reformat
```

#### Lỗi: "Amount mismatch"
```
Nguyên nhân: Số tiền chuyển khoản ≠ intent.amount
Giải pháp:
- Chuyển chính xác số tiền trong QR
- Không làm tròn/thay đổi số tiền
```

#### Lỗi: "Insufficient balance"
```
Nguyên nhân: Ví không đủ tiền
Giải pháp:
- Nạp tiền trước: POST /wallet/topup/
- Hoặc dùng: POST /symbol/order/{id}/topup-sepay
```

#### Lỗi: "Wallet is suspended"
```
Nguyên nhân: Ví bị khóa
Giải pháp:
- Admin cập nhật wallet.status = 'active'
```

### 8.2. Debug Webhook

#### Kiểm tra webhook đã nhận chưa:
```sql
SELECT * FROM pay_sepay_webhook_events
WHERE sepay_tx_id = 123456789;
```

#### Kiểm tra lỗi xử lý:
```sql
SELECT process_error FROM pay_sepay_webhook_events
WHERE processed = false;
```

#### Test webhook local với ngrok:
```bash
ngrok http 8000
# Copy URL: https://abc123.ngrok.io
# Cấu hình SePay webhook: https://abc123.ngrok.io/api/seapay/webhook/
```

### 8.3. Kiểm tra Ledger

#### Xem lịch sử giao dịch ví:
```sql
SELECT
  ledger_id, tx_type, amount, is_credit,
  balance_before, balance_after, created_at
FROM pay_wallet_ledger
WHERE wallet_id = '<wallet_uuid>'
ORDER BY created_at DESC;
```

#### Validate balance:
```python
# Balance phải = tổng ledger
expected_balance = sum(
    entry.amount if entry.is_credit else -entry.amount
    for entry in wallet.ledger_entries.all()
)
assert wallet.balance == expected_balance
```

### 8.4. Test Environment Variables

```python
# settings.py hoặc .env
SEPAY_BASE_URL = "https://api.sepay.vn"
SEPAY_API_KEY = "your_api_key_here"
SEPAY_ACCOUNT_NUMBER = "96247CISI1"
```

### 8.5. Logs quan trọng

```python
# Check logs
import logging
logger = logging.getLogger('apps.seapay')

# Logs webhook
logger.info(f"Received webhook: {payload}")

# Logs payment
logger.info(f"Payment {payment_id} succeeded for intent {intent_id}")

# Logs ledger
logger.info(f"Wallet {wallet_id} credited with {amount}")
```

---

## 9. BẢO MẬT & BEST PRACTICES

### 9.1. Security Checklist
- ✅ Validate webhook signature (nếu SePay hỗ trợ)
- ✅ Idempotent webhook processing (dùng `sepay_tx_id`)
- ✅ Transaction atomic cho wallet operations
- ✅ Validate amount mismatch
- ✅ Expire payment intents sau thời gian quy định
- ✅ JWT authentication cho tất cả endpoints

### 9.2. Database Best Practices
- ✅ UUID cho tất cả primary keys
- ✅ Index trên các cột search (user, order_code, status)
- ✅ Unique constraint trên order_code, sepay_tx_id
- ✅ JSON metadata cho flexibility

### 9.3. Code Conventions
- ✅ Service layer xử lý business logic
- ✅ Repository layer cho database ops
- ✅ Schema validation với Ninja schemas
- ✅ Exception handling rõ ràng

---

## 10. MAINTENANCE

### 10.1. Cronjobs cần chạy

#### Expire old payment intents:
```python
# Chạy mỗi 5 phút
def expire_old_intents():
    expired = PayPaymentIntent.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=[PaymentStatus.REQUIRES_PAYMENT_METHOD, PaymentStatus.PROCESSING]
    )
    for intent in expired:
        intent.expire()
```

#### Expire old licenses:
```python
# Chạy mỗi ngày
def expire_old_licenses():
    expired = PayUserSymbolLicense.objects.filter(
        end_at__lt=timezone.now(),
        status=LicenseStatus.ACTIVE
    )
    expired.update(status=LicenseStatus.EXPIRED)
```

### 10.2. Monitoring

- Monitor webhook failures: `pay_sepay_webhook_events.processed = false`
- Monitor wallet balance consistency
- Monitor payment success rate
- Monitor API response times

---

## 11. LIÊN HỆ & HỖ TRỢ

- **Documentation**: Xem file này
- **API Spec**: `/api/docs` (Swagger UI)
- **Issues**: GitHub Issues hoặc team chat

---

**Phiên bản**: 1.0.0
**Cập nhật lần cuối**: 2024-11-15
**Tác giả**: Development Team
