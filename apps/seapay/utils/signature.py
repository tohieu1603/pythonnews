import hmac
import hashlib

SECRET_KEY = "MY_SEAPAY_SECRET"

def verify_signature(payload: dict) -> bool:
    signature = payload.pop("signature", None)
    if not signature:
        return False
    msg = f"{payload['order_id']}{payload['status']}{payload['amount']}"
    computed_signature = hmac.new(
        SECRET_KEY.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, computed_signature)
