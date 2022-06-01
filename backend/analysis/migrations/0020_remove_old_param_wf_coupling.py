# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('analysis', '0019_convert_wfparams_to_paramset'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='psetfileparam',
            name='wf',
        ),
        migrations.RemoveField(
            model_name='psetparam',
            name='wf',
        ),
        migrations.RemoveField(
            model_name='psetpredeffileparam',
            name='wf',
        ),
        ]
