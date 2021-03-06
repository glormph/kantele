# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-09-30 11:33
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def convert_filetypes(apps, schema_editor):
    FileParam = apps.get_model('analysis', 'FileParam')
    StoredFileType = apps.get_model('rawstatus', 'StoredFileType')
    sftmap = {x.filetype: x.id for x in StoredFileType.objects.all()}
    for fp in FileParam.objects.all():
        fp.filetype = sftmap[fp.filetype]
        fp.save()


def revert_sftypes(apps, schema_editor):
    FileParam = apps.get_model('analysis', 'FileParam')
    StoredFileType = apps.get_model('rawstatus', 'StoredFileType')
    sftmap = {x.id: x.filetype for x in StoredFileType.objects.all()}
    for fp in FileParam.objects.all():
        fp.filetype = sftmap[fp.filetype]
        fp.save()


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0007_workflow_public'),
    ]

    operations = [
        migrations.RunPython(convert_filetypes, revert_sftypes),
        migrations.AlterField(
            model_name='fileparam',
            name='filetype',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='rawstatus.StoredFileType'),
        ),
    ]
