from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService
import time


class Command(BaseCommand):
    help = 'Complete import pipeline: symbols -> companies -> industries -> shareholders/officers/events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.0,
            help='Sleep time between API calls (default: 0.0 seconds - maximum speed)'
        )
        parser.add_argument(
            '--skip-step',
            type=str,
            nargs='*',
            choices=['symbols', 'companies', 'industries', 'shareholders', 'officers', 'events', 'sub_companies'],
            default=[],
            help='Steps to skip (e.g., --skip-step symbols companies)'
        )

    def handle(self, *args, **options):
        sleep_time = options['sleep']
        skip_steps = set(options['skip_step'])
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting complete import pipeline (sleep: {sleep_time}s)')
        )
        
        if skip_steps:
            self.stdout.write(f'Skipping steps: {", ".join(skip_steps)}')
        
        service = VnstockImportService(per_symbol_sleep=sleep_time)
        
        total_start_time = time.time()
        
        try:
            # Step 1: Symbols
            if 'symbols' not in skip_steps:
                self.stdout.write('\n=== STEP 1: SYMBOLS ===')
                start_time = time.time()
                symbols_count = service.import_all_symbols()
                end_time = time.time()
                
                self.stdout.write(self.style.SUCCESS(
                    f'Symbols: {symbols_count} imported (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 2: Companies
            if 'companies' not in skip_steps:
                self.stdout.write('\n=== STEP 2: COMPANIES ===')
                start_time = time.time()
                companies_results = service.import_companies_for_all_symbols()
                end_time = time.time()
                
                self.stdout.write(self.style.SUCCESS(
                    f'Companies: {len(companies_results)} symbols processed (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 3: Industries
            if 'industries' not in skip_steps:
                self.stdout.write('\n=== STEP 3: INDUSTRIES ===')
                start_time = time.time()
                industries_results = service.import_industries_for_all_symbols()
                end_time = time.time()
                
                total_mappings = sum(r.get('mappings_count', 0) for r in industries_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Industries: {len(industries_results)} symbols, {total_mappings} mappings (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 4: Shareholders
            if 'shareholders' not in skip_steps:
                self.stdout.write('\n=== STEP 4: SHAREHOLDERS ===')
                start_time = time.time()
                shareholders_results = service.import_shareholders_for_all_symbols()
                end_time = time.time()
                
                total_shareholders = sum(r.get('shareholders_count', 0) for r in shareholders_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Shareholders: {len(shareholders_results)} symbols, {total_shareholders} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 5: Officers
            if 'officers' not in skip_steps:
                self.stdout.write('\n=== STEP 5: OFFICERS ===')
                start_time = time.time()
                officers_results = service.import_officers_for_all_symbols()
                end_time = time.time()
                
                total_officers = sum(r.get('officers_count', 0) for r in officers_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Officers: {len(officers_results)} symbols, {total_officers} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 6: Events
            if 'events' not in skip_steps:
                self.stdout.write('\n=== STEP 6: EVENTS ===')
                start_time = time.time()
                events_results = service.import_events_for_all_symbols()
                end_time = time.time()
                
                total_events = sum(r.get('events_count', 0) for r in events_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Events: {len(events_results)} symbols, {total_events} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            # Step 7: Sub Companies
            if 'sub_companies' not in skip_steps:
                self.stdout.write('\n=== STEP 7: SUB COMPANIES ===')
                start_time = time.time()
                sub_companies_results = service.import_sub_companies_for_all_symbols()
                end_time = time.time()
                
                total_sub_companies = sum(r.get('sub_companies_count', 0) for r in sub_companies_results)
                self.stdout.write(self.style.SUCCESS(
                    f'Sub Companies: {len(sub_companies_results)} symbols, {total_sub_companies} total (Time: {end_time-start_time:.1f}s)'
                ))
            
            total_end_time = time.time()
            
            self.stdout.write('\n=== COMPLETE PIPELINE SUMMARY ===')
            self.stdout.write(f'Total execution time: {total_end_time-total_start_time:.1f} seconds')
            self.stdout.write(f'Steps completed: {7 - len(skip_steps)}/7')
            self.stdout.write('Complete import pipeline finished successfully!')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during complete import: {e}')
            )
            raise e