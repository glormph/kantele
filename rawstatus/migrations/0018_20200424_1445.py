from __future__ import unicode_literals

from django.db.models import F
from django.db import migrations
from kantele import settings


def mzml_to_raw_ft(apps, sch_ed):
    SFile = apps.get_model('rawstatus', 'StoredFile')
    SFile.objects.filter(mzmlfile__isnull=False, rawfile__storedfile__filetype_id=settings.RAW_SFGROUP_ID).update(filetype_id=settings.RAW_SFGROUP_ID)
    SFile.objects.filter(mzmlfile__isnull=False, rawfile__storedfile__filetype_id=settings.BRUKER_SFGROUP_ID).update(filetype_id=settings.BRUKER_SFGROUP_ID)


def undo_mzmlft(apps, sch_ed):
    SFile = apps.get_model('rawstatus', 'StoredFile')
    FT = apps.get_model('rawstatus', 'StoredFileType')
    SFile.objects.filter(mzmlfile__isnull=False).upate(filetype_id=settings.MZML_SFGROUP_ID)


class Migration(migrations.Migration):

    dependencies = [
        ('rawstatus', '0017_20200424_1350'),
    ]

    operations = [
        migrations.RunPython(mzml_to_raw_ft, undo_mzmlft)
    ]
