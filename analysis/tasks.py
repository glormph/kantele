import os
import json
import shutil
import subprocess
from urllib.parse import urljoin
from dulwich.porcelain import clone, reset

from django.urls import reverse
from celery import shared_task
from bioblend.galaxy import GalaxyInstance

from jobs.post import update_db, taskfail_update_db
from kantele import settings
from analysis import qc, galaxy


def run_nextflow(run, params, stagefiles, task_id):
    """Fairly generalized code for kantele celery task to run a WF in NXF"""
    runname = 'longqc_{}'.format(run['timestamp'])
    rundir = os.path.join(settings.NEXTFLOW_RUNDIR, runname)
    stagedir = os.path.join(rundir, 'stage')
    gitwfdir = os.path.join(rundir, 'gitwfs')
    if not os.path.exists(rundir):
        os.makedirs(rundir)
    if not os.path.exists(stagedir):
        os.makedirs(stagedir)
    try:
        clone('https://github.com/lehtiolab/galaxy-workflows',
              gitwfdir, checkout=run['commit'])
    except FileExistsError:
        reset(gitwfdir, 'hard', run['commit'])
    for fn, fndata in stagefiles.items():
        fpath = os.path.join(settings.SHAREMAP[fndata[0]], fndata[1], fn)
        dst = os.path.join(stagedir, fn)
        if not os.path.exists(dst):
            shutil.copy(fpath, dst)
    # TODO stagefiles should probably not be looked up like this from params:
    cmdparams = [os.path.join(stagedir, x) if x in stagefiles else x
                 for x in params]
    try:
        # There will be files inside data dir of WF repo so we must be in
        # that dir for WF to find them
        subprocess.run(['nextflow', 'run', run['nxf_wf_fn'], *cmdparams,
                        '--outdir', 'output', '-resume'], check=True,
                       cwd=gitwfdir)
    except subprocess.CalledProcessError:
        taskfail_update_db(task_id)
        raise RuntimeError('Error occurred running QC workflow '
                           '{}'.format(rundir))
    return rundir


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_nextflow_longitude_qc(self, run, params, stagefiles):
    rundir = run_nextflow(run, params, stagefiles, self.request.id)
    outfiles = {}
    # TODO Ideally have dynamic output dict defined in a JSON in nextflow repo?
    for exp_out, expfn in {'sqltable': 'mslookup_db.sqlite',
                           'psmtable': 'psmtable.txt',
                           'peptable': 'peptable.txt',
                           'prottable': 'prottable.txt'}.items():
        outfile = os.path.join(rundir, 'output', expfn)
        if not os.path.exists(outfile):
            taskfail_update_db(self.request.id)
            raise RuntimeError('Ran QC workflow but output file {} not '
                               'found'.format(outfile))
        outfiles[exp_out] = os.path.abspath(outfile)
    qcreport = qc.calc_longitudinal_qc(outfiles)
    postdata = {'client_id': settings.APIKEY, 'rf_id': run['rf_id'],
                'analysis_id': run['analysis_id'], 'plots': qcreport,
                'task': self.request.id}
    url = urljoin(settings.KANTELEHOST, reverse('dash:storeqc'))
    try:
        update_db(url, json=postdata)
        transfer_resultfiles('internal_results', rundir, outfiles)
        shutil.rmtree(rundir)
    except RuntimeError:
        taskfail_update_db(self.request.id)
        raise
    return run


def transfer_resultfiles(userdir, rundir, outfiles):
    """Copies analysis results to data server"""
    # FIXME need scp for this
    outdir = os.path.join(settings.SHAREMAP[settings.ANALYSISSHARENAME],
                          userdir, os.path.split(rundir)[-1])
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    for name, fn in outfiles.items():
        shutil.copy(fn, os.path.join(outdir, os.path.basename(fn)))
