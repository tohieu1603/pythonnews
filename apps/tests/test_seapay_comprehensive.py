from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json
import uuid

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

from apps.seapay.models import (
    PayWallet,
    PayWalletLedger,
    PayPaymentIntent,
    PayPayment,
    PaySymbolOrder,
    PaySymbolOrderItem,
    PaySymbolLicense,
    PaymentMethod,
    OrderStatus,
    PaymentStatus,
    IntentStatus,
    WalletTxType,
    LicenseStatus
)
from apps.seapay.services.symbol_purchase_service import SymbolPurchaseService
from apps.seapay.services.wallet_service import WalletService
from apps.seapay.services.payment_service import PaymentService
from apps.stock.models import Symbol
from apps.setting.models import (
    SymbolAutoRenewSubscription,
    SymbolAutoRenewAttempt,
    AutoRenewStatus,
    AutoRenewAttemptStatus,
)

User = get_user_model()


class SeaPayWalletTestCase(TestCase):
    """Test PayWallet functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.wallet_service = WalletService()
    
    def test_create_wallet(self):
        """Test wallet creation"""
        wallet = self.wallet_service.get_or_create_wallet(self.user)
        
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('0'))
        self.assertEqual(wallet.currency, 'VND')
        self.assertEqual(wallet.status, 'active')
    
    def test_wallet_topup(self):
        """Test wallet balance increase"""
        wallet = self.wallet_service.get_or_create_wallet(self.user)
        
        # Topup 100,000 VND
        amount = Decimal('100000')
        self.wallet_service.credit(
            wallet=wallet,
            amount=amount,
            tx_type=WalletTxType.DEPOSIT,
            note="Test topup",
            order=None
        )
        
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, amount)
        
        # Check ledger entry
        ledger = PayWalletLedger.objects.filter(wallet=wallet).first()
        self.assertEqual(ledger.amount, amount)
        self.assertEqual(ledger.tx_type, WalletTxType.DEPOSIT)
        self.assertTrue(ledger.is_credit)
        self.assertEqual(ledger.balance_after, amount)
    
    def test_wallet_debit(self):
        """Test wallet balance decrease"""
        wallet = self.wallet_service.get_or_create_wallet(self.user)
        
        # Add initial balance
        wallet.balance = Decimal('50000')
        wallet.save()
        
        # Debit 20,000 VND
        debit_amount = Decimal('20000')
        self.wallet_service.debit(
            wallet=wallet,
            amount=debit_amount,
            tx_type=WalletTxType.PURCHASE,
            note="Test purchase",
            order=None
        )
        
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('30000'))
        
        # Check ledger entry
        ledger = PayWalletLedger.objects.filter(
            wallet=wallet, 
            tx_type=WalletTxType.PURCHASE
        ).first()
        self.assertEqual(ledger.amount, debit_amount)
        self.assertFalse(ledger.is_credit)
    
    def test_insufficient_funds(self):
        """Test debit with insufficient funds"""
        wallet = self.wallet_service.get_or_create_wallet(self.user)
        wallet.balance = Decimal('10000')
        wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.wallet_service.debit(
                wallet=wallet,
                amount=Decimal('20000'),
                tx_type=WalletTxType.PURCHASE,
                note="Test insufficient funds",
                order=None
            )
        
        self.assertIn("Insufficient balance", str(context.exception))


class SeaPayPaymentIntentTestCase(TestCase):
    """Test Payment Intent functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="payuser",
            email="pay@example.com", 
            password="paypass123"
        )
        self.payment_service = PaymentService()
    
    def test_create_payment_intent(self):
        """Test payment intent creation"""
        intent_data = {
            'purpose': 'wallet_topup',
            'amount': Decimal('100000'),
            'currency': 'VND',
            'expires_in_minutes': 30,
            'metadata': {'test': 'data'}
        }
        
        intent = self.payment_service.create_payment_intent(
            user=self.user,
            **intent_data
        )
        
        self.assertEqual(intent.user, self.user)
        self.assertEqual(intent.purpose, 'wallet_topup')
        self.assertEqual(intent.amount, Decimal('100000'))
        self.assertEqual(intent.status, IntentStatus.PENDING)
        self.assertIsNotNone(intent.order_code)
        self.assertIsNotNone(intent.expires_at)
    
    def test_payment_intent_expiry(self):
        """Test payment intent expiration"""
        # Create expired intent
        intent = PayPaymentIntent.objects.create(
            user=self.user,
            purpose='test_expired',
            amount=Decimal('50000'),
            status=IntentStatus.PENDING,
            order_code='TEST123',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        self.assertTrue(intent.is_expired())
    
    @patch('apps.seapay.services.payment_service.requests.post')
    def test_sepay_webhook_processing(self, mock_post):
        """Test SePay webhook processing"""
        # Mock SePay API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'status': 'success'}
        
        # Create payment intent
        intent = PayPaymentIntent.objects.create(
            user=self.user,
            purpose='wallet_topup',
            amount=Decimal('100000'),
            status=IntentStatus.PENDING,
            order_code='SEPAY123',
            reference_code='REF123',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Simulate webhook data
        webhook_data = {
            'id': 12345,
            'gateway': 'BIDV',
            'transactionDate': '2025-09-25 15:30:00',
            'accountNumber': '12345678',
            'subAccount': '',
            'content': 'REF123',
            'transferType': 'in',
            'transferAmount': Decimal('100000'),
            'referenceCode': 'REF123',
            'accumulated': 100000
        }
        
        result = self.payment_service.process_sepay_webhook(webhook_data)
        
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['payment_id'])
        
        # Check intent is completed
        intent.refresh_from_db()
        self.assertEqual(intent.status, IntentStatus.COMPLETED)


class SeaPaySymbolPurchaseTestCase(TestCase):
    """Test Symbol Purchase functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="buyerpass123"
        )
        self.symbol = Symbol.objects.create(
            name="AAPL",
            exchange="NYSE"
        )
        self.wallet = PayWallet.objects.create(
            user=self.user,
            balance=Decimal('500000'),
            currency='VND',
            status='active'
        )
        self.purchase_service = SymbolPurchaseService()
    
    def test_create_symbol_order_wallet_payment(self):
        """Test creating symbol order with wallet payment"""
        order_data = {
            'items': [
                {
                    'symbol_id': self.symbol.id,
                    'price': Decimal('100000'),
                    'license_days': 30,
                    'metadata': {'test': 'order'}
                }
            ],
            'payment_method': PaymentMethod.WALLET,
            'description': 'Test order'
        }
        
        order = self.purchase_service.create_symbol_order(
            user=self.user,
            **order_data
        )
        
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(order.total_amount, Decimal('100000'))
        self.assertEqual(order.payment_method, PaymentMethod.WALLET)
        
        # Check wallet balance deducted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('400000'))
        
        # Check order items
        item = order.items.first()
        self.assertEqual(item.symbol_id, self.symbol.id)
        self.assertEqual(item.price, Decimal('100000'))
        self.assertEqual(item.license_days, 30)
        
        # Check license created
        license_obj = PaySymbolLicense.objects.get(
            user=self.user,
            symbol_id=self.symbol.id
        )
        self.assertEqual(license_obj.status, LicenseStatus.ACTIVE)
    
    def test_create_symbol_order_sepay_payment(self):
        """Test creating symbol order with SePay payment"""
        order_data = {
            'items': [
                {
                    'symbol_id': self.symbol.id,
                    'price': Decimal('200000'),
                    'license_days': 30,
                }
            ],
            'payment_method': PaymentMethod.SEPAY_TRANSFER,
            'description': 'SePay test order'
        }
        
        result = self.purchase_service.create_symbol_order(
            user=self.user,
            **order_data
        )
        
        # Should return order and payment intent
        self.assertIn('order', result)
        self.assertIn('payment_intent', result)
        
        order = result['order']
        intent = result['payment_intent']
        
        self.assertEqual(order.status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(intent.purpose, 'symbol_purchase')
        self.assertEqual(intent.amount, Decimal('200000'))
    
    def test_insufficient_wallet_balance(self):
        """Test order creation with insufficient wallet balance"""
        # Set low balance
        self.wallet.balance = Decimal('10000')
        self.wallet.save()
        
        order_data = {
            'items': [
                {
                    'symbol_id': self.symbol.id,
                    'price': Decimal('100000'),
                    'license_days': 30,
                }
            ],
            'payment_method': PaymentMethod.WALLET,
        }
        
        with self.assertRaises(ValueError) as context:
            self.purchase_service.create_symbol_order(
                user=self.user,
                **order_data
            )
        
        self.assertIn("Insufficient wallet balance", str(context.exception))
    
    def test_symbol_access_check(self):
        """Test checking symbol access"""
        # Create license
        license_obj = PaySymbolLicense.objects.create(
            user=self.user,
            symbol_id=self.symbol.id,
            status=LicenseStatus.ACTIVE,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            is_lifetime=False
        )
        
        access_info = self.purchase_service.check_symbol_access(
            user=self.user,
            symbol_id=self.symbol.id
        )
        
        self.assertTrue(access_info['has_access'])
        self.assertEqual(access_info['license_id'], str(license_obj.license_id))
        self.assertFalse(access_info['is_lifetime'])
    
    def test_auto_renew_subscription_creation(self):
        """Test auto-renew subscription creation during purchase"""
        order_data = {
            'items': [
                {
                    'symbol_id': self.symbol.id,
                    'price': Decimal('100000'),
                    'license_days': 30,
                    'auto_renew': True,
                    'auto_renew_price': Decimal('90000'),
                    'auto_renew_cycle_days': 30,
                }
            ],
            'payment_method': PaymentMethod.WALLET,
        }
        
        order = self.purchase_service.create_symbol_order(
            user=self.user,
            **order_data
        )
        
        # Check auto-renew subscription created
        subscription = SymbolAutoRenewSubscription.objects.get(
            user=self.user,
            symbol_id=self.symbol.id
        )
        
        self.assertEqual(subscription.status, AutoRenewStatus.ACTIVE)
        self.assertEqual(subscription.price, Decimal('90000'))
        self.assertEqual(subscription.cycle_days, 30)
        self.assertIsNotNone(subscription.next_billing_at)


class SeaPayAutoRenewTestCase(TestCase):
    """Test Auto-Renew functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="autouser",
            email="auto@example.com",
            password="autopass123"
        )
        self.symbol = Symbol.objects.create(
            name="MSFT",
            exchange="NASDAQ"
        )
        self.wallet = PayWallet.objects.create(
            user=self.user,
            balance=Decimal('300000'),
            currency='VND',
            status='active'
        )
    
    def test_auto_renew_success(self):
        """Test successful auto-renewal"""
        from apps.setting.services.subscription_service import SymbolAutoRenewService
        
        # Create subscription
        subscription = SymbolAutoRenewSubscription.objects.create(
            user=self.user,
            symbol_id=self.symbol.id,
            status=AutoRenewStatus.ACTIVE,
            price=Decimal('50000'),
            cycle_days=30,
            payment_method=PaymentMethod.WALLET,
            next_billing_at=timezone.now() - timedelta(minutes=5)  # Due for billing
        )
        
        service = SymbolAutoRenewService()
        result = service.run_due_subscriptions(limit=1)
        
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['failed'], 0)
        
        # Check wallet balance deducted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('250000'))
        
        # Check attempt record
        attempt = SymbolAutoRenewAttempt.objects.get(subscription=subscription)
        self.assertEqual(attempt.status, AutoRenewAttemptStatus.SUCCESS)
        self.assertEqual(attempt.amount_charged, Decimal('50000'))
    
    def test_auto_renew_insufficient_funds(self):
        """Test auto-renewal with insufficient funds"""
        from apps.setting.services.subscription_service import SymbolAutoRenewService
        
        # Set low wallet balance
        self.wallet.balance = Decimal('10000')
        self.wallet.save()
        
        subscription = SymbolAutoRenewSubscription.objects.create(
            user=self.user,
            symbol_id=self.symbol.id,
            status=AutoRenewStatus.ACTIVE,
            price=Decimal('50000'),
            cycle_days=30,
            payment_method=PaymentMethod.WALLET,
            next_billing_at=timezone.now() - timedelta(minutes=5)
        )
        
        service = SymbolAutoRenewService()
        result = service.run_due_subscriptions(limit=1)
        
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['success'], 0)
        self.assertEqual(result['failed'], 1)
        
        # Check attempt record
        attempt = SymbolAutoRenewAttempt.objects.get(subscription=subscription)
        self.assertEqual(attempt.status, AutoRenewAttemptStatus.FAILED)
        self.assertIn("Insufficient", attempt.error_message)


