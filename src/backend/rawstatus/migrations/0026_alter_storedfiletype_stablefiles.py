# Generated by Django 3.2.13 on 2022-10-31 12:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0025_auto_20221031_1010'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storedfiletype',
            name='stablefiles',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
