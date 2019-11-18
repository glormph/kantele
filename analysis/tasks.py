import os
import json
import shutil
import requests
import subprocess
from time import sleep
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from ftplib import FTP
from dulwich.porcelain import clone, reset, pull
from tempfile import NamedTemporaryFile
from gzip import GzipFile

from django.urls import reverse
from django.utils import timezone
from celery import shared_task

from jobs.post import update_db, taskfail_update_db
from kantele import settings
from analysis import qc
from rawstatus.tasks import calc_md5


@shared_task(bind=True, queue=settings.QUEUE_PXDOWNLOAD)
def check_ensembl_uniprot_fasta_download(self):
    """Checks if there is a new version of ENSEMBL data,
    downloads it to system over FTP"""
    def register_transfer_libfile(regresp, dstfn, description, ftype):
        # register transfer, will fire md5 check and create libfile of it
        postdata = {'fn_id': regresp['file_id'],
                    'client_id': settings.ADMIN_APIKEY,
                    'ftype': ftype,
                    'filename': dstfn,
                    }
        resp = requests.post(url=urljoin(settings.KANTELEHOST, reverse('files:transferred')), data=postdata)
        resp.raise_for_status()
        postdata = {'fn_id': regresp['file_id'],
                    'client_id': settings.ADMIN_APIKEY,
                    'desc': description,
                    }
        resp = requests.post(url=urljoin(settings.KANTELEHOST, reverse('files:setlibfile')), data=postdata)
        resp.raise_for_status()
        finished = False
        while True:
            r = requests.get(url=urljoin(settings.KANTELEHOST, 
                reverse('files:checklibfile')), params={'fn_id': regresp['file_id']})
            r.raise_for_status()
            if r.json()['ready']:
                break
            print('Libfile not finished yet, checking in 10 sec')
            sleep(10)

    def register_and_copy_lib_fasta_db(dstfn, wfp):
        postdata = {'fn': dstfn,
                    'client_id': settings.ADMIN_APIKEY,
                    'md5': calc_md5(wfp.name),
                    'size': os.path.getsize(wfp.name),
                    'date': str(os.path.getctime(wfp.name)),
                    'claimed': True,
                    }
        resp = requests.post(url=urljoin(settings.KANTELEHOST, reverse('files:register')), data=postdata)
        try:
            resp.raise_for_status()
        except:
            self.retry(countdown=3600)
        regresp = resp.json()
        # edgecase: if we already have this file due to parallel download, dont proceed.
        # otherwise, copy it to tmp
        already_downloaded = check_md5(regresp['file_id'], 'database', settings.ADMIN_APIKEY) == 'ok'
        print('File already downloaded? {}'.format(already_downloaded))
        if not already_downloaded:
            shutil.copy(wfp.name, os.path.join(settings.SHAREMAP[settings.TMPSHARENAME], dstfn))
            os.chmod(os.path.join(settings.SHAREMAP[settings.TMPSHARENAME], dstfn), 0o640)
        return regresp
    # TODO check sum(fn) to validate ENSEMBL checksum
    # First check ENSEMBL and uniprot
    r = requests.get(settings.ENSEMBL_API, headers={'Content-type': 'application/json'})
    ens_version = r.json()['release'] if r.ok else ''
    r = requests.get(settings.UNIPROT_API, stream=True)
    up_version = r.headers['X-UniProt-Release'] if r.ok else ''
    # verify releases with Kantele
    dbstate = requests.get(url=urljoin(settings.KANTELEHOST, reverse('analysis:checkfastarelease')),
            params={'ensembl': ens_version, 'uniprot': up_version}).json()
    done_url = urljoin(settings.KANTELEHOST, reverse('analysis:setfastarelease'))
    if dbstate['uniprot']:
        print('Uniprot version {} is already stored'.format(up_version))
    else:
        print('Downloading uniprot (H.sapiens, swiss, caniso) version {}'.format(up_version))
        with requests.get(settings.UNIPROT_API, stream=True) as req, NamedTemporaryFile(mode='wb') as wfp:
            for chunk in req.iter_content(chunk_size=8192):
                if chunk:
                    wfp.write(chunk)
            dstfn = 'Swissprot_{}_caniso.fa'.format(up_version)
            regresp = register_and_copy_lib_fasta_db(dstfn, wfp)
        register_transfer_libfile(regresp, dstfn,
                'Uniprot release {} swiss canonical/isoform fasta'.format(up_version), 'database')
        requests.post(done_url, data={'type': 'uniprot', 'version': up_version, 'fn_id': regresp['file_id']})
        print('Finished downloading Uniprot database')
    if dbstate['ensembl']:
        print('ENSEMBL version {} is already stored'.format(up_version))
    else:
        print('Downloading new ENSEMBL Homo sapiens version {}'.format(ens_version))
        # Download db, use FTP to get file, download zipped via HTTPS and unzip in stream
        url = urlsplit(settings.ENSEMBL_DL_URL.format(ens_version))
        with FTP(url.netloc) as ftp:
            ftp.login()
            fn = [x for x in ftp.nlst(url.path) if 'pep.all.fa.gz' in x][0]
        with requests.get(urljoin('https://' + url.netloc, fn), stream=True).raw as reqfp:
            with NamedTemporaryFile(mode='wb') as wfp, GzipFile(fileobj=reqfp) as gzfp:
                for line in gzfp:
                    wfp.write(line)
                dstfn = 'ENS{}_{}'.format(ens_version, os.path.basename(fn).replace('.gz', ''))
                # Now register download in Kantele, still in context manager
                # since tmp file will be deleted on close()
                regresp = register_and_copy_lib_fasta_db(dstfn, wfp)
        register_transfer_libfile(regresp, dstfn, 'ENSEMBL release {} pep.all fasta'.format(ens_version),
                'database')
        # Download biomart for ENSEMBL
        martxml = '<?xml version="1.0" encoding="UTF-8"?> <!DOCTYPE Query> <Query  header="1" completionStamp="1" virtualSchemaName = "default" formatter = "TSV" uniqueRows = "0" count = "" datasetConfigVersion = "0.6" > <Dataset name = "hsapiens_gene_ensembl" interface = "default" > <Attribute name = "ensembl_gene_id" /> <Attribute name = "ensembl_peptide_id" /> <Attribute name = "description" /> <Attribute name = "external_gene_name" /> </Dataset> </Query>'
        with requests.get(settings.BIOMART_URL, params={'query': martxml}, stream=True) as reqfp, NamedTemporaryFile(mode='wb') as wfp:
            for chunk in reqfp.iter_content(chunk_size=8192):
                if chunk:
                    wfp.write(chunk)
            dstfn = 'Biomart_table_ENS{}'.format(ens_version)
            # Now register download in Kantele, still in context manager
            # since tmp file will be deleted on close()
            regresp = register_and_copy_lib_fasta_db(dstfn, wfp)
        register_transfer_libfile(regresp, dstfn, 'Biomart map for ENSEMBL release {}'.format(ens_version),
                'martmap')
        requests.post(done_url, data={'type': 'ensembl', 'version': ens_version, 'fn_id': regresp['file_id']})
        print('Finished downloading ENSEMBL database and mart map')