class SeaPayAPITestCase(TestCase):
    """Test SeaPay API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="apiuser",
            email="api@example.com",
            password="apipass123"
        )
        self.client = Client()
        
        # Mock JWT authentication
        from core.jwt_auth import create_jwt_token
        self.jwt_token = create_jwt_token(self.user)
        self.auth_headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'content_type': 'application/json'
        }
    
    def test_get_wallet_info(self):
        """Test GET /api/sepay/wallet endpoint"""
        response = self.client.get('/api/sepay/wallet/', **self.auth_headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('balance', data)
        self.assertIn('currency', data)
        self.assertIn('status', data)
    
    def test_create_wallet_topup_intent(self):
        """Test POST /api/sepay/wallet/topup endpoint"""
        payload = {
            'amount': '100000',
            'currency': 'VND',
            'bank_code': 'BIDV'
        }
        
        response = self.client.post(
            '/api/sepay/wallet/topup/',
            data=json.dumps(payload),
            **self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('intent_id', data)
        self.assertIn('qr_code_url', data)
        self.assertIn('transfer_content', data)
    
    def test_create_symbol_order_api(self):
        """Test POST /api/sepay/symbol/orders endpoint"""
        symbol = Symbol.objects.create(name="GOOGL", exchange="NASDAQ")
        
        # Create wallet with balance
        PayWallet.objects.create(
            user=self.user,
            balance=Decimal('200000'),
            currency='VND',
            status='active'
        )
        
        payload = {
            'items': [
                {
                    'symbol_id': symbol.id,
                    'price': '150000',
                    'license_days': 30
                }
            ],
            'payment_method': 'wallet',
            'description': 'API test order'
        }
        
        response = self.client.post(
            '/api/sepay/symbol/orders/',
            data=json.dumps(payload),
            **self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('order_id', data)
        self.assertEqual(data['status'], 'paid')
        self.assertEqual(data['total_amount'], '150000.00')
    
    def test_get_order_history(self):
        """Test GET /api/sepay/symbol/orders/history endpoint"""
        response = self.client.get(
            '/api/sepay/symbol/orders/history/',
            **self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('total', data)
        self.assertIn('page', data)
    
    def test_get_topup_history(self):
        """Test GET /api/sepay/wallet/topup-history endpoint"""
        response = self.client.get(
            '/api/sepay/wallet/topup-history/',
            **self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
    
    def test_unauthorized_access(self):
        """Test API access without authentication"""
        response = self.client.get('/api/sepay/wallet/')
        self.assertEqual(response.status_code, 401)
    
    def test_invalid_jwt_token(self):
        """Test API access with invalid JWT"""
        headers = {
            'HTTP_AUTHORIZATION': 'Bearer invalid_token_here',
            'content_type': 'application/json'
        }
        
        response = self.client.get('/api/sepay/wallet/', **headers)
        self.assertEqual(response.status_code, 401)


class SeaPayWebhookTestCase(TestCase):
    """Test webhook processing"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="webhook",
            email="webhook@example.com",
            password="webhookpass"
        )
        self.client = Client()
    
    def test_sepay_webhook_success(self):
        """Test successful SePay webhook processing"""
        # Create payment intent
        intent = PayPaymentIntent.objects.create(
            user=self.user,
            purpose='wallet_topup',
            amount=Decimal('100000'),
            status=IntentStatus.PENDING,
            order_code='WH123',
            reference_code='WHREF123',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        webhook_payload = {
            'id': 99999,
            'gateway': 'BIDV',
            'transactionDate': '2025-09-25 16:00:00',
            'accountNumber': '12345678',
            'content': 'WHREF123',
            'transferType': 'in',
            'transferAmount': 100000,
            'referenceCode': 'WHREF123',
            'accumulated': 100000
        }
        
        response = self.client.post(
            '/api/sepay/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check intent updated
        intent.refresh_from_db()
        self.assertEqual(intent.status, IntentStatus.COMPLETED)
        
        # Check wallet credited
        wallet = PayWallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('100000'))
    
    def test_webhook_duplicate_processing(self):
        """Test webhook duplicate request handling"""
        intent = PayPaymentIntent.objects.create(
            user=self.user,
            purpose='wallet_topup',
            amount=Decimal('50000'),
            status=IntentStatus.COMPLETED,  # Already processed
            order_code='DUP123',
            reference_code='DUPREF123',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        webhook_payload = {
            'id': 88888,
            'gateway': 'BIDV',
            'transactionDate': '2025-09-25 16:00:00',
            'accountNumber': '12345678',
            'content': 'DUPREF123',
            'transferType': 'in',
            'transferAmount': 50000,
            'referenceCode': 'DUPREF123'
        }
        
        response = self.client.post(
            '/api/sepay/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        # Should still return 200 but not process again
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('already processed', data['message'].lower())


class SeaPayErrorHandlingTestCase(TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="erroruser",
            email="error@example.com",
            password="errorpass"
        )
    
    def test_create_order_nonexistent_symbol(self):
        """Test creating order with non-existent symbol"""
        from apps.seapay.services.symbol_purchase_service import SymbolPurchaseService
        
        service = SymbolPurchaseService()
        
        with self.assertRaises(ValueError) as context:
            service.create_symbol_order(
                user=self.user,
                items=[
                    {
                        'symbol_id': 99999,  # Non-existent
                        'price': Decimal('100000'),
                        'license_days': 30,
                    }
                ],
                payment_method=PaymentMethod.WALLET
            )
        
        self.assertIn("Symbol not found", str(context.exception))
    
    def test_invalid_payment_amount(self):
        """Test invalid payment amounts"""
        from apps.seapay.services.payment_service import PaymentService
        
        service = PaymentService()
        
        # Test zero amount
        with self.assertRaises(ValueError):
            service.create_payment_intent(
                user=self.user,
                purpose='test',
                amount=Decimal('0'),
                currency='VND'
            )
        
        # Test negative amount
        with self.assertRaises(ValueError):
            service.create_payment_intent(
                user=self.user,
                purpose='test',
                amount=Decimal('-1000'),
                currency='VND'
            )
    
    def test_expired_payment_intent_processing(self):
        """Test processing expired payment intent"""
        expired_intent = PayPaymentIntent.objects.create(
            user=self.user,
            purpose='test_expired',
            amount=Decimal('100000'),
            status=IntentStatus.PENDING,
            order_code='EXP123',
            expires_at=timezone.now() - timedelta(hours=2)  # Expired
        )
        
        from apps.seapay.services.payment_service import PaymentService
        service = PaymentService()
        
        webhook_data = {
            'referenceCode': 'EXP123',
            'transferAmount': Decimal('100000'),
            'transferType': 'in'
        }
        
        result = service.process_sepay_webhook(webhook_data)
        
        # Should reject expired intent
        self.assertFalse(result['success'])
        self.assertIn('expired', result['message'].lower())


# Run all tests
if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)