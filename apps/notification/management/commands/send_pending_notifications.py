"""
Management command để gửi các notifications đang pending
Dùng để chạy cronjob hoặc celery task
"""
from django.core.management.base import BaseCommand
from apps.notification.services.delivery_service import DeliveryService


class Command(BaseCommand):
    help = 'Send pending notification deliveries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of deliveries to send (default: 100)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        self.stdout.write(f'Sending pending notifications (limit: {limit})...')

        service = DeliveryService()
        sent_count = service.send_pending_deliveries(limit=limit)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully sent {sent_count} notifications')
        )