def run_nextflow(run, params, rundir, gitwfdir, profiles, nf_version=False):
    """Fairly generalized code for kantele celery task to run a WF in NXF"""
    print('Starting nextflow workflow {}'.format(run['nxf_wf_fn']))
    outdir = os.path.join(rundir, 'output')
    try:
        clone(run['repo'], gitwfdir, checkout=run['wf_commit'])
    except FileExistsError:
        pull(gitwfdir, run['repo'])
        reset(gitwfdir, 'hard', run['wf_commit'])
    # FIXME dulwich does not seem to checkout anything, use this until it does
    subprocess.run(['git', 'checkout', run['wf_commit']], check=True, cwd=gitwfdir)
    print('Checked out repo {} at commit {}'.format(run['repo'], run['wf_commit']))
    # There will be files inside data dir of WF repo so we must be in
    # that dir for WF to find them
    cmd = ['nextflow', 'run', run['nxf_wf_fn'], *params, '--outdir', outdir, '-profile', profiles, '-with-trace', '-resume']
    print(cmd)
    env = os.environ
    if nf_version:
        env['NXF_VER'] = nf_version
    log_analysis(run['analysis_id'], 'Running command {}, nextflow version {}'.format(' '.join(cmd), env.get('NXF_VER', 'default')))
    subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=gitwfdir, env=env)
    return rundir


