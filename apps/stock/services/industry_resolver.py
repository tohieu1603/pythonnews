# apps/stock/services/industry_resolver.py
from typing import Any, Dict, List, Optional
import pandas as pd

from apps.stock.repositories import repositories as repo
from apps.stock.utils.safe import safe_int, safe_str


class IndustryResolver:
    """Class chuyên xử lý mapping industries cho symbols"""
    
    @staticmethod
    def resolve_symbol_industries(bundle: Dict[str, pd.DataFrame], symbol_name: str) -> List[Any]:
        """
        Resolve the list of Industry ORM objects for a given symbol using
        symbols_by_industries_df (icb_code1..4) and industries_icb_df.
        Returns list of Industry objects; falls back to an "Unknown Industry" if mapping is missing.
        """
        industries: List[Any] = []

        syms_ind_df: Optional[pd.DataFrame] = bundle.get("symbols_by_industries_df")
        ind_df: Optional[pd.DataFrame] = bundle.get("industries_icb_df")

        if syms_ind_df is None or syms_ind_df.empty:
            industries.append(repo.get_or_create_industry("Unknown Industry"))
            return industries

        # Filter mapping row(s) for this symbol
        try:
            sym_rows = syms_ind_df[syms_ind_df["symbol"].astype(str).str.upper() == symbol_name.upper()]
        except Exception:
            sym_rows = syms_ind_df[syms_ind_df.get("symbol") == symbol_name]

        if sym_rows is None or sym_rows.empty:
            industries.append(repo.get_or_create_industry("Unknown Industry"))
            return industries

        first = sym_rows.iloc[0]
        codes: List[str] = []
        for col in ("icb_code1", "icb_code2", "icb_code3", "icb_code4"):
            val = first.get(col)
            if pd.isna(val) if hasattr(pd, 'isna') else val is None:
                continue
            code_str = str(int(val)) if isinstance(val, (int, float)) and not pd.isna(val) else str(val).strip()
            if code_str and code_str not in codes:
                codes.append(code_str)

        if not codes:
            industries.append(repo.get_or_create_industry("Unknown Industry"))
            return industries

        # Map each code to an Industry by looking up industries_icb_df
        if ind_df is not None and not ind_df.empty and "icb_code" in ind_df.columns:
            code_series = ind_df["icb_code"].astype(str).str.strip()
            for code in codes:
                try:
                    match = ind_df[code_series == code]
                except Exception:
                    match = ind_df[ind_df["icb_code"] == code]
                if not match.empty:
                    row = match.iloc[0]
                    industry = repo.upsert_industry({
                        "id": safe_int(row.get("icb_code")),
                        "name": safe_str(row.get("icb_name")),
                        "level": safe_int(row.get("level")),
                    })
                    industries.append(industry)

        if not industries:
            industries.append(repo.get_or_create_industry("Unknown Industry"))

        return industries