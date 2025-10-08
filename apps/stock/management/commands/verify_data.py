from django.core.management.base import BaseCommand
from apps.stock.models import Symbol, Company, Industry, Shareholder, Officer, Event
from django.db.models import Count, Q


class Command(BaseCommand):
    help = 'Verify imported data - check counts and relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detail',
            action='store_true',
            help='Show detailed breakdown by symbol'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='Check specific symbol (e.g., VTO)'
        )

    def handle(self, *args, **options):
        detail = options['detail']
        specific_symbol = options['symbol']
        
        self.stdout.write(
            self.style.SUCCESS('=== DATA VERIFICATION REPORT ===')
        )
        
        if specific_symbol:
            self._check_specific_symbol(specific_symbol)
        else:
            self._check_overall_counts()
            
            if detail:
                self._check_detailed_breakdown()

    def _check_specific_symbol(self, symbol_code):
        """Check specific symbol in detail"""
        self.stdout.write(f'\n=== SYMBOL: {symbol_code} ===')
        
        try:
            symbol = Symbol.objects.get(symbol=symbol_code)
            
            # Basic info
            self.stdout.write(f'Symbol ID: {symbol.id}')
            self.stdout.write(f'Full Name: {symbol.full_name}')
            self.stdout.write(f'Exchange: {symbol.exchange}')
            
            # Company
            if symbol.company:
                self.stdout.write(f'Company: {symbol.company.name} (ID: {symbol.company.id})')
            else:
                self.stdout.write(self.style.WARNING('Company: NOT LINKED'))
            
            # Industries
            industries = symbol.industries.all()
            self.stdout.write(f'Industries: {industries.count()}')
            for industry in industries:
                self.stdout.write(f'  - {industry.name} (ICB: {industry.icb_code})')
            
            # Shareholders
            shareholders = Shareholder.objects.filter(symbol=symbol)
            self.stdout.write(f'Shareholders: {shareholders.count()}')
            if shareholders.exists():
                for sh in shareholders[:3]:  # Show first 3
                    self.stdout.write(f'  - {sh.name}: {sh.ownership_percentage}%')
                if shareholders.count() > 3:
                    self.stdout.write(f'  ... and {shareholders.count() - 3} more')
            
            # Officers
            officers = Officer.objects.filter(symbol=symbol)
            self.stdout.write(f'Officers: {officers.count()}')
            if officers.exists():
                for officer in officers[:3]:  # Show first 3
                    self.stdout.write(f'  - {officer.name}: {officer.position}')
                if officers.count() > 3:
                    self.stdout.write(f'  ... and {officers.count() - 3} more')
            
            # Events
            events = Event.objects.filter(symbol=symbol)
            self.stdout.write(f'Events: {events.count()}')
            if events.exists():
                for event in events[:3]:  # Show first 3
                    self.stdout.write(f'  - {event.title} ({event.event_date})')
                if events.count() > 3:
                    self.stdout.write(f'  ... and {events.count() - 3} more')
                    
        except Symbol.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Symbol {symbol_code} not found'))

    def _check_overall_counts(self):
        """Check overall counts and statistics"""
        # Basic counts
        symbols_count = Symbol.objects.count()
        companies_count = Company.objects.count()
        industries_count = Industry.objects.count()
        shareholders_count = Shareholder.objects.count()
        officers_count = Officer.objects.count()
        events_count = Event.objects.count()
        
        self.stdout.write('\n=== OVERALL COUNTS ===')
        self.stdout.write(f'Symbols: {symbols_count:,}')
        self.stdout.write(f'Companies: {companies_count:,}')
        self.stdout.write(f'Industries: {industries_count:,}')
        self.stdout.write(f'Shareholders: {shareholders_count:,}')
        self.stdout.write(f'Officers: {officers_count:,}')
        self.stdout.write(f'Events: {events_count:,}')
        
        # Relationship stats
        symbols_with_company = Symbol.objects.filter(company__isnull=False).count()
        symbols_with_industries = Symbol.objects.filter(industries__isnull=False).distinct().count()
        symbols_with_shareholders = Symbol.objects.filter(shareholder__isnull=False).distinct().count()
        symbols_with_officers = Symbol.objects.filter(officer__isnull=False).distinct().count()
        symbols_with_events = Symbol.objects.filter(event__isnull=False).distinct().count()
        
        self.stdout.write('\n=== RELATIONSHIP COVERAGE ===')
        self.stdout.write(f'Symbols with Company: {symbols_with_company:,} / {symbols_count:,} ({symbols_with_company/symbols_count*100:.1f}%)')
        self.stdout.write(f'Symbols with Industries: {symbols_with_industries:,} / {symbols_count:,} ({symbols_with_industries/symbols_count*100:.1f}%)')
        self.stdout.write(f'Symbols with Shareholders: {symbols_with_shareholders:,} / {symbols_count:,} ({symbols_with_shareholders/symbols_count*100:.1f}%)')
        self.stdout.write(f'Symbols with Officers: {symbols_with_officers:,} / {symbols_count:,} ({symbols_with_officers/symbols_count*100:.1f}%)')
        self.stdout.write(f'Symbols with Events: {symbols_with_events:,} / {symbols_count:,} ({symbols_with_events/symbols_count*100:.1f}%)')
        
        # Industry mappings
        total_industry_mappings = Symbol.objects.filter(industries__isnull=False).count()
        self.stdout.write(f'Total Industry Mappings: {total_industry_mappings:,}')

    def _check_detailed_breakdown(self):
        """Show detailed breakdown by exchange and top symbols"""
        self.stdout.write('\n=== DETAILED BREAKDOWN ===')
        
        # By exchange
        exchanges = Symbol.objects.values('exchange').annotate(
            count=Count('id'),
            with_company=Count('id', filter=Q(company__isnull=False)),
            with_shareholders=Count('shareholder', distinct=True),
            with_officers=Count('officer', distinct=True),
            with_events=Count('event', distinct=True)
        ).order_by('-count')
        
        self.stdout.write('\n--- By Exchange ---')
        for exchange in exchanges:
            self.stdout.write(
                f"{exchange['exchange']}: {exchange['count']} symbols, "
                f"{exchange['with_company']} with company, "
                f"{exchange['with_shareholders']} with shareholders, "
                f"{exchange['with_officers']} with officers, "
                f"{exchange['with_events']} with events"
            )
        
        # Top symbols by data richness
        top_symbols = Symbol.objects.annotate(
            shareholders_count=Count('shareholder'),
            officers_count=Count('officer'),
            events_count=Count('event'),
            industries_count=Count('industries')
        ).filter(
            shareholders_count__gt=0,
            officers_count__gt=0
        ).order_by('-shareholders_count', '-officers_count')[:10]
        
        self.stdout.write('\n--- Top 10 Data-Rich Symbols ---')
        for symbol in top_symbols:
            self.stdout.write(
                f"{symbol.symbol}: {symbol.shareholders_count} shareholders, "
                f"{symbol.officers_count} officers, {symbol.events_count} events, "
                f"{symbol.industries_count} industries"
            )
        
        # Data quality checks
        self.stdout.write('\n=== DATA QUALITY CHECKS ===')
        
        # Symbols without company
        symbols_no_company = Symbol.objects.filter(company__isnull=True).count()
        if symbols_no_company > 0:
            self.stdout.write(self.style.WARNING(f'Symbols without company: {symbols_no_company}'))
        
        # Symbols without any data
        symbols_no_data = Symbol.objects.filter(
            company__isnull=True,
            industries__isnull=True,
            shareholder__isnull=True,
            officer__isnull=True,
            event__isnull=True
        ).distinct().count()
        
        if symbols_no_data > 0:
            self.stdout.write(self.style.ERROR(f'Symbols with NO data: {symbols_no_data}'))
        else:
            self.stdout.write(self.style.SUCCESS('All symbols have at least some data!'))