def stage_files(stagedir, stagefiles, params=False):
    if not os.path.exists(stagedir):
        os.makedirs(stagedir)
    for flag, fdata in stagefiles.items():
        fpath = os.path.join(settings.SHAREMAP[fdata[0]], fdata[1], fdata[2])
        dst = os.path.join(stagedir, fdata[2])
        if not os.path.exists(dst):
            shutil.copy(fpath, dst)
        if params:
            params.extend([flag, dst])
    return params


def log_analysis(analysis_id, message):
    logurl = urljoin(settings.KANTELEHOST, reverse('analysis:appendlog'))
    entry = '[{}] - {}'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), message)
    update_db(logurl, json={'analysis_id': analysis_id, 'message': entry})


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_nextflow_workflow(self, run, params, mzmls, stagefiles, profiles):
    print('Got message to run nextflow workflow, preparing')
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisdone'))
    postdata = {'client_id': settings.APIKEY,
                'analysis_id': run['analysis_id'], 'task': self.request.id}
    rundir = create_runname_dir(run)
    # write sampletable if it is present
    sampletable = False
    try:
        st_ix = params.index('SAMPLETABLE')
    except ValueError:
        pass
    else:
        sampletable = params[st_ix + 1]
        params = params[0:st_ix] + params[st_ix + 2:]
        print('Sampletable found')
    # stage files, create dirs etc
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles, mzmls, params)
    if sampletable:
        sampletable_fn = os.path.join(rundir, 'sampletable.txt')
        with open(sampletable_fn, 'w') as fp:
            for sample in sampletable:
                fp.write('\t'.join(sample))
                fp.write('\n')
        params.extend(['--sampletable', sampletable_fn])
    # create input file of filenames
    with open(os.path.join(rundir, 'mzmldef.txt'), 'w') as fp:
        for fn in mzmls:
            # set/plate/fraction in LC runs are channel/samplename
            mzstr = '{fpath}\t{setn}'.format(fpath=os.path.join(stagedir, fn[2]), setn=fn[3])
            if fn[4]:  # if a plate is speced, use plate and fraction if they are speced
                mzstr = '{ms}\t{pl}'.format(ms=mzstr, pl=fn[4])
                if len(fn) > 5 and fn[5]:
                    mzstr = '{ms}\t{fr}'.format(ms=mzstr, fr=fn[5])
            mzstr = '{}\n'.format(mzstr)
            fp.write(mzstr)
    params.extend(['--mzmldef', os.path.join(rundir, 'mzmldef.txt')])
    params = [x if x != 'RUNNAME__PLACEHOLDER' else run['runname'] for x in params]
    outfiles = execute_normal_nf(run, params, rundir, gitwfdir, self.request.id, profiles=profiles)
    postdata.update({'state': 'ok'})
    outfiles_db = register_resultfiles(outfiles)
    fileurl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisfile'))
    fn_ids = transfer_resultfiles(run['outdir'], rundir, outfiles_db, run['analysis_id'], fileurl, self.request.id)
    check_rawfile_resultfiles_match(fn_ids)
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def refine_mzmls(self, run, params, mzmls, stagefiles):
    print('Got message to run mzRefine workflow, preparing')
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisdone'))
    postdata = {'client_id': settings.APIKEY,
                'analysis_id': run['analysis_id'], 'task': self.request.id}
    rundir = create_runname_dir(run)
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles, mzmls, params)
    with open(os.path.join(rundir, 'mzmldef.txt'), 'w') as fp:
        # FIXME does not write to mzmldef!
        for fn in mzmls:
            # FIXME not have set, etc, pass rawfnid here!
            mzstr = '{fpath}\t{refined_sfid}\n'.format(fpath=os.path.join(stagedir, fn[2]), refined_sfid=fn[3])
            fp.write(mzstr)
    params.extend(['--mzmldef', os.path.join(rundir, 'mzmldef.txt')])
    outfiles = execute_normal_nf(run, params, rundir, gitwfdir, self.request.id)
    outfiles_db = {fn: {'file_id': os.path.basename(fn).split('___')[0], 'md5': calc_md5(fn)}
                   for fn in outfiles}
    postdata.update({'state': 'ok'})
    fileurl = urljoin(settings.KANTELEHOST, reverse('jobs:mzrefinefile'))
    fn_ids = transfer_resultfiles(run['outdir'], rundir, outfiles_db, run['analysis_id'], fileurl, self.request.id)
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


