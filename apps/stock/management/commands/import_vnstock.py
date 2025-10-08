from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import data from vnstock into database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            default='HSX',
            help='Stock exchange to import (default: HSX)'
        )
        parser.add_argument(
            '--step',
            type=str,
            choices=['symbols', 'companies', 'industries', 'shareholders', 'officers', 'events', 'all'],
            default='all',
            help='Which step to run (default: all)'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=1.0,
            help='Sleep time between API calls (default: 1.0 seconds)'
        )

    def handle(self, *args, **options):
        exchange = options['exchange']
        step = options['step']
        sleep_time = options['sleep']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting vnstock import - Exchange: {exchange}, Step: {step}')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        try:
            if step == 'symbols':
                results = service.import_all_symbols_from_vnstock(exchange)
                self.stdout.write(
                    self.style.SUCCESS(f'Imported {len(results)} symbols')
                )
                
            elif step == 'companies':
                results = service.import_companies_from_vnstock(exchange)
                self.stdout.write(
                    self.style.SUCCESS(f'Imported {len(results)} companies')
                )
                
            elif step == 'industries':
                results = service.import_industries_for_symbols()
                self.stdout.write(
                    self.style.SUCCESS(f'Linked {len(results)} industry-symbol relationships')
                )
                
            elif step == 'shareholders':
                results = service.import_shareholders_for_all_symbols()
                total_shareholders = sum(r.get('shareholders_count', 0) for r in results)
                self.stdout.write(
                    self.style.SUCCESS(f'Imported {total_shareholders} shareholders for {len(results)} symbols')
                )
                
            elif step == 'officers':
                results = service.import_officers_for_all_symbols()
                total_officers = sum(r.get('officers_count', 0) for r in results)
                self.stdout.write(
                    self.style.SUCCESS(f'Imported {total_officers} officers for {len(results)} symbols')
                )
                
            elif step == 'events':
                results = service.import_events_for_all_symbols()
                total_events = sum(r.get('events_count', 0) for r in results)
                self.stdout.write(
                    self.style.SUCCESS(f'Imported {total_events} events for {len(results)} symbols')
                )
                
            elif step == 'all':
                results = service.import_all_data_sequential(exchange)
                summary = results.get('summary', {})
                
                self.stdout.write(
                    self.style.SUCCESS('Import completed! Summary:')
                )
                for key, value in summary.items():
                    self.stdout.write(f'  {key}: {value}')
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Import process completed successfully!')
        )