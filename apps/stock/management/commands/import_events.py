from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import events from vnstock - optimized version'

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
            self.style.SUCCESS(f'Starting events import (sleep: {sleep_time}s)')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            results = service.import_events_for_all_symbols()
            
            total_events = sum(r.get('events_count', 0) for r in results)
            
            self.stdout.write(
                self.style.SUCCESS('Import completed!')
            )
            
            # Show summary
            self.stdout.write('Summary:')
            self.stdout.write(f'  Symbols processed: {len(results)}')
            self.stdout.write(f'  Total events: {total_events}')
            
            if results:
                avg_events = total_events / len(results)
                self.stdout.write(f'  Average events per symbol: {avg_events:.1f}')
                
                # Show sample results
                self.stdout.write('\nSample results:')
                for r in results[:5]:
                    self.stdout.write(f'  {r.get("symbol")}: {r.get("events_count")} events')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during events import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Events import completed successfully!')
        )