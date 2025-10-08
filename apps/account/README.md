# Hướng Dẫn Frontend Tích Hợp Đăng Nhập Google

Tài liệu dành cho đội FE khi kết nối với backend `apps.account`. Ví dụ sử dụng tiếng Việt và bám sát implementation hiện tại.

---

## 1. Mục tiêu
- Hiểu luồng OAuth giữa Google ↔ backend ↔ FE.
- Xác định rõ API cần gọi, dữ liệu request/response.
- Sẵn sàng xử lý lỗi phát sinh trong quá trình tích hợp.

---

## 2. Chuẩn bị
1. Backend đã cấu hình `.env`:
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback
   ```
2. FE cần `GOOGLE_CLIENT_ID` để cấu hình Google Identity Services (GIS) nếu dùng One Tap/mobile.
3. Redirect URI trên Google Cloud Console phải khớp với URI FE thực tế.

---

## 3. Luồng Authorization Code (Web)
### 3.1 Các bước
1. Gọi `GET /api/auth/google/auth-url` → nhận `auth_url`.
2. Redirect người dùng đến `auth_url`.
3. Google trả về `GOOGLE_REDIRECT_URI?code=...&state=...`.
4. FE lấy `code` (và `state` nếu có) rồi POST đến `POST /api/auth/google/login`.
5. Backend trả `TokenResponse` với `access_token`, `refresh_token`, `user`.
6. FE lưu token, cập nhật state đăng nhập, sử dụng `access_token` ở header `Authorization: Bearer <token>` cho các API protected.

> Dùng PKCE? Gửi thêm `code_verifier` trong body – backend đã hỗ trợ.

### 3.2 Ví dụ TypeScript/React
```ts
const { auth_url } = await fetch('/api/auth/google/auth-url').then(r => r.json());
window.location.href = auth_url;
```
Callback:
```ts
const params = new URLSearchParams(window.location.search);
const code = params.get('code');
if (!code) throw new Error('Missing authorization code');

const res = await fetch('/api/auth/google/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ code })
});
const data = await res.json();
if (!res.ok) throw new Error(data.error || 'Google sign-in failed');
storeTokens(data.access_token, data.refresh_token);
setCurrentUser(data.user);
```

---

## 4. Luồng ID Token (SPA/Mobile)
### 4.1 Khi sử dụng
- Ứng dụng mobile native hoặc SPA dùng Google One Tap.
- FE nhận `credential` (ID token) trực tiếp từ GIS.

### 4.2 Các bước
```js
google.accounts.id.initialize({
  client_id: GOOGLE_CLIENT_ID,
  callback: async ({ credential }) => {
    const res = await fetch('/api/auth/google/login-id-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: credential })
    });
    const data = await res.json();
    if (!res.ok) {
      console.error(data);
      return;
    }
    saveTokens(data.access_token, data.refresh_token);
    setCurrentUser(data.user);
  }
});
```
- Không cần redirect.
- Backend verify ID token bằng `google-auth` (nếu cài) hoặc gọi API `tokeninfo`.

---

## 5. Hợp đồng dữ liệu
### 5.1 Request FE → BE
| Endpoint | Body | Ghi chú |
|----------|------|---------|
| `POST /api/auth/google/login` | `{ code, redirect_uri?, code_verifier? }` | `redirect_uri` chỉ cần khi FE xử lý code ở URI khác. |
| `POST /api/auth/google/login-id-token` | `{ id_token }` | ID token từ Google Identity Services. |
| `POST /api/auth/login` | `{ email, password }` | Đăng nhập truyền thống (nếu dùng). |

### 5.2 Response BE → FE
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "user@example.com",
    "first_name": "User",
    "last_name": null
  }
}
```
- `access_token`: JWT cho các yêu cầu cần auth.
- `refresh_token`: JWT TTL dài, backend chưa cung cấp endpoint refresh (cân nhắc bổ sung nếu muốn dùng).
- `user`: thông tin hồ sơ cơ bản.

---

## 6. API liên quan
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/auth/google/auth-url` | GET | Lấy URL đăng nhập Google (có thể truyền `state`). |
| `/api/auth/google/login` | POST | Xử lý Authorization Code → trả JWT + user. |
| `/api/auth/google/login-id-token` | POST | Xử lý ID token → trả JWT + user. |
| `/api/auth/profile` | GET | Lấy thông tin user hiện tại (cần `Authorization`). |

---

## 7. Checklist sau tích hợp
1. Web flow: chạy đầy đủ, đảm bảo nhận token + user.
2. ID token flow: thử với One Tap/mobile emulator.
3. Profile: sau khi có `access_token`, gọi `/api/auth/profile` phải trả đúng user.
4. Xử lý lỗi: test `code` hết hạn, ID token sai… để UI báo lỗi chuẩn.

---

## 8. Lỗi thường gặp & cách xử lý
| Backend trả | Nguyên nhân | Hành động FE |
|-------------|-------------|---------------|
| `Invalid GOOGLE_CLIENT_ID configuration` | Backend thiếu config | Hiển thị lỗi chung, báo backend check. |
| `Google did not return an access_token` | `code` hết hạn hoặc redirect URI sai | Yêu cầu user đăng nhập lại → gọi `/google/auth-url`. |
| `Unable to verify ID token` | ID token hết hạn / sai audience | Lấy ID token mới qua GIS. |
| `ID token audience is not allowed` | FE dùng sai `GOOGLE_CLIENT_ID` | Kiểm tra lại cấu hình GIS. |
| `Invalid email or password` | Login truyền thống sai | Thông báo cho người dùng nhập lại. |

---

## 9. Lưu ý bảo mật
- FE không bao giờ giữ `GOOGLE_CLIENT_SECRET`; mọi token exchange phải đi qua backend.
- Nếu cần refresh token dài hạn, phối hợp backend để bổ sung endpoint refresh + cookie HTTP-only.
- Production bắt buộc dùng HTTPS.

---

_Tài liệu sẽ cập nhật khi backend thay đổi. Liên hệ backend nếu cần ví dụ riêng (React Native, Flutter, ...)._ 
