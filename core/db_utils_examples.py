"""
Examples về cách sử dụng db_utils trong các apps khác
"""

def example_basic_usage():
    from vnstock import Company as VNCompany, Listing
    from core.db_utils import close_db_connections

    vn_company = None
    listing = None

    try:
        vn_company = VNCompany(symbol="VNM", source="TCBS")
        listing = Listing()

        overview = vn_company.overview()
        symbols = listing.symbols_by_exchange()

    finally:
        close_db_connections(vn_company, listing)

def example_context_manager():
    from vnstock import Company as VNCompany, Listing
    from core.db_utils import ConnectionContextManager

    with ConnectionContextManager() as ctx:
        vn_company = VNCompany(symbol="HPG", source="VCI")
        listing = Listing()

        ctx.register(vn_company, listing)

        overview = vn_company.overview()
        shareholders = vn_company.shareholders()

def example_close_all():
    from vnstock import Company as VNCompany
    from core.db_utils import close_all_connections

    vn_company = None

    try:
        vn_company = VNCompany(symbol="VCB", source="TCBS")

        from apps.stock.models import Symbol
        Symbol.objects.bulk_create([...])

    finally:
        close_all_connections(vn_company)

def example_batch_processing():
    from vnstock import Company as VNCompany
    from core.db_utils import close_db_connections

    symbols = ["VNM", "HPG", "VCB", "FPT", "VIC"]

    for symbol in symbols:
        vn_company_tcbs = None
        vn_company_vci = None

        try:
            vn_company_tcbs = VNCompany(symbol=symbol, source="TCBS")
            vn_company_vci = VNCompany(symbol=symbol, source="VCI")

            overview_tcbs = vn_company_tcbs.overview()
            overview_vci = vn_company_vci.overview()

            print(f"Processed {symbol}")

        finally:
            close_db_connections(vn_company_tcbs, vn_company_vci)

def example_nested_contexts():
    from vnstock import Company as VNCompany, Listing
    from core.db_utils import ConnectionContextManager

    with ConnectionContextManager() as outer_ctx:
        listing = Listing()
        outer_ctx.register(listing)

        symbols = listing.symbols_by_exchange()

        for symbol_name in symbols['symbol'][:5]:
            with ConnectionContextManager() as inner_ctx:
                vn_company = VNCompany(symbol=symbol_name)
                inner_ctx.register(vn_company)

                overview = vn_company.overview()


