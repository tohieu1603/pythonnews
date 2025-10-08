import requests
from typing import Dict, Any, Optional
from decimal import Decimal
from django.conf import settings


class SepayClient:
    """Client để tương tác với SePay API"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'SEPAY_BASE_URL', 'https://api.sepay.vn')
        self.api_key = getattr(settings, 'SEPAY_API_KEY', '')
        self.account_number = getattr(settings, 'SEPAY_ACCOUNT_NUMBER', '')
        
    def create_qr_code(
        self, 
        amount: Decimal, 
        content: str, 
        bank_code: str = "BIDV"
    ) -> Dict[str, Any]:
        """
        Tạo QR code VietQR qua SePay
        """
        if not self.api_key:
            return self._get_mock_qr_data(amount, content, bank_code)
        
        url = f"{self.base_url}/api/v1/qr"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'accountNumber': self.account_number,
            'bankCode': bank_code,
            'amount': str(amount),
            'content': content,
            'template': 'vietqr'
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'account_number': data.get('accountNumber', self.account_number),
                    'account_name': data.get('accountName', ''),
                    'qr_image_url': data.get('qrCode', ''),
                    'qr_svg': data.get('qrSVG', ''),
                    'session_id': data.get('sessionId', ''),
                    'bank_code': bank_code
                }
            else:
                raise SepayAPIError(f"SePay API error: {data.get('message', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise SepayAPIError(f"Failed to create QR code: {str(e)}")
    
    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Kiểm tra trạng thái giao dịch"""
        if not self.api_key:
            return self._get_mock_transaction_status(transaction_id)
        
        url = f"{self.base_url}/api/v1/transactions/{transaction_id}"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise SepayAPIError(f"Failed to get transaction status: {str(e)}")
    
    def get_bank_transactions(
        self, 
        from_date: str, 
        to_date: str, 
        limit: int = 100
    ) -> Dict[str, Any]:
        """Lấy danh sách giao dịch ngân hàng"""
        if not self.api_key:
            return self._get_mock_bank_transactions()
        
        url = f"{self.base_url}/api/v1/transactions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'fromDate': from_date,
            'toDate': to_date,
            'limit': limit
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise SepayAPIError(f"Failed to get bank transactions: {str(e)}")
    
    def _get_mock_qr_data(self, amount: Decimal, content: str, bank_code: str) -> Dict[str, Any]:
        """Mock data cho development"""
        return {
            'account_number': '96247CISI1',
            'account_name': 'BIDV Account',
            'qr_image_url': f'https://qr.sepay.vn/img?acc=96247CISI1&bank=BIDV&amount={int(amount)}&des={content}&template=compact',
            'qr_svg': '<svg>Mock QR SVG</svg>',
            'session_id': f'mock_session_{content}',
            'bank_code': 'BIDV'
        }
    
    def _get_mock_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Mock transaction status"""
        return {
            'status': 'success',
            'data': {
                'id': transaction_id,
                'status': 'completed',
                'amount': '100000',
                'content': 'TOPUP_1234567890_ABCD'
            }
        }
    
    def _get_mock_bank_transactions(self) -> Dict[str, Any]:
        """Mock bank transactions"""
        return {
            'status': 'success',
            'data': [],
            'pagination': {
                'total': 0,
                'limit': 100,
                'offset': 0
            }
        }


class SepayAPIError(Exception):
    """Exception cho SePay API errors"""
    pass