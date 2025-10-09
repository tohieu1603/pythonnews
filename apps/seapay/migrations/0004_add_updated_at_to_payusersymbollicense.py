from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('seapay', '0003_alter_paybanktransaction_table_comment_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payusersymbollicense',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
