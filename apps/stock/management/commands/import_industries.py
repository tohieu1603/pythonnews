from django.core.management.base import BaseCommand
from apps.stock.services.vnstock_import_service import VnstockImportService


class Command(BaseCommand):
    help = 'Import industries from vnstock và tạo quan hệ N-N với symbols'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of symbols to process (for testing)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting industry import (limit: {limit})')
        )
        
        service = VnstockImportService(per_symbol_sleep=0.1)
        
        try:
            results = service.import_industries_for_symbols()
            
            self.stdout.write(
                self.style.SUCCESS(f'Imported {len(results)} industry-symbol relationships')
            )
            
            # Show summary
            total_relationships = len(results)
            unique_symbols = len(set(r.get('symbol') for r in results))
            unique_industries = len(set(r.get('industry_name') for r in results))
            
            self.stdout.write('Summary:')
            self.stdout.write(f'  Total relationships: {total_relationships}')
            self.stdout.write(f'  Unique symbols: {unique_symbols}')
            self.stdout.write(f'  Unique industries: {unique_industries}')
            
            # Show sample relationships
            if results:
                self.stdout.write('\nSample relationships:')
                for r in results[:10]:
                    self.stdout.write(f'  {r.get("symbol")} -> {r.get("industry_name")} ({r.get("industry_code")})')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during industry import: {e}')
            )
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('Industry import completed successfully!')
        )