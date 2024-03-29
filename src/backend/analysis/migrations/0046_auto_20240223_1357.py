# Generated by Django 3.2.13 on 2024-02-23 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0045_auto_20240219_1355'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nextflowwfversionparamset',
            name='kanteleanalysis_version',
        ),
        migrations.AddField(
            model_name='nextflowwfversionparamset',
            name='active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='userworkflow',
            name='wftype',
            # add "s" to "proteomic" for 3
            field=models.IntegerField(choices=[(1, 'Quantitative proteomics'), (2, 'Instrument quality control'), (3, 'Other proteomics, special DB'), (4, 'Proteogenomics DB generation'), (5, 'pI-separated identification'), (6, 'Special internal'), (7, 'Labelcheck')]),
        ),

        migrations.DeleteModel(
            name='PsetPredefFileParam',
        ),
    ]
