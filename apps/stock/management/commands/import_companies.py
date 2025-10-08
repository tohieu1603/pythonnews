from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import companies from vnstock và cập nhật company_id ở Symbol'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            default='HSX',
            help='Stock exchange (default: HSX)'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=2.0,
            help='Sleep time between API calls (default: 2.0 seconds)'
        )

    def handle(self, *args, **options):
        exchange = options['exchange']
        sleep_time = options['sleep']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting company import for exchange: {exchange}')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            results = service.import_companies_from_vnstock(exchange)
            
            self.stdout.write(
                self.style.SUCCESS(f'Imported {len(results)} companies')
            )
            
            # Show summary
            processed_symbols = len(results)
            successful_companies = len([r for r in results if r.get('status') == 'processed'])
            
            self.stdout.write('Summary:')
            self.stdout.write(f'  Total symbols processed: {processed_symbols}')
            self.stdout.write(f'  Successful companies: {successful_companies}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during company import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Company import completed successfully!')
        )