def create_runname_dir(run):
    runname = '{}_{}_{}'.format(run['analysis_id'], run['name'], run['timestamp'])
    run['runname'] = runname
    rundir = settings.NF_RUNDIRS[run.get('rundirname', 'small')]
    return os.path.join(rundir, runname).replace(' ', '_')


def prepare_nextflow_run(run, taskid, rundir, stagefiles, mzmls, params):
    log_analysis(run['analysis_id'], 'Got message to run workflow, preparing')
    # runname is set in task so timestamp corresponds to execution start and not job queue
    gitwfdir = os.path.join(rundir, 'gitwfs')
    if not os.path.exists(rundir):
        try:
            os.makedirs(rundir)
        except (OSError, PermissionError):
            taskfail_update_db(taskid, 'Could not create workdir on analysis server')
            raise
    stagedir = os.path.join(settings.ANALYSIS_STAGESHARE, run['runname'])
    log_analysis(run['analysis_id'], 'Checked out workflow repo, staging files')
    print('Staging files to {}'.format(stagedir))
    try:
        params = stage_files(stagedir, stagefiles, params)
        stage_files(stagedir, {x[2]: x for x in mzmls})
    except:
        taskfail_update_db(taskid, 'Could not stage files for analysis')
        raise
    return params, gitwfdir, stagedir


def execute_normal_nf(run, params, rundir, gitwfdir, taskid, profiles=False):
    log_analysis(run['analysis_id'], 'Staging files finished, starting analysis')
    if not profiles:
        profiles = 'standard'
    nf_version = settings.NXF_VER
    if '--nf1901' in params:
        params.pop(params.index('--nf1901'))
        nf_version = '19.01.0'
    try:
        run_nextflow(run, params, rundir, gitwfdir, profiles, nf_version)
    except subprocess.CalledProcessError as e:
        # FIXME report stderr with e
        errmsg = 'OUTPUT:\n{}\nERROR:\n{}'.format(e.stdout, e.stderr)
        taskfail_update_db(taskid, errmsg)
        raise RuntimeError('Error occurred running nextflow workflow '
                           '{}\n\nERROR MESSAGE:\n{}'.format(rundir, errmsg))
    with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
        nflog = fp.read()
    log_analysis(run['analysis_id'], 'Workflow finished, transferring result and'
                 ' cleaning. NF log: \n{}'.format(nflog))
    outfiles = [os.path.join(rundir, 'output', x) for x in os.listdir(os.path.join(rundir, 'output'))]
    outfiles = [x for x in outfiles if not os.path.isdir(x)]
    reportfile = os.path.join(rundir, 'output', 'Documentation', 'pipeline_report.html')
    if os.path.exists(reportfile):
        outfiles.append(reportfile)
    return outfiles


@shared_task(bind=True, queue=settings.QUEUE_QC_NXF)
def run_nextflow_longitude_qc(self, run, params, stagefiles):
    print('Got message to run QC workflow, preparing')
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:storelongqc'))
    postdata = {'client_id': settings.APIKEY, 'rf_id': run['rf_id'],
                'analysis_id': run['analysis_id'], 'task': self.request.id}
    mzmls = {}
    rundir = create_runname_dir(run)
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles, mzmls, params)
    try:
        run_nextflow(run, params, rundir, gitwfdir, profiles='qc')
    except subprocess.CalledProcessError:
        with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
            header = next(fp).strip('\n').split('\t')
            exitfield, namefield = header.index('exit'), header.index('name')
            for line in fp:
                line = line.strip('\n').split('\t')
                if line[namefield] == 'createPSMPeptideTable' and line[exitfield] == '3':
                    postdata.update({'state': 'error', 'errmsg': 'Not enough PSM data found in file to extract QC from, possibly bad run'})
                    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
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
    fileurl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisfile'))
    outfiles_db = register_resultfiles(qcfiles.values())
    fn_ids = transfer_resultfiles(run['outdir'], rundir, outfiles_db, run['analysis_id'], fileurl, self.request.id)
    check_rawfile_resultfiles_match(fn_ids)
    with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
        nflog = fp.read()
    log_analysis(run['analysis_id'], 'Workflow finished, transferring result and'
                 ' cleaning. NF log: \n{}'.format(nflog))
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


