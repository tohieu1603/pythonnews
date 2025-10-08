from functools import wraps
from django.db import connection

def close_db_after(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            connection.close() 
    return wrapper