"""
Management command để đóng tất cả idle database connections
Chạy: python manage.py close_idle_connections
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Close all idle database connections to reduce open connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--idle-timeout',
            type=int,
            default=300,
            help='Idle time (seconds) to consider connection as idle (default: 300s = 5 min)'
        )

    def handle(self, *args, **options):
        idle_timeout = options['idle_timeout']

        self.stdout.write('Checking idle connections...')

        with connection.cursor() as cursor:
            # Query để đếm tất cả connections
            cursor.execute("""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            total_connections = cursor.fetchone()[0]

            # Query để đếm idle connections
            cursor.execute(f"""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                AND state = 'idle'
                AND state_change < now() - interval '{idle_timeout} seconds'
            """)
            idle_connections = cursor.fetchone()[0]

            self.stdout.write(f'Total connections: {total_connections}')
            self.stdout.write(f'Idle connections (>{idle_timeout}s): {idle_connections}')

            # Đóng idle connections (không đóng current connection và pg_stat_activity)
            cursor.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                AND pid != pg_backend_pid()
                AND state = 'idle'
                AND state_change < now() - interval '{idle_timeout} seconds'
            """)

            terminated_count = cursor.rowcount

            self.stdout.write(
                self.style.SUCCESS(f'Closed {terminated_count} idle connections')
            )

            # Kiểm tra lại sau khi đóng
            cursor.execute("""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            remaining_connections = cursor.fetchone()[0]

            self.stdout.write(
                self.style.SUCCESS(f'Remaining connections: {remaining_connections}')
            )
