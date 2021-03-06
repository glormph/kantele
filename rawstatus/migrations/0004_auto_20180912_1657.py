# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-09-12 16:57
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F


def initialize_storedfiletypes(apps, schema_editor):
    StoredFileType = apps.get_model('rawstatus', 'StoredFileType')
    StoredFileType.objects.create(name='raw', filetype='raw')
    StoredFileType.objects.create(name='raw_mzml', filetype='mzml')
    StoredFileType.objects.create(name='refined_mzml', filetype='mzml')
    StoredFileType.objects.create(name='database', filetype='fasta')
    StoredFileType.objects.create(name='fasta', filetype='fasta')
    StoredFileType.objects.create(name='gtf', filetype='gtf')
    StoredFileType.objects.create(name='martmap', filetype='tabular')
    StoredFileType.objects.create(name='peptide_pi', filetype='tabular')
    StoredFileType.objects.create(name='tabular', filetype='tabular')
    StoredFileType.objects.create(name='modifications', filetype='text')
    StoredFileType.objects.create(name='analysis_output', filetype='analysisoutput')
    StoredFile = apps.get_model('rawstatus', 'StoredFile')
    for ft, sftid in {x.filetype: x.id for x in StoredFileType.objects.exclude(name__in=['refined_mzml', 'fasta','martmap', 'peptide_pi'])}.items():
        StoredFile.objects.filter(filetype=ft).update(filetype=sftid)


def revert_sftypes(apps, schema_editor):
    StoredFile = apps.get_model('rawstatus', 'StoredFile')
    for sftid, ft in {x.id: x.filetype for x in StoredFileType.objects.exclude(name__in=['refined_mzml', 'fasta','martmap', 'peptide_pi'])}:
        StoredFile.objects.filter(filetype=sftid).update(filetype=ft)
    StoredFileType = apps.get_model('rawstatus', 'StoredFileType')
    StoredFileType.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0003_storedfilegroup'),
    ]

    operations = [
        migrations.RunPython(initialize_storedfiletypes, revert_sftypes),
    ]
