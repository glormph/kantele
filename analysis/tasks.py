import os
import json
import shutil
import subprocess
from urllib.parse import urljoin
from dulwich.porcelain import clone, reset, pull

from django.urls import reverse
from celery import shared_task

from jobs.post import update_db, taskfail_update_db
from kantele import settings
from analysis import qc, galaxy


def run_nextflow(run, params, stagefiles, nonstagefiles, rundir, gitwfdir):
    """Fairly generalized code for kantele celery task to run a WF in NXF"""
    stagedir = os.path.join(rundir, 'stage')
    outdir = os.path.join(rundir, 'output')
    if not os.path.exists(stagedir):
        os.makedirs(stagedir)
    try:
        clone(run['repo'], gitwfdir, checkout=run['wf_commit'])
    except FileExistsError:
        pull(gitwfdir, wfrepo)
        reset(gitwfdir, 'hard', run['wf_commit'])
    for fn, fndata in stagefiles.items():
        fpath = os.path.join(settings.SHAREMAP[fndata[0]], fndata[1], fn)
        dst = os.path.join(stagedir, fn)
        if not os.path.exists(dst):
            shutil.copy(fpath, dst)
    # TODO stagefiles/nonstage should probably not be looked up like this from params:
    cmdparams = [os.path.join(stagedir, x) if x in stagefiles else x
                 for x in params]
    cmdparams = [os.path.join(settings.SHAREMAP[nonstagefiles[x][0]], 
                              nonstagefiles[x][1], x) 
                 if x in nonstagefiles else x for x in cmdparams]
    # There will be files inside data dir of WF repo so we must be in
    # that dir for WF to find them
    subprocess.run(['nextflow', 'run', run['nxf_wf_fn'], *cmdparams,
                    '--outdir', outdir, '-with-trace', '-resume'], check=True,
                   cwd=gitwfdir)
    return rundir


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_nextflow_ipaw(self, run, params, stagefiles, nonstagefiles):
    postdata = {'client_id': settings.APIKEY,
                'analysis_id': run['analysis_id'], 'task': self.request.id}
    runname = 'ipaw_{}_{}_{}'.format(run['analysis_id'], run['name'], run['timestamp'])
    rundir = os.path.join(settings.NEXTFLOW_RUNDIR, runname)
    gitwfdir = os.path.join(rundir, 'gitwfs')
    if not os.path.exists(rundir):
        os.makedirs(rundir)
    params.extend(['--mzmls', '{}/\\*.mzML'.format(os.path.join(rundir, 'stage'))])
    try:
        run_nextflow(run, params, stagefiles, nonstagefiles, rundir, gitwfdir)
    except subprocess.CalledProcessError:
        taskfail_update_db(self.request.id)
        raise RuntimeError('Error occurred running iPAW workflow '
                           '{}'.format(rundir))
    outfiles = os.listdir(os.path.join(rundir, 'output'))
    outfiles = [os.path.join(rundir, 'output', x) for x in outfiles]
    postdata.update({'state': 'ok'})
    report_finished_run(postdata, self.request.id, rundir, outfiles)
    return run


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_nextflow_longitude_qc(self, run, params, stagefiles):
    postdata = {'client_id': settings.APIKEY, 'rf_id': run['rf_id'],
                'analysis_id': run['analysis_id'], 'task': self.request.id}
    runname = 'longqc_{}_{}'.format(run['analysis_id'], run['timestamp'])
    rundir = os.path.join(settings.NEXTFLOW_RUNDIR, runname)
    gitwfdir = os.path.join(rundir, 'gitwfs')
    if not os.path.exists(rundir):
        os.makedirs(rundir)
    try:
        run_nextflow(run, params, stagefiles, {}, rundir, gitwfdir)
    except subprocess.CalledProcessError:
        with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
            header = next(fp).strip('\n').split('\t')
            exitfield, namefield = header.index('exit'), header.index('name')
            for line in fp:
                line = line.strip('\n').split('\t')
                if line[namefield] == 'createPSMPeptideTable' and line[exitfield] == '3':
                    postdata.update({'state': 'error', 'errmsg': 'Not enough PSM data found in file to extract QC from, possibly bad run'})
                    report_finished_run(postdata, self.request.id, rundir)
                    raise RuntimeError('QC file did not contain enough quality PSMs')
        taskfail_update_db(self.request.id)
        raise RuntimeError('Error occurred running QC workflow '
                           '{}'.format(rundir))
    outfiles = os.listdir(os.path.join(rundir, 'output'))
    # TODO hardcoded is probably not a good idea
    qcfiles = {}
    expect_out = {'sqltable': 'mslookup_db.sqlite', 'psmtable': 'psmtable.txt',
                  'peptable': 'peptable.txt', 'prottable': 'prottable.txt'}
    if set(expect_out.values()).difference(outfiles):
        taskfail_update_db(self.request.id)
        raise RuntimeError('Ran QC workflow but output file {} not '
                           'found'.format(expfn))
    qcfiles = {x: os.path.join(rundir, 'output', fn) for x, fn 
               in expect_out.items()}
    qcreport = qc.calc_longitudinal_qc(qcfiles)
    postdata.update({'state': 'ok', 'plots': qcreport})
    report_finished_run(postdata, self.request.id, 'internal_results', rundir,
                        qcfiles.values())
    return run


def report_finished_run(postdata, task_id, userdir, rundir, outfiles=False):
    with open('report.json', 'w') as fp:
        json.dump(postdata, fp)
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:storelongqc'))
    try:
        if outfiles:
            transfer_resultfiles(userdir, rundir, outfiles)
        shutil.rmtree(rundir)
        update_db(reporturl, json=postdata)
    except RuntimeError:
        taskfail_update_db(task_id)
        raise


def transfer_resultfiles(userdir, rundir, outfiles):
    """Copies analysis results to data server"""
    # TODO need scp for this, including a firewall opening
    outdir = os.path.join(settings.SHAREMAP[settings.ANALYSISSHARENAME],
                          userdir, os.path.split(rundir)[-1])
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    for fn in outfiles:
        shutil.copy(fn, os.path.join(outdir, os.path.basename(fn)))
