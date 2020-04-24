from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion

from kantele import settings


def merge_refined(apps, sch_ed):
    SFile = apps.get_model('rawstatus', 'StoredFile')
    FT = apps.get_model('rawstatus', 'StoredFileType')
    SFile.objects.filter(filetype_id=settings.REFINEDMZML_SFGROUP_ID).update(filetype_id=settings.MZML_SFGROUP_ID)
    FT.objects.filter(pk=settings.REFINEDMZML_SFGROUP_ID).delete()


def undo_merge(apps, sch_ed):
    SFile = apps.get_model('rawstatus', 'StoredFile')
    FT = apps.get_model('rawstatus', 'StoredFileType')
    new_ft = FT.objects.create(filetype='mzml', name='refinedned_mzml')
    SFile.objects.filter(mzmlfile__refined=True).update(filetype=new_ft)
    print('You must set REFINEDMZML_SFGROUP_ID in settings to {}'.format(new_ft.id))


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0016_auto_20200404_1827'),
        ('analysis', '0016_auto_20200404_1827'),
    ]

    operations = [
        migrations.RunPython(merge_refined, undo_merge)
    ]
