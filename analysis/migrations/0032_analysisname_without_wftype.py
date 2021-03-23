from django.db import migrations, models

def remove_wftype_from_name(apps, sce):
    Ana = apps.get_model('analysis', 'Analysis')
    for ana in Ana.objects.filter(nextflowsearch__workflow__shortname__isnull=False):
        splitname = ana.name.split('_')
        if splitname[0] == ana.nextflowsearch.workflow.shortname.name:
            ana.name = '_'.join(splitname[1:])
            ana.save()


def put_back_wftype_to_name(apps, sce):
    Ana = apps.get_model('analysis', 'Analysis')
    for ana in Ana.objects.filter(nextflowsearch__workflow__shortname__isnull=False):
        if ana.nextflowsearch.workflow.shortname.name in ['STD', 'LC', '6FT']:
            ana.name = f'{ana.nextflowsearch.workflow.shortname.name}_{ana.name}'
            ana.save()



class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0031_auto_20210319_1246'),
    ]

    operations = [
        migrations.RunPython(remove_wftype_from_name, put_back_wftype_to_name)
    ]
