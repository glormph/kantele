# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-08-20 13:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0013_param_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowfileparam',
            name='allow_resultfiles',
            field=models.BooleanField(default=False),
        ),
    ]
