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


def run_nextflow(run, params, stagefiles, rundir, gitwfdir):
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
    # TODO stagefiles should probably not be looked up like this from params:
    cmdparams = [os.path.join(stagedir, x) if x in stagefiles else x
                 for x in params]
    # There will be files inside data dir of WF repo so we must be in
    # that dir for WF to find them
    subprocess.run(['nextflow', 'run', run['nxf_wf_fn'], *cmdparams,
                    '--outdir', outdir, '-with-trace', '-resume'], check=True,
                   cwd=gitwfdir)
    return rundir


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
        run_nextflow(run, params, stagefiles, rundir, gitwfdir)
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
    postdata.update({'state': 'ok', 'plots': qcreport})
    report_finished_run(postdata, self.request.id, rundir, outfiles)
    return run


def report_finished_run(postdata, task_id, rundir, outfiles=False):
    with open('report.json', 'w') as fp:
        json.dump(postdata, fp)
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:storelongqc'))
    try:
        update_db(reporturl, json=postdata)
        if outfiles:
            transfer_resultfiles('internal_results', rundir, outfiles)
        shutil.rmtree(rundir)
    except RuntimeError:
        taskfail_update_db(task_id)
        raise


def transfer_resultfiles(userdir, rundir, outfiles):
    """Copies analysis results to data server"""
    # FIXME need scp for this
    outdir = os.path.join(settings.SHAREMAP[settings.ANALYSISSHARENAME],
                          userdir, os.path.split(rundir)[-1])
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    for name, fn in outfiles.items():
        shutil.copy(fn, os.path.join(outdir, os.path.basename(fn)))
