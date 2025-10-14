"""Cache service cho Calendar API để giảm external API calls"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from django.core.cache import cache
from django.conf import settings

from .service import EconomicEvent

logger = logging.getLogger(__name__)


class CalendarCacheService:
    """Service để cache kết quả calendar API"""
    
    # Cache timeout: lấy từ settings hoặc default 15 phút
    CACHE_TIMEOUT = getattr(settings, 'CALENDAR_CACHE_TIMEOUT', 15 * 60)
    
    # Cache key prefix
    CACHE_PREFIX = "calendar_events"
    
    @classmethod
    def _generate_cache_key(
        cls,
        date_from: date,
        date_to: date, 
        time_zone: str = "110",
        importance: Optional[List[int]] = None,
        countries: Optional[List[str]] = None,
        skip_holidays: bool = True
    ) -> str:
        """Tạo unique cache key từ parameters"""
        # Tạo hash từ tất cả parameters
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "time_zone": time_zone,
            "importance": sorted(importance) if importance else None,
            "countries": sorted(countries) if countries else None,
            "skip_holidays": skip_holidays,
        }
        
        # Serialize params để tạo consistent hash
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        
        return f"{cls.CACHE_PREFIX}:{params_hash}"
    
    @classmethod
    def get_cached_events(
        cls,
        date_from: date,
        date_to: date,
        time_zone: str = "110", 
        importance: Optional[List[int]] = None,
        countries: Optional[List[str]] = None,
        skip_holidays: bool = True
    ) -> Optional[List[EconomicEvent]]:
        """Lấy cached events nếu có"""
        if not getattr(settings, 'USE_CALENDAR_CACHE', True):
            return None
            
        cache_key = cls._generate_cache_key(
            date_from, date_to, time_zone, importance, countries, skip_holidays
        )
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for calendar data: {cache_key[:20]}...")
                
                # Convert dict back to EconomicEvent objects
                events = []
                for event_data in cached_data:
                    events.append(EconomicEvent(**event_data))
                
                return events
            else:
                logger.info(f"Cache MISS for calendar data: {cache_key[:20]}...")
                
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
            
        return None
    
    @classmethod
    def cache_events(
        cls,
        events: List[EconomicEvent],
        date_from: date,
        date_to: date,
        time_zone: str = "110",
        importance: Optional[List[int]] = None, 
        countries: Optional[List[str]] = None,
        skip_holidays: bool = True
    ) -> bool:
        """Cache events với parameters tương ứng"""
        if not getattr(settings, 'USE_CALENDAR_CACHE', True):
            return False
            
        cache_key = cls._generate_cache_key(
            date_from, date_to, time_zone, importance, countries, skip_holidays
        )
        
        try:
            # Convert EconomicEvent objects to dict for serialization
            events_data = [asdict(event) for event in events]
            
            # Cache với timeout
            cache.set(cache_key, events_data, cls.CACHE_TIMEOUT)
            
            logger.info(f"Cached {len(events)} events for key: {cache_key[:20]}... (TTL: {cls.CACHE_TIMEOUT}s)")
            return True
            
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
            return False
    
    @classmethod
    def invalidate_date_range(cls, date_from: date, date_to: date) -> int:
        """Invalidate cache cho date range cụ thể (nếu cần manual refresh)"""
        # Vì cache key có hash, ta không thể directly invalidate range
        # Thay vào đó, clear toàn bộ calendar cache
        return cls.clear_all_cache()
    
    @classmethod 
    def clear_all_cache(cls) -> int:
        """Clear toàn bộ calendar cache"""
        try:
            # Django cache không có built-in wildcard delete
            # Nếu sử dụng Redis, có thể implement pattern-based deletion
            if hasattr(cache, 'delete_pattern'):
                # Redis cache backend with pattern support
                deleted = cache.delete_pattern(f"{cls.CACHE_PREFIX}:*")
                logger.info(f"Cleared {deleted} calendar cache entries")
                return deleted
            else:
                # Fallback: không thể clear selective, log warning
                logger.warning("Cache backend does not support pattern deletion")
                return 0
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Lấy statistics về cache usage (nếu backend hỗ trợ)"""
        try:
            # Cơ bản chỉ trả về config info
            return {
                "cache_enabled": getattr(settings, 'USE_CALENDAR_CACHE', True),
                "cache_timeout": cls.CACHE_TIMEOUT,
                "cache_prefix": cls.CACHE_PREFIX,
                "backend": str(cache.__class__.__name__),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


class SmartCacheService(CalendarCacheService):
    """Enhanced cache service với smart invalidation"""
    
    @classmethod
    def should_use_cache(cls, date_from: date, date_to: date) -> bool:
        """Kiểm tra có nên sử dụng cache không based on date range"""
        now = date.today()
        
        # Không cache nếu date range chứa ngày hôm nay (data có thể thay đổi)
        if date_from <= now <= date_to:
            return False
            
        # Không cache nếu quá gần hiện tại (trong 1 ngày)
        if abs((date_from - now).days) <= 1:
            return False
            
        # Cache cho historical data (> 1 ngày cũ)
        return True
    
    @classmethod
    def get_adaptive_timeout(cls, date_from: date, date_to: date) -> int:
        """Tính toán cache timeout adaptive based on date range"""
        now = date.today()
        
        # Historical data (> 7 ngày cũ): cache lâu hơn (2 giờ)
        if (now - date_to).days > 7:
            return 2 * 60 * 60  # 2 hours
            
        # Recent data (1-7 ngày cũ): cache trung bình (30 phút)
        elif (now - date_to).days > 1:
            return 30 * 60  # 30 minutes
            
        # Today/tomorrow data: cache ngắn (5 phút)
        else:
            return 5 * 60  # 5 minutes