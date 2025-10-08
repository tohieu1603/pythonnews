from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import tất cả dữ liệu stock từ vnstock: symbols, companies, industries, shareholders, officers, events, sub_companies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            default='HSX',
            help='Stock exchange to import from (default: HSX)'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=1.0,
            help='Sleep time between API calls in seconds (default: 1.0 for rate limit safety)'
        )
        parser.add_argument(
            '--fast',
            action='store_true',
            help='Fast mode with minimal sleep (0.5s) - use with caution'
        )
        parser.add_argument(
            '--safe',
            action='store_true',
            help='Safe mode with longer sleep (2.0s) to avoid rate limits'
        )

    def handle(self, *args, **options):
        exchange = options['exchange']
        
        # Determine sleep time
        if options['fast']:
            sleep_time = 0.5
            self.stdout.write(self.style.WARNING('⚡ Fast mode enabled - may hit rate limits!'))
        elif options['safe']:
            sleep_time = 2.0
            self.stdout.write(self.style.SUCCESS('🛡️ Safe mode enabled - longer sleep times'))
        else:
            sleep_time = options['sleep']
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Starting complete import for {exchange} exchange with {sleep_time}s sleep')
        )
        
        # Initialize service
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            # Run complete import
            results = service.import_all_data_sequential(exchange=exchange)
            
            # Check results
            if results.get('errors'):
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Import completed with {len(results["errors"])} errors')
                )
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'   ❌ {error}'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ Complete import finished successfully!'))
            
            # Print summary
            summary = results.get('summary', {})
            if summary:
                self.stdout.write(self.style.SUCCESS('\n📊 FINAL SUMMARY:'))
                for key, value in summary.items():
                    self.stdout.write(f'   {key}: {value}')
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⛔ Import interrupted by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'💥 Critical error: {e}'))
            raise