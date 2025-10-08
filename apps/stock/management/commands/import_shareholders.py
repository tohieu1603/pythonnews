
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import shareholders from vnstock - optimized version'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.5,
            help='Sleep time between API calls (default: 0.5 seconds)'
        )

    def handle(self, *args, **options):
        sleep_time = options['sleep']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting shareholders import (sleep: {sleep_time}s)')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            results = service.import_shareholders_for_all_symbols()
            
            total_shareholders = sum(r.get('shareholders_count', 0) for r in results)
            
            self.stdout.write(
                self.style.SUCCESS(f'Import completed!')
            )
            
            # Show summary
            self.stdout.write('Summary:')
            self.stdout.write(f'  Symbols processed: {len(results)}')
            self.stdout.write(f'  Total shareholders: {total_shareholders}')
            
            if results:
                avg_shareholders = total_shareholders / len(results)
                self.stdout.write(f'  Average shareholders per symbol: {avg_shareholders:.1f}')
                
                # Show sample results
                self.stdout.write('\nSample results:')
                for r in results[:5]:
                    self.stdout.write(f'  {r.get("symbol")}: {r.get("shareholders_count")} shareholders')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during shareholders import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Shareholders import completed successfully!')
        )