"""
Management command để retry các notifications bị failed
"""
from django.core.management.base import BaseCommand
from apps.notification.services.delivery_service import DeliveryService


class Command(BaseCommand):
    help = 'Retry failed notification deliveries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of deliveries to retry (default: 100)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        self.stdout.write(f'Retrying failed notifications (limit: {limit})...')

        service = DeliveryService()
        retried_count = service.retry_failed_deliveries(limit=limit)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully retried {retried_count} notifications')
        )
