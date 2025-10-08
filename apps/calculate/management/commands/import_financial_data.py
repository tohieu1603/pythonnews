# apps/calculate/management/commands/import_financial_data.py
from django.core.management.base import BaseCommand
from apps.calculate.services.financial_import_service import FinancialImportService


class Command(BaseCommand):
    help = 'Import financial data (cash flow, income statement, balance sheet, ratios) từ vnstock'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Import cho symbol cụ thể (e.g., VTO)',
        )
        parser.add_argument(
            '--symbols',
            nargs='+',
            help='Import cho list symbols (e.g., VTO ACB FPT)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Import cho tất cả symbols trong database',
        )

    def handle(self, *args, **options):
        service = FinancialImportService()
        
        symbol = options.get('symbol')
        symbols = options.get('symbols')
        import_all = options.get('all')
        
        if symbol:
            self.stdout.write(f"Importing financial data for symbol: {symbol}")
            results = service.import_all_financial_data_for_symbol(symbol)
            self._print_results({symbol: results})
            
        elif symbols:
            self.stdout.write(f"Importing financial data for symbols: {', '.join(symbols)}")
            results = service.import_financial_data_for_symbols(symbols)
            self._print_bulk_results(results)
            
        elif import_all:
            self.stdout.write("Importing financial data for all symbols in database")
            results = service.import_all_symbols_financial_data()
            self._print_bulk_results(results)
            
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify --symbol, --symbols, or --all"
                )
            )
    
    def _print_results(self, results):
        """Print results cho single symbol import"""
        for symbol, data in results.items():
            self.stdout.write(
                self.style.SUCCESS(f"\n=== Results for {symbol} ===")
            )
            self.stdout.write(f"Cash Flow records: {data['cash_flow']}")
            self.stdout.write(f"Income Statement records: {data['income_statement']}")
            self.stdout.write(f"Balance Sheet records: {data['balance_sheet']}")
            self.stdout.write(f"Ratio records: {data['ratio']}")
    
    def _print_bulk_results(self, results):
        """Print results cho bulk import"""
        self.stdout.write(
            self.style.SUCCESS("\n=== Bulk Import Results ===")
        )
        self.stdout.write(f"Processed symbols: {results['processed_symbols']}")
        self.stdout.write(f"Total Cash Flow records: {results['cash_flow']}")
        self.stdout.write(f"Total Income Statement records: {results['income_statement']}")
        self.stdout.write(f"Total Balance Sheet records: {results['balance_sheet']}")
        self.stdout.write(f"Total Ratio records: {results['ratio']}")
        
        if results['failed_symbols']:
            self.stdout.write(
                self.style.WARNING(f"Failed symbols: {', '.join(results['failed_symbols'])}")
            )