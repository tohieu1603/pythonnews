"""
Pandas compatibility utilities để fix deprecated warnings
"""
import pandas as pd
import warnings
from typing import Any, Callable


def safe_map_dataframe(df: pd.DataFrame, func: Callable, **kwargs) -> pd.DataFrame:
    """
    Safely apply function to DataFrame, using appropriate method based on pandas version
    """
    if df is None or df.empty:
        return df

    try:
        # Suppress specific deprecated warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*applymap.*", category=FutureWarning)

            # Try new method first (pandas >= 2.1.0)
            if hasattr(df, 'map'):
                return df.map(func, **kwargs)
            # Fallback to deprecated method
            else:
                return df.applymap(func, **kwargs)
    except Exception:
        # If all else fails, return original DataFrame
        return df


def safe_fillna(df: pd.DataFrame, value: Any = None, method: str = None) -> pd.DataFrame:
    """
    Safely fill NaN values with appropriate method
    """
    if df is None or df.empty:
        return df

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)

            if method:
                # Handle deprecated method parameter
                if method == 'ffill':
                    return df.ffill()
                elif method == 'bfill':
                    return df.bfill()
                else:
                    return df.fillna(value=value)
            else:
                return df.fillna(value=value)
    except Exception:
        return df


def safe_convert_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Safely convert DataFrame dtypes without warnings
    """
    if df is None or df.empty:
        return df

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)

            # Convert object columns to string where appropriate
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Check if column contains mostly strings
                    sample = df[col].dropna().head(10)
                    if not sample.empty and all(isinstance(x, str) for x in sample):
                        df[col] = df[col].astype('string')

            return df
    except Exception:
        return df


def suppress_pandas_warnings():
    """
    Suppress common pandas warnings that are not actionable
    """
    warnings.filterwarnings("ignore", message=".*applymap.*", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*method.*", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*iloc.*", category=FutureWarning)

    # Suppress vnstock specific warnings
    warnings.filterwarnings("ignore", message=".*VCI.*", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*rate limit.*", category=UserWarning)


# Apply warning suppression when module is imported
suppress_pandas_warnings()