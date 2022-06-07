# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def wfparam2pset(apps, sch_ed):
    WF = apps.get_model('analysis', 'Workflow')
    PS = apps.get_model('analysis', 'ParameterSet')
    for wf in WF.objects.all():
        pset = PS.objects.create(name=wf.name)
        wf.psetfileparam_set.all().update(pset=pset)
        wf.psetpredeffileparam_set.all().update(pset=pset)
        wf.psetparam_set.all().update(pset=pset)
        wf.nfworkflow.nextflowwfversion_set.all().update(paramset=pset)


def reverse_pset2wfp(apps, sch_ed):
    # Cannot REALLY reverse this as we are going to diverge after moving the
    # params from workflow to wf-nfwf-version, but have this in case we revert
    # immediately
    WF = apps.get_model('analysis', 'Workflow')
    PS = apps.get_model('analysis', 'ParameterSet')
    for wf in WF.objects.all():
        pset = wf.nfworkflow.nextflowwfversion_set.distinct('paramset').paramset
        pset.psetfileparam_set.all().update(wf=wf)
        pset.psetpredeffileparam_set.all().update(wf=wf)
        pset.psetparam_set.all().update(wf=wf)


class Migration(migrations.Migration):
    dependencies = [
        ('analysis', '0018_auto_20200617_1137'),
    ]

    operations = [
        migrations.RunPython(wfparam2pset, reverse_pset2wfp),
    ]
