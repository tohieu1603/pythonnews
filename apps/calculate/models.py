
from django.db import models
from apps.stock.models import Symbol
STOCK_SYMBOL_MODEL = 'stock.Symbol'


class CashFlow(models.Model):
    """Báo cáo lưu chuyển tiền tệ"""
    year_report = models.IntegerField(help_text="Năm")
    length_report = models.IntegerField(help_text="Kỳ")

    net_profit_loss_before_tax = models.BigIntegerField(null=True, blank=True)
    depreciation_and_amortisation = models.BigIntegerField(null=True, blank=True)
    provision_for_credit_losses = models.BigIntegerField(null=True, blank=True)
    unrealized_foreign_exchange_gain_loss = models.BigIntegerField(null=True, blank=True)
    profit_loss_from_investing_activities = models.BigIntegerField(null=True, blank=True)
    interest_expense = models.BigIntegerField(null=True, blank=True)
    operating_profit_before_changes_in_working_capital = models.BigIntegerField(null=True, blank=True)
    increase_decrease_in_receivables = models.BigIntegerField(null=True, blank=True)
    increase_decrease_in_inventories = models.BigIntegerField(null=True, blank=True)
    increase_decrease_in_payables = models.BigIntegerField(null=True, blank=True)
    increase_decrease_in_prepaid_expenses = models.BigIntegerField(null=True, blank=True)
    interest_paid = models.BigIntegerField(null=True, blank=True)
    business_income_tax_paid = models.BigIntegerField(null=True, blank=True)
    net_cash_inflows_outflows_from_operating_activities = models.BigIntegerField(null=True, blank=True)
    purchase_of_fixed_assets = models.BigIntegerField(null=True, blank=True)
    proceeds_from_disposal_of_fixed_assets = models.BigIntegerField(null=True, blank=True)
    loans_granted_purchases_of_debt_instruments_bn_vnd = models.BigIntegerField(null=True, blank=True)
    collection_of_loans_proceeds_sales_instruments_vnd = models.BigIntegerField(null=True, blank=True)
    investment_in_other_entities = models.BigIntegerField(null=True, blank=True)
    proceeds_from_divestment_in_other_entities = models.BigIntegerField(null=True, blank=True)
    gain_on_dividend = models.BigIntegerField(null=True, blank=True)
    net_cash_flows_from_investing_activities = models.BigIntegerField(null=True, blank=True)
    increase_in_charter_captial = models.BigIntegerField(null=True, blank=True)
    payments_for_share_repurchases = models.BigIntegerField(null=True, blank=True)
    proceeds_from_borrowings = models.BigIntegerField(null=True, blank=True)
    repayment_of_borrowings = models.BigIntegerField(null=True, blank=True)
    finance_lease_principal_payments = models.BigIntegerField(null=True, blank=True)
    dividends_paid = models.BigIntegerField(null=True, blank=True)
    cash_flows_from_financial_activities = models.BigIntegerField(null=True, blank=True)
    net_increase_decrease_in_cash_and_cash_equivalents = models.BigIntegerField(null=True, blank=True)
    cash_and_cash_equivalents = models.BigIntegerField(null=True, blank=True)
    foreign_exchange_differences_adjustment = models.BigIntegerField(null=True, blank=True)
    cash_and_cash_equivalents_at_the_end_of_period = models.BigIntegerField(null=True, blank=True)

    symbol = models.ForeignKey(
        STOCK_SYMBOL_MODEL,
        on_delete=models.CASCADE,
        related_name='cash_flows'
    )

    class Meta:
        unique_together = ('symbol', 'year_report', 'length_report')
        ordering = ['-year_report', '-length_report']

    def __str__(self):
        return f"{self.symbol.name} - Cash Flow {self.year_report}Q{self.length_report}"

