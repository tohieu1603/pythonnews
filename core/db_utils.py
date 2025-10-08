"""
Database connection utilities để đóng connections đúng cách
Tránh connection leaks khi làm việc với external libraries và batch operations
"""
import logging
from typing import Any, List, Optional, Callable
from functools import wraps
from django.db import connection, reset_queries

logger = logging.getLogger('app')


def close_db_connections(*objects: Any) -> None:
    """
    Đóng database connections trong các objects (VNStock, SQLAlchemy, etc.)

    Args:
        *objects: Danh sách objects cần đóng connections

    Usage:
        from core.db_utils import close_db_connections

        vn_company = VNCompany(symbol="VNM")
        listing = Listing()

        try:
            # Do something
            pass
        finally:
            close_db_connections(vn_company, listing)
    """
    for obj in objects:
        if obj is None:
            continue

        try:
            # Các thuộc tính connection phổ biến
            connection_attrs = ['conn', '_conn', 'connection', '_connection', 'db', '_db']

            for attr in connection_attrs:
                if hasattr(obj, attr):
                    conn = getattr(obj, attr)
                    if conn is not None and hasattr(conn, 'close'):
                        try:
                            conn.close()
                            logger.debug(f"Closed connection for {type(obj).__name__}.{attr}")
                        except Exception as e:
                            logger.warning(f"Error closing {type(obj).__name__}.{attr}: {e}")

            # Nếu object có method close()
            if hasattr(obj, 'close') and callable(getattr(obj, 'close')):
                try:
                    obj.close()
                    logger.debug(f"Closed {type(obj).__name__} via close() method")
                except Exception as e:
                    logger.warning(f"Error closing {type(obj).__name__}: {e}")

        except Exception as e:
            logger.warning(f"Error processing {type(obj).__name__}: {e}")


def ensure_django_connection_closed() -> None:
    """
    Đảm bảo Django connection được đóng (hữu ích cho management commands)

    Usage:
        from core.db_utils import ensure_django_connection_closed

        try:
            # Do batch operations
            pass
        finally:
            ensure_django_connection_closed()
    """
    try:
        if connection.connection is not None:
            connection.close()
            logger.debug("Closed Django database connection")
    except Exception as e:
        logger.warning(f"Error closing Django connection: {e}")


def close_django_connection_after(func: Callable) -> Callable:
    """
    Decorator để tự động đóng Django connection sau khi function chạy xong

    Usage:
        from core.db_utils import close_django_connection_after

        @close_django_connection_after
        def import_symbols():
            # Do import operations
            Symbol.objects.bulk_create([...])
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            ensure_django_connection_closed()
            reset_queries()  # Clear query cache
    return wrapper


def batch_operation_wrapper(batch_size: int = 100):
    """
    Decorator cho batch operations - đóng connection sau mỗi batch

    Usage:
        from core.db_utils import batch_operation_wrapper

        @batch_operation_wrapper(batch_size=100)
        def process_symbols(symbols):
            for i, symbol in enumerate(symbols):
                # Process symbol
                if (i + 1) % 100 == 0:
                    yield  # Signal để đóng connection
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            generator = func(*args, **kwargs)
            if generator is None:
                ensure_django_connection_closed()
                reset_queries()
                return

            try:
                batch_count = 0
                for item in generator:
                    batch_count += 1
                    if batch_count >= batch_size:
                        ensure_django_connection_closed()
                        reset_queries()
                        batch_count = 0
                    yield item
            finally:
                ensure_django_connection_closed()
                reset_queries()
        return wrapper
    return decorator


def close_all_connections(*objects: Any) -> None:
    """
    Đóng tất cả connections: cả objects và Django connection

    Usage:
        from core.db_utils import close_all_connections

        vn_company = VNCompany(symbol="VNM")

        try:
            # Do something
            pass
        finally:
            close_all_connections(vn_company)
    """
    close_db_connections(*objects)
    ensure_django_connection_closed()


class ConnectionContextManager:
    """
    Context manager để tự động đóng connections khi ra khỏi block

    Usage:
        from core.db_utils import ConnectionContextManager

        with ConnectionContextManager() as ctx:
            vn_company = VNCompany(symbol="VNM")
            listing = Listing()

            ctx.register(vn_company, listing)

            # Do something
            # Connections sẽ tự động đóng khi ra khỏi with block
    """

    def __init__(self, close_django_connection: bool = False):
        self.objects: List[Any] = []
        self.close_django_connection = close_django_connection

    def register(self, *objects: Any) -> None:
        """Đăng ký objects cần đóng connection"""
        self.objects.extend(objects)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        close_db_connections(*self.objects)

        if self.close_django_connection:
            ensure_django_connection_closed()

        return False  # Don't suppress exceptions


class DatabaseConnectionMiddleware:
    """
    Middleware để đảm bảo database connections được quản lý đúng cách
    Thêm vào MIDDLEWARE trong settings:
        'core.db_utils.DatabaseConnectionMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Reset queries trước request (nếu DEBUG=True)
        reset_queries()

        response = self.get_response(request)

        # Đóng connection nếu có lỗi
        if connection.errors_occurred:
            logger.warning('Database errors occurred, closing connection')
            connection.close()

        return response


def close_old_connections_decorator(func):
    """
    Decorator để đóng old connections trước và sau khi chạy function
    Dùng cho các long-running tasks, celery tasks, etc.

    Usage:
        from core.db_utils import close_old_connections_decorator

        @close_old_connections_decorator
        def my_long_task():
            # Process data
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import close_old_connections

        # Đóng old connections trước khi chạy
        close_old_connections()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Đóng old connections sau khi chạy
            close_old_connections()

    return wrapper


def get_db_connection_info():
    """
    Lấy thông tin về database connections hiện tại
    Returns dict với total, idle, active connections

    Usage:
        from core.db_utils import get_db_connection_info

        info = get_db_connection_info()
        print(f"Total: {info['total']}, Idle: {info['idle']}")
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                count(*) FILTER (WHERE state IS NOT NULL) as total,
                count(*) FILTER (WHERE state = 'idle') as idle,
                count(*) FILTER (WHERE state = 'active') as active,
                count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)

        row = cursor.fetchone()
        return {
            'total': row[0] or 0,
            'idle': row[1] or 0,
            'active': row[2] or 0,
            'idle_in_transaction': row[3] or 0,
        }
