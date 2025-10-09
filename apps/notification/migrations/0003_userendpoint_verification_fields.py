from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0002_webhooklog'),
    ]

    operations = [
        migrations.AddField(
            model_name='userendpoint',
            name='verification_code',
            field=models.CharField(
                blank=True,
                help_text='Mã OTP xác thực (mã plaintext hoặc hashed)',
                max_length=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='userendpoint',
            name='verification_expires_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Thời gian hết hạn của mã xác thực',
                null=True,
            ),
        ),
    ]
