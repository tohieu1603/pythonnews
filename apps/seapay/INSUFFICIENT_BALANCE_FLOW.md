# LUỒNG XỬ LÝ KHI THIẾU TIỀN MUA SYMBOL

## 🎯 Tổng quan

Khi user chọn thanh toán bằng **Wallet** nhưng số dư không đủ, hệ thống sẽ:
- ✅ **KHÔNG** raise error
- ✅ Trả về đơn hàng với trạng thái `pending_payment`
- ✅ Kèm thông tin thiếu bao nhiêu tiền
- ✅ Frontend hiển thị 2 nút: **Hủy** và **Thanh toán ngay**

---

## 📱 Flow Frontend

### 1. Tạo đơn hàng (Wallet - Thiếu tiền)

**Request:**
```http
POST /api/seapay/symbol/orders/
Authorization: Bearer {token}
Content-Type: application/json

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
  "total_amount": 200000,
  "status": "pending_payment",
  "payment_method": "wallet",
  "items": [...],
  "created_at": "2024-11-15T09:40:00Z",
  "message": "Số dư ví không đủ. Thiếu 150,000 VND. Vui lòng chọn thanh toán bằng SePay.",

  // 🔑 Key fields để kiểm tra
  "insufficient_balance": true,
  "wallet_balance": 50000,
  "shortage": 150000,

  "payment_intent_id": null,
  "qr_code_url": null,
  "deep_link": null
}
```

---

### 2. Frontend Check Response

```javascript
// React/Vue/Angular example
const createOrder = async (orderData) => {
  const response = await api.post('/api/seapay/symbol/orders/', orderData);

  if (response.insufficient_balance) {
    // Hiển thị modal thiếu tiền
    showInsufficientBalanceModal({
      orderId: response.order_id,
      walletBalance: response.wallet_balance,
      totalAmount: response.total_amount,
      shortage: response.shortage,
      message: response.message
    });
  } else if (response.status === 'paid') {
    // Thanh toán thành công
    showSuccessMessage('Đã mua thành công!');
    navigateToLicenses();
  } else if (response.status === 'pending_payment' && response.payment_method === 'sepay_transfer') {
    // Đơn SePay - hiển thị QR
    showQRCodeModal({
      qrCodeUrl: response.qr_code_url,
      orderCode: response.order_code
    });
  }
};
```

---

### 3. Modal Thiếu Tiền

