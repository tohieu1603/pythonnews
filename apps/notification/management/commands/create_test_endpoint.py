"""
Management command để tạo test endpoint cho notification
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.notification.models import UserEndpoint

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test notification endpoint'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID (default: first user in DB)'
        )
        parser.add_argument(
            '--channel',
            type=str,
            default='telegram',
            help='Channel: telegram|zalo|email (default: telegram)'
        )
        parser.add_argument(
            '--address',
            type=str,
            default='123456789',
            help='Address (Telegram chat_id, Zalo user_id, or email)'
        )
        parser.add_argument(
            '--verified',
            action='store_true',
            help='Mark as verified'
        )

    def handle(self, *args, **options):
        # Get user
        user_id = options.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User {user_id} not found'))
                return
        else:
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('No users found in database'))
                return

        # Create endpoint
        channel = options['channel']
        address = options['address']
        verified = options['verified']

        endpoint, created = UserEndpoint.objects.get_or_create(
            user=user,
            channel=channel,
            address=address,
            defaults={
                'is_primary': True,
                'verified': verified,
                'details': {'created_by': 'test_command'}
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created endpoint: {endpoint.endpoint_id}\n'
                    f'User: {user.email}\n'
                    f'Channel: {channel}\n'
                    f'Address: {address}\n'
                    f'Verified: {verified}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Endpoint already exists: {endpoint.endpoint_id}')
            )
