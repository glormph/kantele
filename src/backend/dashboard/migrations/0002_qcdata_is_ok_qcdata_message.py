# Generated by Django 4.2 on 2024-05-15 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='qcdata',
            name='is_ok',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='qcdata',
            name='message',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
