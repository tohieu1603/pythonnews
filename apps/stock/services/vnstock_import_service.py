import time
from typing import Any, Dict, List, Optional
import pandas as pd
from django.db import transaction
from vnstock import Listing, Company

from apps.stock.models import Symbol
from apps.stock.repositories import repositories as repo
from apps.stock.utils.safe import safe_decimal, safe_int, safe_str, to_datetime
from apps.stock.services.cache_service import VNStockCacheService
from apps.stock.services.rate_limiter import get_rate_limiter
from apps.stock.utils.pandas_compat import suppress_pandas_warnings

suppress_pandas_warnings()


class VnstockImportService:
    """Service chuyên dụng để import dữ liệu từ vnstock vào database"""

    def __init__(self, per_symbol_sleep: float = 0.5): 
        self.per_symbol_sleep = per_symbol_sleep
        self.listing = Listing()
        self.cache_service = VNStockCacheService()
        self.rate_limiter = get_rate_limiter()

    def import_all_complete(self, exchange: str = "HSX", force_update: bool = False) -> Dict[str, Any]:
        """
        Import ALL stock data (symbols, companies, industries, shareholders, officers, events, sub_companies)
        for all symbols with detailed logging for each table.

        Args:
            exchange: Exchange to import (HSX, HNX, UPCOM)
            force_update: If False (default), skip symbols that already have data.
                         If True, re-import all symbols (to get latest data from vnstock).
        """
        from apps.stock.models import Company, ShareHolder, Officers, Events, SubCompany

        mode_text = "FORCE UPDATE MODE" if force_update else "RESUME MODE"

        result = {
            "exchange": exchange,
            "mode": mode_text,
            "total_symbols": 0,
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_companies": 0,
            "total_industries": 0,
            "total_shareholders": 0,
            "total_officers": 0,
            "total_events": 0,
            "total_sub_companies": 0,
            "errors": [],
            "details": []
        }

        print(f"\n{'='*60}")
        print(f"STOCK IMPORT - {mode_text}")
        print(f"Exchange: {exchange}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Import Symbols
            print(f"[1/7] → Importing Symbols from {exchange}...", end=" ")
            symbols_result = self.import_all_symbols_from_vnstock(exchange)
            result["total_symbols"] = len(symbols_result)
            print(f"✓ SUCCESS ({len(symbols_result)} symbols)")

            symbols = Symbol.objects.all().order_by('name')

            if not force_update:
                symbols_to_process = []
                for symbol in symbols:
                    has_company = hasattr(symbol, 'company') and symbol.company is not None
                    has_shareholders = has_company and ShareHolder.objects.filter(company=symbol.company).exists()
                    has_officers = has_company and Officers.objects.filter(company=symbol.company).exists()
                    has_events = has_company and Events.objects.filter(company=symbol.company).exists()
                    has_subs = has_company and SubCompany.objects.filter(company=symbol.company).exists()

                    # Process if missing any data
                    if not (has_company and has_shareholders and has_officers and has_events and has_subs):
                        symbols_to_process.append(symbol)

                symbols = symbols_to_process
                print(f"  ℹ Resume mode: {len(symbols)} symbols need processing\n")
            else:
                print(f"  ℹ Force update: Processing all {symbols.count()} symbols\n")

            # Step 2: Import Companies
            print(f"[2/7] → Importing Companies...", end=" ")
            companies_result = self.import_companies_from_vnstock(exchange)
            result["total_companies"] = len(companies_result)
            print(f"✓ SUCCESS ({len(companies_result)} companies)")

            # Step 3: Import Industries
            print(f"[3/7] → Importing Industries...", end=" ")
            industries_result = self.import_industries_for_symbols()
            result["total_industries"] = len(industries_result)
            print(f"✓ SUCCESS ({len(industries_result)} mappings)")

            # Step 4-7: Import related data for each symbol
            total_symbols = len(symbols)
            for idx, symbol in enumerate(symbols, 1):
                symbol_detail = {
                    "symbol": symbol.name,
                    "success": False,
                    "shareholders": 0,
                    "officers": 0,
                    "events": 0,
                    "sub_companies": 0,
                    "errors": []
                }

                print(f"\n[{idx}/{total_symbols}] Processing: {symbol.name}")

                try:
                    if not hasattr(symbol, 'company') or symbol.company is None:
                        print(f"  ⊘ SKIPPED: No company data")
                        symbol_detail["errors"].append("No company data")
                        result["symbols_failed"] += 1
                        continue

                    # Import Shareholders
                    print(f"  → Importing Shareholders...", end=" ")
                    sh_result = self._import_shareholders_for_symbol(symbol)
                    symbol_detail["shareholders"] = sh_result.get("count", 0)
                    result["total_shareholders"] += symbol_detail["shareholders"]
                    print(f"✓ SUCCESS ({symbol_detail['shareholders']} records)")

                    # Import Officers
                    print(f"  → Importing Officers...", end=" ")
                    off_result = self._import_officers_for_symbol(symbol)
                    symbol_detail["officers"] = off_result.get("count", 0)
                    result["total_officers"] += symbol_detail["officers"]
                    print(f"✓ SUCCESS ({symbol_detail['officers']} records)")

                    # Import Events
                    print(f"  → Importing Events...", end=" ")
                    evt_result = self._import_events_for_symbol(symbol)
                    symbol_detail["events"] = evt_result.get("count", 0)
                    result["total_events"] += symbol_detail["events"]
                    print(f"✓ SUCCESS ({symbol_detail['events']} records)")

                    # Import Sub Companies
                    print(f"  → Importing Sub Companies...", end=" ")
                    sub_result = self._import_sub_companies_for_symbol(symbol)
                    symbol_detail["sub_companies"] = sub_result.get("count", 0)
                    result["total_sub_companies"] += symbol_detail["sub_companies"]
                    print(f"✓ SUCCESS ({symbol_detail['sub_companies']} records)")

                    symbol_detail["success"] = True
                    result["symbols_processed"] += 1
                    print(f"  ✓ COMPLETED: All tables imported successfully")

                except Exception as e:
                    error_msg = f"Import error: {str(e)}"
                    symbol_detail["errors"].append(error_msg)
                    result["symbols_failed"] += 1
                    print(f"  ✗ FAILED: {error_msg}")

                finally:
                    result["details"].append(symbol_detail)
                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)

            # Final summary
            print(f"\n{'='*60}")
            print(f"STOCK IMPORT COMPLETE SUMMARY")
            print(f"{'='*60}")
            print(f"Mode:                 {mode_text}")
            print(f"Exchange:             {exchange}")
            print(f"Total Symbols:        {result['total_symbols']}")
            print(f"Processed:            {result['symbols_processed']}")
            print(f"Failed:               {result['symbols_failed']}")
            print(f"Companies:            {result['total_companies']} records")
            print(f"Industries:           {result['total_industries']} mappings")
            print(f"Shareholders:         {result['total_shareholders']} records")
            print(f"Officers:             {result['total_officers']} records")
            print(f"Events:               {result['total_events']} records")
            print(f"Sub Companies:        {result['total_sub_companies']} records")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            error_msg = f"Import failed: {str(e)}"
            result["errors"].append(error_msg)
            print(f"\n✗ IMPORT FAILED: {error_msg}")
            return result

    def _handle_rate_limit_error(self, error, symbol_name=None):
        """Handle rate limit errors gracefully"""
        error_msg = str(error)
        print(f"Rate limit error for {symbol_name or 'unknown'}: {error_msg}")
        
        if "36 giây" in error_msg or "36s" in error_msg:
            wait_time = 40  
        elif "30 giây" in error_msg or "30s" in error_msg:
            wait_time = 35
        elif "60 giây" in error_msg or "60s" in error_msg:
            wait_time = 65
        else:
            wait_time = 60  
            
        print(f"Waiting {wait_time} seconds before retry...")
        time.sleep(wait_time)
        return wait_time

    def _safe_api_call(self, api_func, symbol_name=None, max_retries=3):
        """Safely call API with retry mechanism for rate limits"""
        for attempt in range(max_retries):
            try:
                result = api_func()
                return result 
            except Exception as e:
                error_msg = str(e)
                if "rate limit" in error_msg.lower() or "quá nhiều request" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = self._handle_rate_limit_error(e, symbol_name)
                        print(f"Retrying API call for {symbol_name} (attempt {attempt + 2}/{max_retries})")
                        continue
                    else:
                        print(f"Failed after {max_retries} attempts for {symbol_name}: {error_msg}")
                        return None
                else:
                    print(f"Non-rate-limit error for {symbol_name}: {error_msg}")
                    return None
        return None
    
    def import_all_symbols_from_vnstock(self, exchange: str = "HSX") -> List[Dict[str, Any]]:
        """
        Import tất cả symbols từ vnstock - gọi 1 lần duy nhất rồi bulk import
        """
        print(f"Starting import symbols from vnstock - exchange: {exchange}")
        results = []
        
        try:
            all_symbols_df = self._fetch_all_symbols_from_vnstock(exchange)
            if all_symbols_df is None or all_symbols_df.empty:
                print("Failed to fetch symbols from vnstock")
                return results
            
            symbols_df = self._filter_symbols_by_exchange(all_symbols_df, exchange)
            if symbols_df.empty:
                print(f"No symbols found for exchange {exchange}")
                return results
            
            results = self._bulk_import_symbols(symbols_df, exchange)
            print(f"Import completed! {len(results)} symbols imported successfully")
            return results
            
        except Exception as e:
            print(f"Error in import_all_symbols_from_vnstock: {e}")
            return results
    
    def _fetch_all_symbols_from_vnstock(self, exchange: str = "HSX"):
        """Lấy tất cả symbols từ vnstock với cache"""
        print(f"Fetching all symbols from vnstock for {exchange}...")

        symbols_df = self.cache_service.fetch_symbols_with_cache(exchange)

        if symbols_df is not None and not symbols_df.empty:
            print(f"Got {len(symbols_df)} symbols for {exchange}")
            return symbols_df

        return None
    
    def _filter_symbols_by_exchange(self, all_symbols_df, exchange: str):
        """Filter symbols theo exchange"""
        print(f"Filtering for exchange: {exchange}")
        
        for col_name in ['exchange', 'Exchange', 'EXCHANGE']:
            if col_name in all_symbols_df.columns:
                filtered_df = all_symbols_df[all_symbols_df[col_name].str.upper() == exchange.upper()]
                print(f"Filtered by {col_name}: {len(filtered_df)} symbols")
                return filtered_df
        
        if exchange.upper() == "HSX" and 'symbol' in all_symbols_df.columns:
            filtered_df = all_symbols_df[all_symbols_df['symbol'].str.len() <= 4]
            print(f"Filtered HSX by symbol length: {len(filtered_df)} symbols")
            return filtered_df
        
        return all_symbols_df
    
    def _bulk_import_symbols(self, symbols_df, exchange: str) -> List[Dict[str, Any]]:
        """Bulk import symbols vào DB"""
        print(f"Bulk importing {len(symbols_df)} symbols...")
        results = []
        batch_size = 50
        total_imported = 0
        
        for i in range(0, len(symbols_df), batch_size):
            batch_df = symbols_df.iloc[i:i+batch_size]
            batch_results = self._import_symbol_batch(batch_df, exchange)
            
            results.extend(batch_results)
            total_imported += len(batch_results)
            print(f"Batch {i//batch_size + 1}: Imported {len(batch_results)} symbols (Total: {total_imported})")
            
            if self.per_symbol_sleep > 0:
                time.sleep(self.per_symbol_sleep * 5)
        
        return results
    
    def _import_symbol_batch(self, batch_df, exchange: str) -> List[Dict[str, Any]]:
        """Import 1 batch symbols"""
        results = []
        
        with transaction.atomic():
            for _, row in batch_df.iterrows():
                try:
                    symbol_name = safe_str(
                        row.get('symbol') or row.get('ticker') or 
                        row.get('Symbol') or row.get('SYMBOL')
                    )
                    if not symbol_name:
                        continue
                    
                    repo.upsert_symbol(
                        symbol_name, 
                        defaults={'exchange': exchange}
                    )
                    
                    results.append({
                        'symbol': symbol_name,
                        'exchange': exchange,
                        'status': 'created'
                    })
                    
                except Exception as e:
                    print(f"Error importing symbol {symbol_name}: {e}")
                    continue
        
        return results
    
    def import_companies_from_vnstock(self, exchange: str = "HSX") -> List[Dict[str, Any]]:
        """
        Import tất cả companies từ vnstock và cập nhật company_id ở Symbol
        """
        print(f"Starting import companies from vnstock - exchange: {exchange}")
        results = []
        
        try:
            # Lấy danh sách symbols đã có trong DB
            symbols_queryset = repo.qs_all_symbols()
            if not symbols_queryset.exists():
                print("No symbols found in database. Please import symbols first.")
                return results
            
            print(f"Found {symbols_queryset.count()} symbols in database")
            
            total_processed = 0
            companies_created = 0
            
            for symbol in symbols_queryset:
                try:
                    print(f"Processing symbol: {symbol.name}")
                    
                    # Lấy thông tin company từ vnstock
                    company_info = self._fetch_company_info_from_vnstock(symbol.name)
                    if not company_info:
                        print(f"No company info found for symbol: {symbol.name}")
                        continue
                    
                    company = self._upsert_company_from_info(company_info)
                    
                    symbol.company = company
                    symbol.save()
                    
                    results.append({
                        'symbol': symbol.name,
                        'company': company.company_name,
                        'status': 'processed'
                    })
                    
                    companies_created += 1
                    total_processed += 1
                    
                    print(f"Updated symbol {symbol.name} with company: {company.company_name}")
                    
                except Exception as e:
                    print(f"Error processing symbol {symbol.name}: {e}")
                    continue
                
                if self.per_symbol_sleep > 0:
                    time.sleep(self.per_symbol_sleep)
            
            print(f"Import companies completed! Processed: {total_processed}, Companies: {companies_created}")
            return results
            
        except Exception as e:
            print(f"Error in import_companies_from_vnstock: {e}")
            return results
    
    def _fetch_company_info_from_vnstock(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin company từ vnstock theo symbol sử dụng bundle approach với cache"""
        try:
            bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol)
            
            if not ok or not bundle:
                print(f"Failed to fetch bundle for {symbol}")
                return None
            
            profile_df = bundle.get("profile_df")
            company_name = (
                safe_str(profile_df.iloc[0].get("company_name"))
                if profile_df is not None and not profile_df.empty
                else symbol
            )
            
            overview_df = bundle.get("overview_df_TCBS")
            if overview_df is None or overview_df.empty:
                overview_df = bundle.get("overview_df_VCI")
            
            if overview_df is None or overview_df.empty:
                print(f"No overview data found for {symbol}")
                return None
            
            overview_data = overview_df.iloc[0]
            
            overview_df_vci = bundle.get("overview_df_VCI")
            if overview_df_vci is not None and not overview_df_vci.empty:
                vci_data = overview_df_vci.iloc[0]
                company_profile = safe_str(vci_data.get("company_profile"))
                history = safe_str(vci_data.get("history"))
                fin_ratio_share = safe_int(vci_data.get("financial_ratio_issue_share"))
                charter_cap = safe_int(vci_data.get("charter_capital"))
            else:
                company_profile = ""
                history = ""
                fin_ratio_share = None
                charter_cap = None
            
            company_info = {
                'company_name': company_name,
                'company_profile': company_profile,
                'history': history,
                'issue_share': safe_int(overview_data.get("issue_share")),
                'financial_ratio_issue_share': fin_ratio_share,
                'charter_capital': charter_cap,
                'outstanding_share': safe_int(overview_data.get("outstanding_share", 0)),
                'foreign_percent': safe_decimal(overview_data.get("foreign_percent", 0)),
                'established_year': safe_int(overview_data.get("established_year", 0)),
                'no_employees': safe_int(overview_data.get("no_employees", 0)),
                'stock_rating': safe_decimal(overview_data.get("stock_rating"), None),
                'website': safe_str(overview_data.get("website", "")),
                'delta_in_week': safe_decimal(overview_data.get("delta_in_week", 0)),
                'delta_in_month': safe_decimal(overview_data.get("delta_in_month", 0)),
                'delta_in_year': safe_decimal(overview_data.get("delta_in_year", 0)),
            }
            
            return company_info
            
        except Exception as e:
            print(f"Error fetching company info for {symbol}: {e}")
            return None
    
    def _upsert_company_from_info(self, company_info: Dict[str, Any]) -> Company:
        """Upsert company vào database"""
        company_name = company_info.get('company_name')
        
        defaults = {k: v for k, v in company_info.items() if k != 'company_name'}
        
        company = repo.upsert_company(company_name, defaults)
        return company
    
    def import_companies_for_symbols(self) -> List[Dict[str, Any]]:
        """
        Import company data cho tất cả symbols có trong database
        """
        print("Starting import companies for symbols...")
        results = []
        
        # Lấy tất cả symbols từ database
        symbols = Symbol.objects.all()
        print(f"Found {symbols.count()} symbols in database")
        
        for symbol in symbols:
            try:
                print(f"Processing company for symbol: {symbol.name}")
                
                company_client = Company(symbol=symbol.name, source="TCBS")
                
                def get_profile(client=company_client):
                    return client.profile()
                
                profile_data = self._safe_api_call(get_profile, symbol.name)
                
                if profile_data is None or profile_data.empty:
                    print(f"No company profile found for {symbol.name}")
                    continue
                
                company_data = profile_data.iloc[0]
                
                with transaction.atomic():
                    company_name = safe_str(company_data.get('companyName') or company_data.get('company_name'))
                    if not company_name:
                        company_name = symbol.name + " Company"
                    
                    company_obj = repo.upsert_company(
                        company_name,
                        defaults={
                            'company_profile': safe_str(company_data.get('companyProfile')),
                            'history': safe_str(company_data.get('history')),
                            'issue_share': safe_int(company_data.get('issueShare')),
                            'charter_capital': safe_int(company_data.get('charterCapital')),
                            'outstanding_share': safe_decimal(company_data.get('outstandingShare')),
                            'foreign_percent': safe_decimal(company_data.get('foreignPercent')),
                            'established_year': safe_int(company_data.get('establishedYear')),
                            'no_employees': safe_int(company_data.get('noEmployees')),
                            'website': safe_str(company_data.get('website')),
                        }
                    )
                    
                    symbol.company = company_obj
                    symbol.save()
                    
                    result = {
                        'symbol': symbol.name,
                        'company': company_name,
                        'status': 'updated'
                    }
                    results.append(result)
                    print(f"Updated company for symbol: {symbol.name}")
                
                if self.per_symbol_sleep > 0:
                    time.sleep(self.per_symbol_sleep)
                else:
                    time.sleep(1.0) 
                
            except Exception as e:
                print(f"Error importing company for {symbol.name}: {e}")
                continue
                
            if self.per_symbol_sleep > 0:
                time.sleep(self.per_symbol_sleep)
        
        print(f"Company import completed! {len(results)} companies processed")
        return results
    
    def import_industries_for_symbols(self) -> List[Dict[str, Any]]:
        """
        Import industry data và tạo quan hệ N-N với symbols theo cách đúng
        """
        print("Starting import industries for symbols...")
        results = []
        
        try:
            print("Fetching industries and symbols mapping from vnstock...")

            industries_icb_df, symbols_by_industries_df = self.cache_service.fetch_industries_with_cache()
            
            if industries_icb_df is None or industries_icb_df.empty:
                print("No industries_icb data found")
                return results
                
            if symbols_by_industries_df is None or symbols_by_industries_df.empty:
                print("No symbols_by_industries data found")  
                return results
            
            print(f"Found {len(industries_icb_df)} industries and {len(symbols_by_industries_df)} symbol mappings")
            
            print("Importing industries to database...")
            industries_imported = 0
            for _, row in industries_icb_df.iterrows():
                try:
                    industry_id = safe_int(row.get('icb_code'))
                    industry_name = safe_str(row.get('icb_name'))
                    level = safe_int(row.get('level'))
                    
                    if industry_id and industry_name:
                        repo.upsert_industry({
                            'id': industry_id,
                            'name': industry_name,
                            'level': level
                        })
                        industries_imported += 1
                        
                except Exception as e:
                    print(f"Error importing industry {row}: {e}")
                    continue
            
            print(f"Imported {industries_imported} industries")
            
            print("Creating Symbol-Industry relationships...")
            symbols = Symbol.objects.all()
            relationships_created = 0
            
            for symbol in symbols:
                try:
                    symbol_name = symbol.name.upper()
                    try:
                        sym_rows = symbols_by_industries_df[
                            symbols_by_industries_df["symbol"].astype(str).str.upper() == symbol_name
                        ]
                    except Exception:
                        sym_rows = symbols_by_industries_df[
                            symbols_by_industries_df.get("symbol") == symbol.name
                        ]
                    
                    if sym_rows.empty:
                        continue
                    
                    first_row = sym_rows.iloc[0]
                    
                    icb_codes = []
                    for col in ("icb_code1", "icb_code2", "icb_code3", "icb_code4"):
                        val = first_row.get(col)
                        if pd.isna(val) if hasattr(pd, 'isna') else val is None:
                            continue
                        code_str = str(int(val)) if isinstance(val, (int, float)) and not pd.isna(val) else str(val).strip()
                        if code_str and code_str not in icb_codes:
                            icb_codes.append(code_str)
                    
                    if not icb_codes:
                        continue
                    
                    for code in icb_codes:
                        try:
                            code_series = industries_icb_df["icb_code"].astype(str).str.strip()
                            match = industries_icb_df[code_series == code]
                            
                            if not match.empty:
                                industry_row = match.iloc[0]
                                industry = repo.upsert_industry({
                                    'id': safe_int(industry_row.get('icb_code')),
                                    'name': safe_str(industry_row.get('icb_name')),
                                    'level': safe_int(industry_row.get('level'))
                                })
                                
                                repo.upsert_symbol_industry(symbol, industry)
                                relationships_created += 1
                                
                                results.append({
                                    'symbol': symbol.name,
                                    'industry_code': code,
                                    'industry_name': industry.name,
                                    'status': 'linked'
                                })
                                
                        except Exception as e:
                            print(f"Error linking {symbol.name} to industry {code}: {e}")
                            continue
                    
                    if icb_codes:
                        print(f"Linked {symbol.name} to {len(icb_codes)} industries: {icb_codes}")
                        
                except Exception as e:
                    print(f"Error processing symbol {symbol.name}: {e}")
                    continue
            
            print(f"Industry import completed! Created {relationships_created} Symbol-Industry relationships")
            return results
            
        except Exception as e:
            print(f"Error in import_industries_for_symbols: {e}")
            return results
    
    def import_shareholders_for_all_symbols(self) -> List[Dict[str, Any]]:
        """
        Import shareholders cho tất cả symbols có company - optimized version
        """
        print("Starting import shareholders for all symbols...")
        results = []
        
        symbols = Symbol.objects.filter(company__isnull=False).select_related('company')
        total_symbols = symbols.count()
        print(f"Processing {total_symbols} symbols with companies...")
        
        processed = 0
        batch_size = 20 
        
        for i in range(0, total_symbols, batch_size):
            batch_symbols = symbols[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}: {len(batch_symbols)} symbols")
            
            for symbol in batch_symbols:
                try:
                    symbol_name = symbol.name

                    # Sử dụng cache để lấy bundle data
                    bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
                    if not bundle:
                        print(f"No bundle data for {symbol.name}")
                        continue

                    shareholders_df = bundle.get("shareholders_df")
                    if shareholders_df is None or shareholders_df.empty:
                        print(f"No shareholders data for {symbol.name}")
                        continue
                    
                    shareholder_rows = []
                    for _, row in shareholders_df.iterrows():
                        shareholder_row = {
                            'share_holder': safe_str(row.get('shareholder') or row.get('share_holder') or row.get('name')),
                            'quantity': safe_int(row.get('quantity') or row.get('shares')),
                            'share_own_percent': safe_decimal(row.get('percentage') or row.get('share_own_percent') or row.get('ownership')),
                            'update_date': to_datetime(row.get('date') or row.get('update_date'))
                        }
                        shareholder_rows.append(shareholder_row)
                    
                    if shareholder_rows:
                        repo.upsert_shareholders(symbol.company, shareholder_rows)
                        
                        results.append({
                            'symbol': symbol.name,
                            'shareholders_count': len(shareholder_rows),
                            'status': 'imported'
                        })
                        
                        print(f"✓ {symbol.name}: {len(shareholder_rows)} shareholders")
                    
                    processed += 1
                    
                    self.rate_limiter.wait_if_needed(f"processing_{symbol.name}")
                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)
                    else:
                        time.sleep(0.5)  
                    
                except Exception as e:
                    print(f"✗ Error with {symbol.name}: {e}")
                    continue
            
        print(f"Shareholders import completed! Processed {processed}/{total_symbols} symbols, {len(results)} successful")
        return results
    
    def import_officers_for_all_symbols(self) -> List[Dict[str, Any]]:
        """
        Import officers cho tất cả symbols có company - optimized version with cache
        """
        print("Starting import officers for all symbols...")
        results = []

        symbols = Symbol.objects.filter(company__isnull=False).select_related('company')
        total_symbols = symbols.count()
        print(f"Processing {total_symbols} symbols with companies...")

        processed = 0
        batch_size = 20 
        
        for i in range(0, total_symbols, batch_size):
            batch_symbols = symbols[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}: {len(batch_symbols)} symbols")
            
            for symbol in batch_symbols:
                try:
                    bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
                    if not bundle:
                        continue
                    
                    officers_df = bundle.get("officers_df")
                    if officers_df is None or officers_df.empty:
                        continue
                    
                    officer_rows = []
                    for _, row in officers_df.iterrows():
                        officer_row = {
                            'officer_name': safe_str(row.get('officer_name') or row.get('name')),
                            'officer_position': safe_str(row.get('officer_position') or row.get('position')),
                            'position_short_name': safe_str(row.get('position_short_name') or row.get('short_name')),
                            'officer_owner_percent': safe_decimal(row.get('officer_owner_percent') or row.get('ownership') or row.get('percentage'))
                        }
                        officer_rows.append(officer_row)
                    
                    if officer_rows:
                        repo.upsert_officers(symbol.company, officer_rows)
                        
                        results.append({
                            'symbol': symbol.name,
                            'officers_count': len(officer_rows),
                            'status': 'imported'
                        })
                        
                        print(f"✓ {symbol.name}: {len(officer_rows)} officers")
                    
                    processed += 1
                    
                    self.rate_limiter.wait_if_needed(f"processing_{symbol.name}")
                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)
                    else:
                        time.sleep(0.5)  
                    
                except Exception as e:
                    print(f"✗ Error with {symbol.name}: {e}")
                    continue
            
        
        print(f"Officers import completed! Processed {processed}/{total_symbols} symbols, {len(results)} successful")
        return results
    
    def import_events_for_all_symbols(self) -> List[Dict[str, Any]]:
        """
        Import events cho tất cả symbols có company - optimized version with cache
        """
        print("Starting import events for all symbols...")
        results = []

        symbols = Symbol.objects.filter(company__isnull=False).select_related('company')
        total_symbols = symbols.count()
        print(f"Processing {total_symbols} symbols with companies...")

        processed = 0
        batch_size = 20  # Increased batch size
        
        for i in range(0, total_symbols, batch_size):
            batch_symbols = symbols[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}: {len(batch_symbols)} symbols")
            
            for symbol in batch_symbols:
                try:
                    bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
                    if not bundle:
                        continue
                    
                    events_df = bundle.get("events_df")
                    if events_df is None or events_df.empty:
                        continue
                    
                    event_rows = []
                    for _, row in events_df.iterrows():
                        event_row = {
                            'event_title': safe_str(row.get('event_title') or row.get('title')),
                            'public_date': to_datetime(row.get('public_date') or row.get('date')),
                            'issue_date': to_datetime(row.get('issue_date')),
                            'source_url': safe_str(row.get('source_url') or row.get('url'))
                        }
                        event_rows.append(event_row)
                    
                    if event_rows:
                        repo.upsert_events(symbol.company, event_rows)
                        
                        results.append({
                            'symbol': symbol.name,
                            'events_count': len(event_rows),
                            'status': 'imported'
                        })
                        
                        print(f"✓ {symbol.name}: {len(event_rows)} events")
                    
                    processed += 1
                    
                    self.rate_limiter.wait_if_needed(f"processing_{symbol.name}")
                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)
                    else:
                        time.sleep(0.5)
                    
                except Exception as e:
                    print(f"✗ Error with {symbol.name}: {e}")
                    continue
            
        print(f"Events import completed! Processed {processed}/{total_symbols} symbols, {len(results)} successful")
        return results

    def import_sub_companies_for_all_symbols(self) -> List[Dict[str, Any]]:
        """
        Import sub companies (subsidiaries) cho tất cả symbols - optimized with cache
        """
        print("Starting import sub companies for all symbols (cache approach)...")
        results = []

        symbols = Symbol.objects.filter(company__isnull=False).select_related('company')
        total_symbols = symbols.count()

        if not total_symbols:
            print("No symbols with companies found")
            return results

        print(f"Found {total_symbols} symbols with companies")

        processed = 0
        batch_size = 25  
        
        for i in range(0, total_symbols, batch_size):
            batch_symbols = symbols[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}: {len(batch_symbols)} symbols")
            
            for symbol in batch_symbols:
                try:
                    bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
                    if not bundle:
                        continue
                    
                    subsidiaries_df = bundle.get("subsidiaries")
                    if subsidiaries_df is None or subsidiaries_df.empty:
                        continue
                    
                    sub_company_rows = []
                    for _, row in subsidiaries_df.iterrows():
                        sub_company_row = {
                            'company_name': safe_str(row.get('sub_company_name') or row.get('company_name') or row.get('name')),
                            'sub_own_percent': safe_decimal(row.get('sub_own_percent') or row.get('ownership_percentage') or row.get('percentage'))
                        }
                        sub_company_rows.append(sub_company_row)
                    
                    if sub_company_rows:
                        repo.upsert_sub_company(sub_company_rows, symbol.company)
                        
                        results.append({
                            'symbol': symbol.name,
                            'sub_companies_count': len(sub_company_rows),
                            'status': 'imported'
                        })
                        
                        print(f"✓ {symbol.name}: {len(sub_company_rows)} sub companies")
                    
                    processed += 1
                    
                    self.rate_limiter.wait_if_needed(f"processing_{symbol.name}")
                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)
                    else:
                        time.sleep(0.5) 
                    
                except Exception as e:
                    print(f"✗ Error with {symbol.name}: {e}")
                    continue
            
        print(f"Sub companies import completed! Processed {processed}/{total_symbols} symbols, {len(results)} successful")
        return results

    def _import_shareholders_for_symbol(self, symbol: Symbol) -> Dict[str, Any]:
        """Import shareholders for a single symbol"""
        result = {"symbol": symbol.name, "count": 0, "errors": []}

        try:
            if not hasattr(symbol, 'company') or symbol.company is None:
                return result

            bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
            if not ok or not bundle:
                return result

            shareholders_df = bundle.get("shareholders_df")
            if shareholders_df is None or shareholders_df.empty:
                return result

            shareholder_rows = []
            for _, row in shareholders_df.iterrows():
                shareholder_row = {
                    'share_holder': safe_str(row.get('shareholder') or row.get('share_holder') or row.get('name')),
                    'quantity': safe_int(row.get('quantity') or row.get('shares')),
                    'share_own_percent': safe_decimal(row.get('percentage') or row.get('share_own_percent') or row.get('ownership')),
                    'update_date': to_datetime(row.get('date') or row.get('update_date'))
                }
                shareholder_rows.append(shareholder_row)

            if shareholder_rows:
                repo.upsert_shareholders(symbol.company, shareholder_rows)
                result["count"] = len(shareholder_rows)

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _import_officers_for_symbol(self, symbol: Symbol) -> Dict[str, Any]:
        """Import officers for a single symbol"""
        result = {"symbol": symbol.name, "count": 0, "errors": []}

        try:
            if not hasattr(symbol, 'company') or symbol.company is None:
                return result

            bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
            if not ok or not bundle:
                return result

            officers_df = bundle.get("officers_df")
            if officers_df is None or officers_df.empty:
                return result

            officer_rows = []
            for _, row in officers_df.iterrows():
                officer_row = {
                    'officer_name': safe_str(row.get('officer_name') or row.get('name')),
                    'officer_position': safe_str(row.get('officer_position') or row.get('position')),
                    'position_short_name': safe_str(row.get('position_short_name') or row.get('short_name')),
                    'officer_owner_percent': safe_decimal(row.get('officer_owner_percent') or row.get('ownership') or row.get('percentage'))
                }
                officer_rows.append(officer_row)

            if officer_rows:
                repo.upsert_officers(symbol.company, officer_rows)
                result["count"] = len(officer_rows)

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _import_events_for_symbol(self, symbol: Symbol) -> Dict[str, Any]:
        """Import events for a single symbol"""
        result = {"symbol": symbol.name, "count": 0, "errors": []}

        try:
            if not hasattr(symbol, 'company') or symbol.company is None:
                return result

            bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
            if not ok or not bundle:
                return result

            events_df = bundle.get("events_df")
            if events_df is None or events_df.empty:
                return result

            event_rows = []
            for _, row in events_df.iterrows():
                event_row = {
                    'event_title': safe_str(row.get('event_title') or row.get('title')),
                    'public_date': to_datetime(row.get('public_date') or row.get('date')),
                    'issue_date': to_datetime(row.get('issue_date')),
                    'source_url': safe_str(row.get('source_url') or row.get('url'))
                }
                event_rows.append(event_row)

            if event_rows:
                repo.upsert_events(symbol.company, event_rows)
                result["count"] = len(event_rows)

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _import_sub_companies_for_symbol(self, symbol: Symbol) -> Dict[str, Any]:
        """Import sub companies for a single symbol"""
        result = {"symbol": symbol.name, "count": 0, "errors": []}

        try:
            if not hasattr(symbol, 'company') or symbol.company is None:
                return result

            bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
            if not ok or not bundle:
                return result

            subsidiaries_df = bundle.get("subsidiaries")
            if subsidiaries_df is None or subsidiaries_df.empty:
                return result

            sub_company_rows = []
            for _, row in subsidiaries_df.iterrows():
                sub_company_row = {
                    'company_name': safe_str(row.get('sub_company_name') or row.get('company_name') or row.get('name')),
                    'sub_own_percent': safe_decimal(row.get('sub_own_percent') or row.get('ownership_percentage') or row.get('percentage'))
                }
                sub_company_rows.append(sub_company_row)

            if sub_company_rows:
                repo.upsert_sub_company(sub_company_rows, symbol.company)
                result["count"] = len(sub_company_rows)

        except Exception as e:
            result["errors"].append(str(e))

        return result

