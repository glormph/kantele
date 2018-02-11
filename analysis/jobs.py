import os
from datetime import datetime

from celery import chain

from jobs.post import save_task_chain
from analysis import galaxy, tasks, models
from rawstatus import models as filemodels


def auto_run_qc_workflow(job_id, sf_id, analysis_id):
    """Assumes one file, one analysis"""
    analysis = models.Analysis.objects.select_related(
        'search__workflow', 'account').get(pk=analysis_id)
    mzml = filemodels.StoredFile.objects.get(pk=sf_id).select_related(
        'rawfile__producer')
    params = ['--mzml', mzml, '--db', dbfn, '--mods', 'data/labelfreemods.txt',
              '--instrument']
    params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
    run['timestamp'] = datetime.strftime(analysis.date, '%Y%m%d_%H.%M')
    res = tasks.run_nextflow_longitude_qc(run, commit, nffile, params, stagefiles)
    # FIXME when analysis already queued and going to rerun we need to skip
    # some things (stageing, wd creation, checkout etc)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')


def keeparound():
    targetdb = models.GalaxyLibDataset.objects.get(pk=qcparams['target db'])
    run['params']['MS-GF+'] = galaxy.get_msgf_inputs(run['params'])


