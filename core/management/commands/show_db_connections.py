"""
Management command để xem chi tiết database connections
Chạy: python manage.py show_db_connections
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Hiển thị chi tiết tất cả database connections đang mở'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Hiển thị chi tiết đầy đủ'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']

        with connection.cursor() as cursor:
            # Tổng số connections
            cursor.execute("""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            total = cursor.fetchone()[0]

            self.stdout.write(self.style.WARNING(f'\n=== TOTAL CONNECTIONS: {total} ===\n'))

            # Thống kê theo state
            cursor.execute("""
                SELECT state, count(*) as count
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY state
                ORDER BY count DESC
            """)

            self.stdout.write('By State:')
            for row in cursor.fetchall():
                state = row[0] or 'NULL'
                count = row[1]
                self.stdout.write(f'  {state}: {count}')

            # Thống kê theo application_name
            cursor.execute("""
                SELECT application_name, count(*) as count
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY application_name
                ORDER BY count DESC
            """)

            self.stdout.write('\nBy Application:')
            for row in cursor.fetchall():
                app_name = row[0] or 'Unknown'
                count = row[1]
                self.stdout.write(f'  {app_name}: {count}')

            # Idle connections > 5 phút
            cursor.execute("""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                AND state = 'idle'
                AND state_change < now() - interval '300 seconds'
            """)
            idle_5min = cursor.fetchone()[0]

            self.stdout.write(
                self.style.WARNING(f'\nIdle connections > 5 min: {idle_5min}')
            )

            if verbose:
                # Chi tiết connections
                cursor.execute("""
                    SELECT
                        pid,
                        usename,
                        application_name,
                        client_addr,
                        state,
                        query,
                        state_change
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    ORDER BY state_change DESC
                    LIMIT 20
                """)

                self.stdout.write('\n=== TOP 20 RECENT CONNECTIONS ===')
                for row in cursor.fetchall():
                    pid, user, app, addr, state, query, change = row
                    self.stdout.write(f'\nPID: {pid}')
                    self.stdout.write(f'  User: {user}')
                    self.stdout.write(f'  App: {app}')
                    self.stdout.write(f'  State: {state}')
                    self.stdout.write(f'  Last change: {change}')
                    if query:
                        query_short = query[:100] + '...' if len(query) > 100 else query
                        self.stdout.write(f'  Query: {query_short}')

            self.stdout.write(
                self.style.SUCCESS(f'\nConnection check completed\n')
            )
