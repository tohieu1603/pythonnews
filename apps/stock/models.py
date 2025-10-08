from django.db import models

class Industry(models.Model):
    id = models.IntegerField(primary_key=True)  
    name = models.CharField(max_length=255)
    level = models.IntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Company(models.Model):
    company_name = models.CharField(max_length=255, unique=True)
    company_profile = models.TextField(null=True, blank=True)
    history = models.TextField(null=True, blank=True)
    issue_share = models.BigIntegerField(null=True, blank=True)
    financial_ratio_issue_share = models.BigIntegerField(null=True, blank=True)
    charter_capital = models.BigIntegerField(null=True, blank=True)
    outstanding_share = models.FloatField(null=True, blank=True)
    foreign_percent = models.FloatField(null=True, blank=True)
    established_year = models.IntegerField(null=True, blank=True)
    no_employees = models.IntegerField(null=True, blank=True)
    stock_rating = models.FloatField(null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)
    industries = models.ManyToManyField('Industry', related_name='companies', blank=True)
    delta_in_week = models.FloatField(null=True, blank=True)
    delta_in_month = models.FloatField(null=True, blank=True)
    delta_in_year = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

class Symbol(models.Model):
    name = models.CharField(max_length=200, unique=True)
    exchange = models.CharField(max_length=50)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='symbols'
    )
    industries = models.ManyToManyField('Industry', related_name='symbols', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.exchange})"

class ShareHolder(models.Model):
    share_holder = models.CharField(max_length=255)
    quantity = models.BigIntegerField(default=0)
    share_own_percent = models.DecimalField(max_digits=12, decimal_places=6, default=0.0)
    update_date = models.DateField(null=True, blank=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='shareholders'
    )

    class Meta:
        unique_together = ("share_holder", "company")

    def __str__(self):
        return f"{self.share_holder} - {self.share_own_percent}%"
class News(models.Model):
    title = models.CharField(max_length=255)
    news_image_url = models.CharField(max_length=255, blank=True, null=True)
    news_source_link = models.CharField(max_length=255, blank=True, null=True)
    price_change_pct = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    public_date = models.BigIntegerField(null=True, blank=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='news'
    )

    def __str__(self):
        return self.title

class Events(models.Model):
    event_title = models.CharField(max_length=255)
    public_date = models.DateTimeField(null=True, blank=True)
    issue_date = models.DateTimeField(null=True, blank=True)
    source_url = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='events'
    )

    def __str__(self):
        return self.event_title

class Officers(models.Model):
    officer_name = models.CharField(max_length=255)
    officer_position = models.CharField(max_length=255)
    position_short_name = models.CharField(max_length=255)
    officer_owner_percent = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='officers'
    )

    def __str__(self):
        return f"{self.officer_name} - {self.officer_position}"
class SubCompany(models.Model):
    parent = models.ForeignKey("Company", on_delete=models.CASCADE, related_name="subsidiaries")
    company_name = models.CharField(max_length=200)
    sub_own_percent = models.FloatField(blank=True)