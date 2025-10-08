from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService
import time


class Command(BaseCommand):
    help = 'Fast import all: shareholders, officers, events - optimized for speed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.0,
            help='Sleep time between API calls (default: 0.0 seconds - maximum speed)'
        )
        parser.add_argument(
            '--step',
            type=str,
            choices=['shareholders', 'officers', 'events', 'sub_companies', 'all'],
            default='all',
            help='Which step to run (default: all)'
        )

    def handle(self, *args, **options):
        sleep_time = options['sleep']
        step = options['step']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting fast import (step: {step}, sleep: {sleep_time}s)')
        )
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        total_start_time = time.time()
        
        try:
            if step in ['shareholders', 'all']:
                self.stdout.write('\n=== SHAREHOLDERS ===')
                start_time = time.time()
                shareholders_results = service.import_shareholders_for_all_symbols()
                end_time = time.time()
                
                total_shareholders = sum(r.get('shareholders_count', 0) for r in shareholders_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Shareholders: {len(shareholders_results)} symbols, {total_shareholders} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            if step in ['officers', 'all']:
                self.stdout.write('\n=== OFFICERS ===')
                start_time = time.time()
                officers_results = service.import_officers_for_all_symbols()
                end_time = time.time()
                
                total_officers = sum(r.get('officers_count', 0) for r in officers_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Officers: {len(officers_results)} symbols, {total_officers} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            if step in ['events', 'all']:
                self.stdout.write('\n=== EVENTS ===')
                start_time = time.time()
                events_results = service.import_events_for_all_symbols()
                end_time = time.time()
                
                total_events = sum(r.get('events_count', 0) for r in events_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Events: {len(events_results)} symbols, {total_events} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            if step in ['sub_companies', 'all']:
                self.stdout.write('\n=== SUB COMPANIES ===')
                start_time = time.time()
                sub_companies_results = service.import_sub_companies_for_all_symbols()
                end_time = time.time()
                
                total_sub_companies = sum(r.get('sub_companies_count', 0) for r in sub_companies_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Sub Companies: {len(sub_companies_results)} symbols, {total_sub_companies} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            total_end_time = time.time()
            
            self.stdout.write('\n=== SUMMARY ===')
            self.stdout.write(f'Total execution time: {total_end_time-total_start_time:.1f} seconds')
            
            if step == 'all':
                self.stdout.write('All import steps completed successfully!')
            else:
                self.stdout.write(f'{step.title()} import completed successfully!')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during fast import: {e}')
            )
            raise e