# Generated by Django 3.2.7 on 2021-11-17 13:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0036_auto_20211028_1258'),
    ]

    operations = [
        migrations.AddField(
            model_name='proteowizard',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