```jsx
// React component example
function InsufficientBalanceModal({ orderId, walletBalance, totalAmount, shortage, onClose }) {
  const [loading, setLoading] = useState(false);

  const handlePayNow = async () => {
    setLoading(true);
    try {
      // Gọi API thanh toán ngay
      const response = await api.post(`/api/seapay/symbol/order/${orderId}/pay-sepay`);

      // Hiển thị QR code
      showQRCodeModal({
        qrCodeUrl: response.qr_code_url,
        orderCode: response.order_code,
        amount: response.amount,
        expiresAt: response.expires_at
      });

      onClose();
    } catch (error) {
      showError('Không thể tạo thanh toán. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-content">
        <h3>⚠️ Số dư ví không đủ</h3>

        <div className="balance-info">
          <p>Số dư hiện tại: <strong>{formatCurrency(walletBalance)} VND</strong></p>
          <p>Cần thanh toán: <strong>{formatCurrency(totalAmount)} VND</strong></p>
          <p className="shortage">Thiếu: <strong>{formatCurrency(shortage)} VND</strong></p>
        </div>

        <div className="actions">
          <button onClick={onClose} className="btn-cancel">
            Hủy
          </button>
          <button onClick={handlePayNow} disabled={loading} className="btn-primary">
            {loading ? 'Đang xử lý...' : 'Thanh toán ngay'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

### 4. API "Thanh toán ngay"

**Request:**
```http
POST /api/seapay/symbol/order/{order_id}/pay-sepay
Authorization: Bearer {token}
```

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

---

### 5. Hiển thị QR Code

```jsx
function QRCodePaymentModal({ qrCodeUrl, orderCode, amount, expiresAt, onClose }) {
  const [paymentStatus, setPaymentStatus] = useState('pending');
  const [countdown, setCountdown] = useState(null);

  useEffect(() => {
    // Polling để check trạng thái thanh toán
    const intervalId = setInterval(async () => {
      const status = await checkPaymentStatus(orderCode);
      if (status === 'succeeded') {
        setPaymentStatus('succeeded');
        clearInterval(intervalId);
        setTimeout(() => {
          onClose();
          navigateToLicenses();
        }, 2000);
      }
    }, 3000); // Check mỗi 3 giây

    return () => clearInterval(intervalId);
  }, [orderCode]);

  useEffect(() => {
    // Countdown timer
    const expireTime = new Date(expiresAt).getTime();
    const timer = setInterval(() => {
      const now = new Date().getTime();
      const distance = expireTime - now;

      if (distance <= 0) {
        clearInterval(timer);
        setCountdown('Hết hạn');
      } else {
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        setCountdown(`${minutes}:${seconds.toString().padStart(2, '0')}`);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [expiresAt]);

  return (
    <div className="modal">
      <div className="modal-content">
        {paymentStatus === 'pending' ? (
          <>
            <h3>📱 Quét mã QR để thanh toán</h3>

            <div className="qr-code">
              <img src={qrCodeUrl} alt="QR Code" />
            </div>

            <div className="payment-info">
              <p>Số tiền: <strong>{formatCurrency(amount)} VND</strong></p>
              <p>Nội dung CK: <code>{orderCode}</code></p>
              <p className="countdown">Hết hạn sau: <strong>{countdown}</strong></p>
            </div>

            <p className="instruction">
              1. Mở app ngân hàng<br/>
              2. Quét mã QR hoặc chuyển khoản với nội dung trên<br/>
              3. Chờ xác nhận (tự động)
            </p>

            <button onClick={onClose} className="btn-cancel">Đóng</button>
          </>
        ) : (
          <>
            <h3>✅ Thanh toán thành công!</h3>
            <p>Đang chuyển hướng...</p>
          </>
        )}
      </div>
    </div>
  );
}
```

---

## 🔄 Luồng hoàn chỉnh

```
┌─────────────────────────────────────────────────────────┐
│  1. User tạo đơn (Wallet)                              │
│     POST /symbol/orders/                               │
│     payment_method: "wallet"                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Check wallet balance │
          └──────────┬───────────┘
                     │
        ┌────────────┴─────────────┐
        │                          │
    Đủ tiền                   Thiếu tiền
        │                          │
        ▼                          ▼
┌───────────────┐      ┌──────────────────────────┐
│ Auto thanh toán│      │ Return insufficient_balance│
│ Order → paid  │      │ status: pending_payment   │
│ Tạo license   │      └───────────┬──────────────┘
└───────────────┘                  │
                                   ▼
                     ┌─────────────────────────────┐
                     │  Frontend hiển thị Modal    │
                     │  "Số dư không đủ"          │
                     │  - Hủy                      │
                     │  - Thanh toán ngay          │
                     └─────────────┬───────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
                  Hủy                     Thanh toán ngay
                     │                           │
                     ▼                           ▼
              ┌────────────┐      ┌──────────────────────────┐
              │ Đóng modal │      │ POST /order/{id}/pay-sepay│
              │ Giữ order  │      │ Nhận QR code SePay       │
              └────────────┘      └───────────┬──────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │ Hiển thị QR code│
                                    │ User quét & CK  │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ Webhook SePay   │
                                    │ Order → paid    │
                                    │ Tạo license     │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ ✅ Thành công!  │
                                    │ Navigate to     │
                                    │ Licenses        │
                                    └─────────────────┘
```

---

## 📊 API Summary

### API chính cho nút "Thanh toán ngay"

| Endpoint | Method | Mô tả | Amount |
|----------|--------|-------|--------|
| `/symbol/orders/` | POST | Tạo đơn | - |
| `/symbol/order/{id}/pay-sepay` | POST | Thanh toán ngay (Khuyến nghị) | Toàn bộ đơn hàng |
| `/symbol/order/{id}/topup-sepay` | POST | Top-up ví (Alternative) | Chỉ phần thiếu |

---

## 🧪 Test với Postman

### Scenario: Mua symbol khi thiếu tiền

1. **Login** → Lưu JWT token
2. **Nạp ví 50,000 VND** (để test thiếu tiền)
3. **Tạo đơn 200,000 VND** (wallet method):
   ```json
   POST /api/seapay/symbol/orders/
   {
     "items": [{"symbol_id": 1, "price": 200000, "license_days": 30}],
     "payment_method": "wallet"
   }
   ```
4. **Check response** → `insufficient_balance: true`
5. **Gọi API thanh toán ngay**:
   ```json
   POST /api/seapay/symbol/order/{order_id}/pay-sepay
   ```
6. **Nhận QR code** → Copy `qr_code_url` và `order_code`
7. **Mock webhook**:
   ```json
   POST /api/seapay/webhook/
   {
     "id": 123456789,
     "content": "{order_code}",
     "transferAmount": 200000,
     "transferType": "in",
     "referenceCode": "FT123456"
   }
   ```
8. **Check order history** → Status = `paid`
9. **Check licenses** → License đã được tạo

---

## ✅ Checklist Implementation

### Backend (✅ Đã implement)
- [x] Thay đổi logic SymbolPurchaseService: Không raise error khi thiếu tiền
- [x] Thêm fields vào CreateSymbolOrderResponse: `insufficient_balance`, `wallet_balance`, `shortage`
- [x] API `/symbol/order/{id}/pay-sepay` hoạt động đúng
- [x] API `/symbol/order/{id}/topup-sepay` vẫn hoạt động (alternative)
- [x] Webhook xử lý cả 2 luồng thanh toán

### Frontend (TODO)
- [ ] Kiểm tra `insufficient_balance` trong response
- [ ] Hiển thị modal "Số dư không đủ"
- [ ] Nút "Hủy": Đóng modal
- [ ] Nút "Thanh toán ngay": Gọi API `/pay-sepay`
- [ ] Hiển thị QR code payment
- [ ] Polling check payment status
- [ ] Countdown timer cho QR
- [ ] Navigate to licenses sau khi thành công

### Testing
- [ ] Test case: Đủ tiền → Auto thanh toán
- [ ] Test case: Thiếu tiền → Modal hiển thị
- [ ] Test case: Click "Thanh toán ngay" → QR code
- [ ] Test case: Webhook → Order paid → License created
- [ ] Test case: QR expired → Thông báo lỗi
- [ ] Test case: Click "Hủy" → Modal đóng, order pending

---

## 🔗 Tài liệu liên quan

- [README.md](./README.md) - Tài liệu tổng quan
- [POSTMAN_GUIDE.md](./POSTMAN_GUIDE.md) - Hướng dẫn test API
- API Docs: http://localhost:8000/api/docs

---

**Cập nhật**: 2024-11-15
**Tác giả**: Development Team
