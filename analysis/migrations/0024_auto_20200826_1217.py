# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-08-26 12:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0023_auto_20200826_1051'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ensemblfasta',
            name='version',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='uniprotfasta',
            name='version',
            field=models.TextField(),
        ),
    ]