def check_md5(fn_id, ftype, apikey=False):
    if not apikey:
        apikey = settings.APIKEY
    checkurl = urljoin(settings.KANTELEHOST, reverse('files:md5check'))
    params = {'client_id': apikey, 'fn_id': fn_id, 'ftype': ftype}
    resp = requests.get(url=checkurl, params=params, verify=settings.CERTFILE)
    return resp.json()['md5_state']


def report_finished_run(url, postdata, stagedir, rundir, analysis_id):
    print('Reporting and cleaning up after workflow in {}'.format(rundir))
    # If deletion fails, rerunning will be a problem? TODO wrap in a try/taskfail block
    postdata.update({'log': '[{}] - Analysis completed.'.format(
        datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S')),
                     'analysis_id': analysis_id})
    shutil.rmtree(rundir)
    shutil.rmtree(stagedir)
    update_db(url, json=postdata)


def register_resultfiles(outfiles):
    # First register files, check md5, prune those
    reg_url = urljoin(settings.KANTELEHOST, reverse('files:register'))
    outfiles_db = {}
    for fn in outfiles:
        postdata = {'fn': os.path.basename(fn),
                    'client_id': settings.APIKEY,
                    'md5': calc_md5(fn),
                    'size': os.path.getsize(fn),
                    'date': str(os.path.getctime(fn)),
                    'claimed': True,
                    }
        resp = requests.post(url=reg_url, data=postdata, verify=settings.CERTFILE)
        resp.raise_for_status()
        rj = resp.json()
        # check md5 of file so we can skip already transferred files in reruns
        if not check_md5(rj['file_id'], 'analysis_output') == 'ok':
            outfiles_db[fn] = resp.json()
    return outfiles_db


def transfer_resultfiles(userdir, rundir, outfiles_db, analysis_id, url, task_id):
    """Copies analysis results to data server"""
    outpath = os.path.join(userdir, os.path.split(rundir)[-1])
    outdir = os.path.join(settings.SHAREMAP[settings.ANALYSISSHARENAME],
                          outpath)
    try:
        if not os.path.exists(outdir):
            os.makedirs(outdir)
    except (OSError, PermissionError):
        taskfail_update_db(task_id)
        raise
    for fn in outfiles_db:
        filename = os.path.basename(fn)
        dst = os.path.join(outdir, filename)
        try:
            shutil.copy(fn, dst)
        except:
            taskfail_update_db(task_id)
            raise
        if 'md5' in outfiles_db[fn] and calc_md5(dst) != outfiles_db[fn]['md5']:
            taskfail_update_db(task_id)
            raise RuntimeError('Copying error, MD5 of src and dst are different')
        postdata = {'client_id': settings.APIKEY, 'fn_id': outfiles_db[fn]['file_id'],
                    'outdir': outpath, 'filename': filename,
                    'ftype': 'analysis_output', 'analysis_id': analysis_id}
        if 'md5' in outfiles_db[fn]:
            postdata['md5'] = outfiles_db[fn]['md5']
        response = update_db(url, form=postdata)
        response.raise_for_status()
    return {x['file_id']: False for x in outfiles_db.values()}


def check_rawfile_resultfiles_match(fn_ids):
    while False in fn_ids.values():
        for fn_id, checked in fn_ids.items():
            if not checked:
                fn_ids[fn_id] = check_md5(fn_id, 'analysis_output')
                if fn_ids[fn_id] == 'error':
                    taskfail_update_db(task_id)
                    raise RuntimeError
        sleep(30)
