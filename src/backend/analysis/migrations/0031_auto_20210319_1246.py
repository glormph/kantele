# Generated by Django 3.1.2 on 2021-03-19 12:46

from django.db import migrations, models


def convert_nullstring_to_empty_list(apps, sce):
    Ana = apps.get_model('analysis', 'Analysis')
    Ana.objects.filter(log='').update(log='[]')


def revert_emptylist_to_nullstring(apps, sce):
    Ana = apps.get_model('analysis', 'Analysis')
    Ana.objects.filter(log='[]').update(log='')


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0030_auto_20210121_1354'),
    ]

    operations = [
        migrations.RunPython(convert_nullstring_to_empty_list, revert_emptylist_to_nullstring),

        migrations.AlterField(
            model_name='analysis',
            name='log',
            field=models.JSONField(default=list),
        ),
        migrations.AlterField(
            model_name='analysis',
            name='name',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='fileparam',
            name='name',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='fileparam',
            name='nfparam',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='libraryfile',
            name='description',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='nextflowwfversion',
            name='filename',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='nextflowwfversion',
            name='update',
            field=models.TextField(help_text='Description of workflow update'),
        ),
        migrations.AlterField(
            model_name='nextflowworkflow',
            name='description',
            field=models.TextField(help_text='Description of workflow'),
        ),
        migrations.AlterField(
            model_name='nextflowworkflow',
            name='repo',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='param',
            name='name',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='param',
            name='nfparam',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='param',
            name='ptype',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='wfinputcomponent',
            name='value',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='name',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='workflowtype',
            name='name',
            field=models.TextField(),
        ),
    ]