class IncomeStatement(models.Model):
    """Báo cáo kết quả kinh doanh"""
    year_report = models.IntegerField(help_text="Năm")
    length_report = models.IntegerField(help_text="Kỳ")

    revenue_yoy_percent = models.FloatField(null=True, blank=True, help_text="Doanh thu YoY (%)")
    revenue_bn_vnd = models.BigIntegerField(null=True, blank=True, help_text="Doanh thu (Bn. VND)")
    attribute_to_parent_company_bn_vnd = models.BigIntegerField(null=True, blank=True, help_text="LN sau thuế CĐ công ty mẹ (Bn. VND)")
    attribute_to_parent_company_yo_y_percent = models.FloatField(null=True, blank=True, help_text="Tăng trưởng LN CĐ mẹ YoY (%)")
    financial_income = models.BigIntegerField(null=True, blank=True, help_text="Thu nhập tài chính (Bn. VND)")
    interest_expenses = models.BigIntegerField(null=True, blank=True, help_text="Chi phí lãi vay (Bn. VND)")
    sales = models.BigIntegerField(null=True, blank=True, help_text="Doanh thu bán hàng")
    sales_deductions = models.BigIntegerField(null=True, blank=True, help_text="Các khoản giảm trừ")
    net_sales = models.BigIntegerField(null=True, blank=True, help_text="Doanh thu thuần")
    cost_of_sales = models.BigIntegerField(null=True, blank=True, help_text="Giá vốn hàng bán")
    gross_profit = models.BigIntegerField(null=True, blank=True, help_text="Lợi nhuận gộp")
    financial_expenses = models.BigIntegerField(null=True, blank=True, help_text="Chi phí tài chính")
    gain_loss_from_joint_ventures = models.BigIntegerField(null=True, blank=True, help_text="LN/Lỗ liên doanh")
    selling_expenses = models.BigIntegerField(null=True, blank=True, help_text="Chi phí bán hàng")
    general_admin_expenses = models.BigIntegerField(null=True, blank=True, help_text="Chi phí QLDN")
    operating_profit_loss = models.BigIntegerField(null=True, blank=True, help_text="LN từ HĐKD")
    other_income = models.BigIntegerField(null=True, blank=True, help_text="Thu nhập khác")
    other_income_expenses = models.BigIntegerField(null=True, blank=True, help_text="Thu nhập/Chi phí khác")
    net_other_income_expenses = models.BigIntegerField(null=True, blank=True, help_text="LN/Lỗ thuần từ HĐ khác")
    profit_before_tax = models.BigIntegerField(null=True, blank=True, help_text="LN trước thuế")
    business_income_tax_current = models.BigIntegerField(null=True, blank=True, help_text="Thuế TNDN hiện hành")
    business_income_tax_deferred = models.BigIntegerField(null=True, blank=True, help_text="Thuế TNDN hoãn lại")
    net_profit_for_the_year = models.BigIntegerField(null=True, blank=True, help_text="LN thuần năm")
    minority_interest = models.BigIntegerField(null=True, blank=True, help_text="Lợi ích cổ đông thiểu số")
    attributable_to_parent_company = models.BigIntegerField(null=True, blank=True, help_text="LN thuộc về CĐ công ty mẹ")

    symbol = models.ForeignKey(
        STOCK_SYMBOL_MODEL,
        on_delete=models.CASCADE,
        related_name='income_statements'
    )

    class Meta:
        unique_together = ('symbol', 'year_report', 'length_report')
        ordering = ['-year_report', '-length_report']

    def __str__(self):
        return f"{self.symbol.name} - {self.year_report}Q{self.length_report}"

