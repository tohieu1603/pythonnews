from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import officers from vnstock - optimized version'

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
            self.style.SUCCESS(f'Starting officers import (sleep: {sleep_time}s)')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            results = service.import_officers_for_all_symbols()
            
            total_officers = sum(r.get('officers_count', 0) for r in results)
            
            self.stdout.write(
                self.style.SUCCESS('Import completed!')
            )
            
            # Show summary
            self.stdout.write('Summary:')
            self.stdout.write(f'  Symbols processed: {len(results)}')
            self.stdout.write(f'  Total officers: {total_officers}')
            
            if results:
                avg_officers = total_officers / len(results)
                self.stdout.write(f'  Average officers per symbol: {avg_officers:.1f}')
                
                # Show sample results
                self.stdout.write('\nSample results:')
                for r in results[:5]:
                    self.stdout.write(f'  {r.get("symbol")}: {r.get("officers_count")} officers')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during officers import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Officers import completed successfully!')
        )