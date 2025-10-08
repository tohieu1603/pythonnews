from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import sub companies (subsidiaries) from vnstock - optimized version'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.0,
            help='Sleep time between API calls (default: 0.0 seconds - maximum speed)'
        )

    def handle(self, *args, **options):
        sleep_time = options['sleep']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting sub companies import (sleep: {sleep_time}s)')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            results = service.import_sub_companies_for_all_symbols()
            
            total_sub_companies = sum(r.get('sub_companies_count', 0) for r in results)
            
            self.stdout.write('\n=== SUMMARY ===')
            self.stdout.write(f'Symbols processed: {len(results)}')
            self.stdout.write(f'Total sub companies: {total_sub_companies}')
            
            self.stdout.write(
                self.style.SUCCESS('Sub companies import completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during sub companies import: {e}')
            )
            raise e