# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0007_transfer_samplefreetext_table'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quantchannelsample',
            name='sample',
        ),
        migrations.RemoveField(
            model_name='quantsamplefile',
            name='sample',
        ),
    ]
