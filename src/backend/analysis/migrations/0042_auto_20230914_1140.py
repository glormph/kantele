# Generated by Django 3.2.13 on 2023-09-14 11:40

from django.db import migrations, models


# Admin will have to add stuff by hand to psetcomopnent after applying this migration!
# This migration needs to be deployed in two steps:
# One: add new field 0042
# Two: Admin fixes new field content
# Three: remove other models and deploy new code 0043

# This migration can go first, e.g. on master, deploy


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0041_analysis_storage_dir'),
    ]

    operations = [
        migrations.AddField(
            model_name='psetcomponent',
            name='value',
            field=models.JSONField(default=1),
        ),

    ]
