# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-06-17 10:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0016_auto_20200404_1827'),
    ]

    operations = [
        migrations.AddField(
            model_name='nextflowwfversion',
            name='kanteleanalysis_version',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='nextflowwfversion',
            name='nfversion',
            field=models.TextField(default='19.04.0'),
            preserve_default=False,
        ),
    ]