"""
VNStock API caching service để tối ưu hoá hiệu năng
"""
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
import pandas as pd
from apps.stock.clients.vnstock_client import VNStockClient
from apps.stock.utils.pandas_compat import suppress_pandas_warnings

# Suppress pandas warnings
suppress_pandas_warnings()


class VNStockCacheService:
    """
    Service quản lý cache cho VNStock API calls
    """

    # Cache TTL (time to live) trong giây - tăng thời gian cache để giảm API calls
    CACHE_TTL_SYMBOLS = 3 * 24 * 60 * 60  # 3 ngày cho danh sách symbols
    CACHE_TTL_COMPANY_BUNDLE = 24 * 60 * 60  # 24 giờ cho company bundle
    CACHE_TTL_INDUSTRIES = 7 * 24 * 60 * 60  # 7 ngày cho industries (ít thay đổi)

    def __init__(self):
        # Tăng wait time để tránh rate limit
        self.client = VNStockClient(max_retries=2, wait_seconds=45)

    def _get_cache_key(self, prefix: str, symbol: str = None, **kwargs) -> str:
        """Tạo cache key duy nhất"""
        if symbol:
            key_data = f"{prefix}:{symbol.upper()}"
        else:
            key_data = prefix

        # Thêm thông tin phụ nếu có
        if kwargs:
            key_data += ":" + hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()[:8]

        return f"vnstock_cache:{key_data}"

    def get_cached_symbols_list(self, exchange: str = "HSX") -> Optional[pd.DataFrame]:
        """Lấy danh sách symbols từ cache"""
        cache_key = self._get_cache_key("symbols_list", exchange=exchange)
        cached_data = cache.get(cache_key)

        if cached_data:
            try:
                return pd.DataFrame(cached_data)
            except Exception:
                cache.delete(cache_key)

        return None

    def set_cached_symbols_list(self, symbols_df: pd.DataFrame, exchange: str = "HSX") -> None:
        """Lưu danh sách symbols vào cache"""
        cache_key = self._get_cache_key("symbols_list", exchange=exchange)
        try:
            # Convert DataFrame to dict để cache
            cache_data = symbols_df.to_dict('records')
            cache.set(cache_key, cache_data, self.CACHE_TTL_SYMBOLS)
        except Exception as e:
            print(f"Error caching symbols list: {e}")

    def get_cached_company_bundle(self, symbol: str) -> Optional[Tuple[Dict[str, pd.DataFrame], bool]]:
        """Lấy company bundle từ cache"""
        cache_key = self._get_cache_key("company_bundle", symbol)
        cached_data = cache.get(cache_key)

        if cached_data:
            try:
                bundle = {}
                for key, data in cached_data['bundle'].items():
                    if data:
                        bundle[key] = pd.DataFrame(data)
                    else:
                        bundle[key] = pd.DataFrame()
                return bundle, cached_data['ok']
            except Exception:
                cache.delete(cache_key)

        return None

    def set_cached_company_bundle(self, symbol: str, bundle: Dict[str, pd.DataFrame], ok: bool) -> None:
        """Lưu company bundle vào cache"""
        cache_key = self._get_cache_key("company_bundle", symbol)
        try:
            # Convert DataFrames to dict để cache
            cache_data = {
                'bundle': {},
                'ok': ok,
                'timestamp': time.time()
            }

            for key, df in bundle.items():
                if df is not None and not df.empty:
                    cache_data['bundle'][key] = df.to_dict('records')
                else:
                    cache_data['bundle'][key] = None

            cache.set(cache_key, cache_data, self.CACHE_TTL_COMPANY_BUNDLE)
        except Exception as e:
            print(f"Error caching company bundle for {symbol}: {e}")

    def get_cached_industries_data(self) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
        """Lấy industries data từ cache"""
        cache_key = self._get_cache_key("industries_data")
        cached_data = cache.get(cache_key)

        if cached_data:
            try:
                industries_icb_df = pd.DataFrame(cached_data['industries_icb']) if cached_data['industries_icb'] else pd.DataFrame()
                symbols_by_industries_df = pd.DataFrame(cached_data['symbols_by_industries']) if cached_data['symbols_by_industries'] else pd.DataFrame()
                return industries_icb_df, symbols_by_industries_df
            except Exception:
                cache.delete(cache_key)

        return None

    def set_cached_industries_data(self, industries_icb_df: pd.DataFrame, symbols_by_industries_df: pd.DataFrame) -> None:
        """Lưu industries data vào cache"""
        cache_key = self._get_cache_key("industries_data")
        try:
            cache_data = {
                'industries_icb': industries_icb_df.to_dict('records') if not industries_icb_df.empty else None,
                'symbols_by_industries': symbols_by_industries_df.to_dict('records') if not symbols_by_industries_df.empty else None,
                'timestamp': time.time()
            }
            cache.set(cache_key, cache_data, self.CACHE_TTL_INDUSTRIES)
        except Exception as e:
            print(f"Error caching industries data: {e}")

    def fetch_symbols_with_cache(self, exchange: str = "HSX") -> pd.DataFrame:
        """Lấy symbols với cache"""
        # Thử lấy từ cache trước
        cached_df = self.get_cached_symbols_list(exchange)
        if cached_df is not None:
            print(f"Using cached symbols list for {exchange}: {len(cached_df)} symbols")
            return cached_df

        # Nếu không có cache, gọi API
        print(f"Fetching symbols list from API for {exchange}...")
        symbols_data = []

        try:
            for symbol_name, symbol_exchange in self.client.iter_all_symbols(exchange):
                symbols_data.append({
                    'symbol': symbol_name,
                    'exchange': symbol_exchange
                })
        except Exception as e:
            print(f"Error fetching symbols from API: {e}")
            return pd.DataFrame()

        symbols_df = pd.DataFrame(symbols_data)

        # Cache kết quả
        if not symbols_df.empty:
            self.set_cached_symbols_list(symbols_df, exchange)
            print(f"Cached {len(symbols_df)} symbols for {exchange}")

        return symbols_df

    def fetch_company_bundle_with_cache(self, symbol: str) -> Tuple[Dict[str, pd.DataFrame], bool]:
        """Lấy company bundle với cache"""
        # Thử lấy từ cache trước
        cached_result = self.get_cached_company_bundle(symbol)
        if cached_result is not None:
            print(f"Using cached company bundle for {symbol}")
            return cached_result

        # Nếu không có cache, gọi API
        print(f"Fetching company bundle from API for {symbol}...")
        bundle, ok = self.client.fetch_company_bundle_safe(symbol)

        # Cache kết quả
        if bundle:
            self.set_cached_company_bundle(symbol, bundle, ok)
            print(f"Cached company bundle for {symbol}")

        return bundle, ok

    def fetch_industries_with_cache(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Lấy industries data với cache"""
        # Thử lấy từ cache trước
        cached_result = self.get_cached_industries_data()
        if cached_result is not None:
            print("Using cached industries data")
            return cached_result

        # Nếu không có cache, gọi API
        print("Fetching industries data from API...")
        try:
            listing = self.client.listing
            industries_icb_df = listing.industries_icb()
            symbols_by_industries_df = listing.symbols_by_industries()

            # Cache kết quả
            if not industries_icb_df.empty and not symbols_by_industries_df.empty:
                self.set_cached_industries_data(industries_icb_df, symbols_by_industries_df)
                print(f"Cached industries data: {len(industries_icb_df)} industries, {len(symbols_by_industries_df)} mappings")

            return industries_icb_df, symbols_by_industries_df

        except Exception as e:
            print(f"Error fetching industries from API: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def clear_cache(self, pattern: str = None) -> None:
        """Xóa cache theo pattern"""
        if pattern:
            # Django cache không hỗ trợ pattern delete natively
            # Cần implement custom cache backend hoặc sử dụng Redis
            print(f"Cache clear pattern not implemented: {pattern}")
        else:
            cache.clear()
            print("All cache cleared")

    def clear_symbol_cache(self, symbol: str) -> None:
        """Xóa cache của một symbol cụ thể"""
        cache_key = self._get_cache_key("company_bundle", symbol)
        cache.delete(cache_key)
        print(f"Cleared cache for symbol: {symbol}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Lấy thống kê cache"""
        stats = {
            'cache_backend': type(cache).__name__,
            'ttl_settings': {
                'symbols': self.CACHE_TTL_SYMBOLS,
                'company_bundle': self.CACHE_TTL_COMPANY_BUNDLE,
                'industries': self.CACHE_TTL_INDUSTRIES
            }
        }

        # Thử lấy một số cache keys để check
        test_keys = [
            self._get_cache_key("symbols_list", exchange="HSX"),
            self._get_cache_key("industries_data")
        ]

        stats['cached_items'] = {}
        for key in test_keys:
            stats['cached_items'][key] = cache.get(key) is not None

        return stats