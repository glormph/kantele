# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-04-27 13:56
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from kantele import settings


def qsf2qfcs(apps, sch_ed):
    QCS = apps.get_model('datasets', 'QuantChannelSample')
    QSF = apps.get_model('datasets', 'QuantSampleFile')
    QFCS = apps.get_model('datasets', 'QuantFileChannelSample')
    qsfs, todelete = {}, []
    qsfdbs = QSF.objects.filter(rawfile__dataset__datatype_id=settings.LC_DTYPE_ID).exclude(
            rawfile__dataset__quantdataset__quanttype__shortname='labelfree')
    for q in qsfdbs:
        try:
            qsfs[q.projsample_id].append(q.rawfile_id)
        except KeyError:
            qsfs[q.projsample_id] = [q.rawfile_id]
    qcss = QCS.objects.filter(dataset__datatype_id=settings.LC_DTYPE_ID)
    for q in qcss:
        try:
            rfid = qsfs[q.projsample_id].pop(0)
        except KeyError:
            pass # No QuantSampleFile, old LC dataset before we registered files, leave
        except IndexError:
            # Problem, none or something in QSF map
            print('PROBLEM!', q)
            todelete.append(q)
        else:
            QFCS.objects.create(channel_id=q.channel_id, projsample_id=q.projsample_id,
                dsrawfile_id=rfid)
            todelete.append(q)
    qsfdbs.delete()
    [x.delete() for x in todelete]


def revert_lc_data(apps, sch_ed):
    QCS = apps.get_model('datasets', 'QuantChannelSample')
    QSF = apps.get_model('datasets', 'QuantSampleFile')
    QFCS = apps.get_model('datasets', 'QuantFileChannelSample')
    for q in QFCS.objects.values('dsrawfile', 'dsrawfile__dataset', 'channel', 'projsample'):
        QCS.objects.create(dataset_id=q['dsrawfile__dataset'], channel_id=q['channel'],
                projsample_id=q['projsample'])
        QSF.objects.create(rawfile_id=q['dsrawfile'], projsample_id=q['projsample'])
        q.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0011_datatype_public'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuantFileChannelSample',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='datasets.QuantTypeChannel')),
                ('dsrawfile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='datasets.DatasetRawFile')),
                ('projsample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='datasets.ProjectSample')),
            ],
        ),
        migrations.RunPython(qsf2qfcs, revert_lc_data)
    ]
