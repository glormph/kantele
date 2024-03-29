# Generated by Django 3.1.2 on 2021-07-28 11:58

from django.db import migrations, models


def fake_revert(a, s):
    pass


def merge_dupes(apps, sch_ed):
    Proj = apps.get_model('datasets', 'Project')
    Experiment = apps.get_model('datasets', 'Experiment')
    RunName = apps.get_model('datasets', 'RunName')
    print('Merging project duplicates')
    dupes_names = Proj.objects.values('name').annotate(co=models.Count('id')).filter(co__gt=1)
    for x in dupes_names:
        # First delete experiments without runnames
        dupprojs = Proj.objects.filter(name=x['name'])
        for proj in dupprojs:
            for exp in proj.experiment_set.all():
                if exp.runname_set.count() == 0:
                    exp.delete()
        # Now delete projects without experiments
        dupprojs = Proj.objects.filter(name=x['name'])
        for proj in dupprojs:
            if proj.experiment_set.count() == 0:
                proj.delete()
        # Merge projects
        dupprojs = Proj.objects.filter(name=x['name']).order_by('registered')
        for proj in dupprojs[1:]:
            oldexps = {x.name: x for x in dupprojs[0].experiment_set.all()}
            existing_runs = RunName.objects.filter(experiment__project=dupprojs[0])
            for exp in proj.experiment_set.all():
                runnames_pks = [x.pk for x in exp.runname_set.all()]
                runnames = RunName.objects.filter(pk__in=runnames_pks)
                if exp.name not in oldexps:
                    # New experiment for existing project
                    exp.project = dupprojs[0]
                    exp.save()
                    print(f'Experiment {exp.pk} merged to project {dupprojs[0].pk} from project {proj.pk}')
                elif not runnames.filter(name__in=[x.name for x in existing_runs]).count():
                    # Runnames are not in old runnames
                    runnames.update(experiment=oldexps[exp.name])
                    print(f'Runnames of experiment {exp.pk} moved to exp. {oldexps[exp.name].pk}')
                    exp.delete()
                else:
                    raise RuntimeError('Cannot merge projects, collisions in experiment/runnames names')
            if proj.experiment_set.count():
                raise('Problem, project not empty, cannot delete, are all experiments moved?')
            else:
                proj.delete()

    print('Merging experiment duplicates')
    dupes_names_exp = Experiment.objects.values('name', 'project').annotate(co=models.Count('id')).filter(co__gt=1)
    for ename in dupes_names_exp:
        dupes_exp = Experiment.objects.filter(name=ename['name'], project_id=ename['project'])
        for exp in dupes_exp[1:]:
            existing_runs = RunName.objects.filter(experiment=dupes_exp[0])
            runnames_pks = [x.pk for x in exp.runname_set.all()]
            runnames = RunName.objects.filter(pk__in=runnames_pks)
            if not runnames.filter(name__in=[x.name for x in existing_runs]).count():
                # Runnames are not in old runnames
                runnames.update(experiment=dupes_exp[0])
                print(f'Runnames of experiment {exp.pk} moved to exp. {dupes_exp[0].pk}')
                exp.delete()
            else:
                raise RuntimeError('Cannot merge projects, collisions in experiment/runnames names')
    if Experiment.objects.values('name', 'project').annotate(co=models.Count('id')).filter(co__gt=1).count():
        raise RuntimeError('Still have dupes in exps') 
        
    print('Splitting runname duplicates')
    # Do not want to merge, since then you cant analyze datasets indep of eachother
    # Not moving dsets to other location though
    dupes_names_run = RunName.objects.values('name', 'experiment').annotate(co=models.Count('id')).filter(co__gt=1)
    for rname in dupes_names_run:
        rncount = 1
        dupes_run = RunName.objects.filter(name=rname['name'], experiment_id=rname['experiment'])
        for rn in dupes_run[1:]:
            rncount += 1
            rn.name = f'{rn.name}__{rncount}'
            rn.save()
            print('Generated', rn.name)
    if RunName.objects.values('name', 'experiment').annotate(co=models.Count('id')).filter(co__gt=1).count():
        raise RuntimeError('Still have dupes in runnames')


def crash(a, b):
    raise RuntimeError('completed but aborted')


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0013_auto_20210319_1246'),
    ]

    operations = [
        migrations.RunPython(merge_dupes, fake_revert),
        #migrations.RunPython(crash, fake_revert),
    ]
