# Generated by Django 3.2.13 on 2022-09-26 12:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0024_auto_20220923_1359'),
        ('datasets', '0015_proj_exp_run_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='storageshare',
            field=models.ForeignKey(default=2, on_delete=django.db.models.deletion.CASCADE, to='rawstatus.servershare'),
            preserve_default=False,
        ),
    ]
