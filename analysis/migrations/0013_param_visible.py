# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-18 15:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0012_analysisdeleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='param',
            name='visible',
            field=models.BooleanField(default=True),
        ),
    ]
