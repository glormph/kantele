from datetime import datetime
import json
import re

from django.utils import timezone

from kantele import settings
from analysis import tasks, models, views
from rawstatus import models as filemodels
from datasets import models as dsmodels
from datasets.jobs import get_or_create_mzmlentry
from jobs.post import create_db_task

# FIXMEs
# rerun qc data and displaying qcdata for a given qc file, how? 
# run should check if already ran with same commit/analysis


def refine_mzmls_getfiles(dset_id, analysis_id, wfv_id, dbfn_id, qtype):
    """Return all a dset mzMLs but not those that have a refined mzML associated, to not do extra work."""
    existing_refined = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=dset_id, filetype_id=settings.REFINEDMZML_SFGROUP_ID, checked=True)
    return filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=dset_id, filetype_id=settings.MZML_SFGROUP_ID).exclude(rawfile__storedfile__in=existing_refined)


def refine_mzmls(job_id, dset_id, analysis_id, wfv_id, dbfn_id, qtype, *dset_mzmls):
    analysis = models.Analysis.objects.get(pk=analysis_id)
    nfwf = models.NextflowWfVersion.objects.get(pk=wfv_id)
    dbfn = models.LibraryFile.objects.get(pk=dbfn_id).sfile
    stagefiles = {'--tdb': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
    mzmlfiles = filemodels.StoredFile.objects.select_related('rawfile').filter(
        pk__in=dset_mzmls)
    analysisshare = filemodels.ServerShare.objects.get(name=settings.ANALYSISSHARENAME).id
    mzmls = [(x.servershare.name, x.path, x.filename, 
              get_or_create_mzmlentry(x, settings.REFINEDMZML_SFGROUP_ID, analysisshare).id, analysisshare)
             for x in mzmlfiles]
    allinstr = [x['rawfile__producer__name'] for x in mzmlfiles.distinct('rawfile__producer').values('rawfile__producer__name')] 
    if len(allinstr) > 1:
        raise RuntimeError('Trying to run a refiner job on dataset containing more than one instrument is not possible')
    params = ['--instrument']
    params.append('velos' if 'elos' in allinstr else 'qe')
    if qtype != 'labelfree':
        params.extend(['--isobaric', qtype])
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           'repo': nfwf.nfworkflow.repo,
           'name': analysis.name,
           'outdir': analysis.user.username,
           }
    res = tasks.refine_mzmls.delay(run, params, mzmls, stagefiles)
    analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
    analysis.save()
    create_db_task(res.id, job_id, run, params, mzmls, stagefiles)


def auto_run_qc_workflow(job_id, sf_id, analysis_id, wfv_id, dbfn_id):
    """Assumes one file, one analysis"""
    analysis = models.Analysis.objects.get(pk=analysis_id)
    nfwf = models.NextflowWfVersion.objects.get(pk=wfv_id)
    dbfn = models.LibraryFile.objects.get(pk=dbfn_id).sfile
    mzml = filemodels.StoredFile.objects.select_related(
        'rawfile__producer', 'servershare', 'filetype').get(rawfile__storedfile__id=sf_id,
                                                filetype__filetype='mzml')
    
    wf = models.Workflow.objects.filter(shortname__name='QC').last()
    params = ['--mods', 'data/labelfreemods.txt', '--instrument']
    params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
    stagefiles = {'--mzml': (mzml.servershare.name, mzml.path, mzml.filename),
                  '--db': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'rf_id': mzml.rawfile_id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           'repo': nfwf.nfworkflow.repo,
           'name': 'longqc',
           'outdir': 'internal_results',
           }
    views.create_nf_search_entries(analysis, wf.id, nfwf.id, job_id)
    res = tasks.run_nextflow_longitude_qc.delay(run, params, stagefiles)
    analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
    analysis.save()
    create_db_task(res.id, job_id, run, params, stagefiles)


def run_nextflow_getfiles(dset_ids, platenames, fractions, setnames, analysis_id, wf_id, wfv_id, inputs):
    # FIXME setnames will be for files, already given an assoc_id
    return filemodels.StoredFile.objects.filter(pk__in=fractions.keys())


def run_nextflow(job_id, dset_ids, platenames, fractions, setnames, analysis_id, wf_id, wfv_id, inputs, *dset_mzmls):
    """
    inputs is {'params': ['--isobaric', 'tmt10plex'],
               'singlefiles': {'--tdb': tdb_sf_id, ... },}
    or shoudl inputs be DB things fields flag,sf_id (how for mzmls though?)
{'params': ['--isobaric', 'tmt10plex', '--instrument', 'qe', '--nfcore', '--hirief'], 'mzml': ('--mzmls', '{sdir}/*.mzML'), 'singlefiles': {'--tdb': 42659, '--dbsnp': 42665, '--genome': 42666, '--snpfa': 42662, '--cosmic': 42663, '--ddb': 42664, '--blastdb': 42661, '--knownproteins': 42408, '--gtf': 42658, '--mods': 42667}}
    """
    analysis = models.Analysis.objects.select_related('user').get(pk=analysis_id)
    nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
        pk=wfv_id)
    stagefiles = {}
    for flag, sf_id in inputs['singlefiles'].items():
        sf = filemodels.StoredFile.objects.get(pk=sf_id)
        stagefiles[flag] = (sf.servershare.name, sf.path, sf.filename)
    mzmls = [(x.servershare.name, x.path, x.filename, setnames[str(x.id)],
              platenames[str(x.rawfile.datasetrawfile.dataset_id)], fractions.get(str(x.id), False)) for x in
             filemodels.StoredFile.objects.filter(pk__in=dset_mzmls)]
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           'repo': nfwf.nfworkflow.repo,
           'name': analysis.name,
           'outdir': analysis.user.username,
           }
    profiles = ['standard']
    if '--nfcore' in inputs['params']:
        inputs['params'] = [x for x in inputs['params'] if x != '--nfcore']
        profiles.extend(['docker', 'lehtio'])
    res = tasks.run_nextflow_workflow.delay(run, inputs['params'], mzmls, stagefiles, ','.join(profiles))
    analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
    analysis.save()
    create_db_task(res.id, job_id, run, inputs['params'], mzmls, stagefiles)
