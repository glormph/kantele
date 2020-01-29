# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-12-06 14:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0013_auto_20190913_1932'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProducerFileType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filetype', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='rawstatus.StoredFileType')),
            ],
        ),
        migrations.RemoveField(
            model_name='producer',
            name='heartbeat',
        ),
        migrations.AddField(
            model_name='producerfiletype',
            name='producer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='rawstatus.Producer'),
        ),
    ]