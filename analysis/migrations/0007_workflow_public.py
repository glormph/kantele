# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-09-21 09:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0006_auto_20180902_0633'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflow',
            name='public',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]
