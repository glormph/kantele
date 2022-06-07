# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def samplenames_to_table(apps, schema_editor):
    PS = apps.get_model('datasets', 'ProjectSample')
    QCS = apps.get_model('datasets', 'QuantChannelSample')
    QSF = apps.get_model('datasets', 'QuantSampleFile')
    for qcs in QCS.objects.select_related('dataset__runname__experiment'):
        pid = qcs.dataset.runname.experiment.project_id
        qcs.projsample_id = PS.objects.get(project_id=pid, sample=qcs.sample)
        qcs.save()
    for qsf in QSF.objects.select_related('rawfile__dataset__runname__experiment'):
        pid = qsf.rawfile.dataset.runname.experiment.project_id
        qsf.projsample_id = PS.objects.get(project_id=pid, sample=qsf.sample)
        qsf.save()


def table_to_samplenames(apps, schema_editor):
    QCS = apps.get_model('datasets', 'QuantChannelSample')
    QSF = apps.get_model('datasets', 'QuantSampleFile')
    for qcs in QCS.objects.select_related('projsample'):
        qcs.sample = qcs.projsample.sample
        qcs.save()
    for qsf in QSF.objects.select_related('projsample'):
        qsf.sample = qsf.projsample.sample
        qsf.save()


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0006_auto_20190424_1225'),
    ]

    operations = [
        migrations.RunPython(samplenames_to_table, table_to_samplenames),
    ]