class Ratio(models.Model):
    """Các chỉ số tài chính"""
    year_report = models.IntegerField()
    length_report = models.IntegerField()

    st_lt_borrowings_equity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    debt_equity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    fixed_asset_to_equity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    owners_equity_charter_capital = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    asset_turnover = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    fixed_asset_turnover = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    days_sales_outstanding = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    days_inventory_outstanding = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    days_payable_outstanding = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    cash_cycle = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    inventory_turnover = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    ebit_margin_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    gross_profit_margin_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    net_profit_margin_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    roe_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    roic_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    roa_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    ebitda_bn_vnd = models.BigIntegerField(null=True, blank=True)
    ebit_bn_vnd = models.BigIntegerField(null=True, blank=True)
    dividend_yield_percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    current_ratio = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    cash_ratio = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    quick_ratio = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    interest_coverage = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    financial_leverage = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    market_capital_bn_vnd = models.BigIntegerField(null=True, blank=True)
    outstanding_share_mil_shares = models.BigIntegerField(null=True, blank=True)
    p_e = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    p_b = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    p_s = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    p_cash_flow = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    eps_vnd = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    bvps_vnd = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    ev_ebitda = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    symbol = models.ForeignKey(
        STOCK_SYMBOL_MODEL,
        on_delete=models.CASCADE,
        related_name='ratios'
    )

    class Meta:
        unique_together = ('symbol', 'year_report', 'length_report')
        ordering = ['-year_report', '-length_report']

    def __str__(self):
        return f"{self.symbol.name} - Ratios {self.year_report}Q{self.length_report}"

class BalanceSheet(models.Model):
    """Bảng cân đối kế toán"""
    year_report = models.IntegerField(help_text="Năm báo cáo")
    length_report = models.IntegerField(help_text="Kỳ báo cáo")

    current_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    cash_and_cash_equivalents_bn_vnd = models.BigIntegerField(null=True, blank=True)
    short_term_investments_bn_vnd = models.BigIntegerField(null=True, blank=True)
    accounts_receivable_bn_vnd = models.BigIntegerField(null=True, blank=True)
    net_inventories = models.BigIntegerField(null=True, blank=True)
    other_current_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_loans_receivables_bn_vnd = models.BigIntegerField(null=True, blank=True)
    fixed_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_investments_bn_vnd = models.BigIntegerField(null=True, blank=True)
    other_non_current_assets = models.BigIntegerField(null=True, blank=True)
    total_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    liabilities_bn_vnd = models.BigIntegerField(null=True, blank=True)
    current_liabilities_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_liabilities_bn_vnd = models.BigIntegerField(null=True, blank=True)
    owners_equitybn_vnd = models.BigIntegerField(null=True, blank=True)
    capital_and_reserves_bn_vnd = models.BigIntegerField(null=True, blank=True)
    undistributed_earnings_bn_vnd = models.BigIntegerField(null=True, blank=True)
    minority_interests = models.BigIntegerField(null=True, blank=True)
    total_resources_bn_vnd = models.BigIntegerField(null=True, blank=True)
    prepayments_to_suppliers_bn_vnd = models.BigIntegerField(null=True, blank=True)
    short_term_loans_receivables_bn_vnd = models.BigIntegerField(null=True, blank=True)
    inventories_net_bn_vnd = models.BigIntegerField(null=True, blank=True)
    investment_and_development_funds_bn_vnd = models.BigIntegerField(null=True, blank=True)
    common_shares_bn_vnd = models.BigIntegerField(null=True, blank=True)
    paid_in_capital_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_borrowings_bn_vnd = models.BigIntegerField(null=True, blank=True)
    advances_from_customers_bn_vnd = models.BigIntegerField(null=True, blank=True)
    short_term_borrowings_bn_vnd = models.BigIntegerField(null=True, blank=True)
    good_will_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_prepayments_bn_vnd = models.BigIntegerField(null=True, blank=True)
    other_long_term_assets_bn_vnd = models.BigIntegerField(null=True, blank=True)
    other_long_term_receivables_bn_vnd = models.BigIntegerField(null=True, blank=True)
    long_term_trade_receivables_bn_vnd = models.BigIntegerField(null=True, blank=True)

    symbol = models.ForeignKey(
        STOCK_SYMBOL_MODEL,
        on_delete=models.CASCADE,
        related_name='balance_sheets'
    )

    class Meta:
        unique_together = ('symbol', 'year_report', 'length_report')
        ordering = ['-year_report', '-length_report']

    def __str__(self):
        return f"{self.symbol.name} - Balance Sheet {self.year_report}Q{self.length_report}"
