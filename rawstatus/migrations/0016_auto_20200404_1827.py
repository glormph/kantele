# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-04-04 18:27
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0015_auto_20200402_1324'),
    ]

    operations = [
        migrations.AlterField(
            model_name='msinstrument',
            name='producer',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='rawstatus.Producer'),
        ),
    ]
