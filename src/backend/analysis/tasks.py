import os
import json
import shutil
import requests
import subprocess
from time import sleep
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from ftplib import FTP
from dulwich.porcelain import clone, reset, fetch
from tempfile import NamedTemporaryFile
from gzip import GzipFile

from django.urls import reverse
from django.utils import timezone
from celery import shared_task, exceptions

from jobs.post import update_db, taskfail_update_db, task_finished
from kantele import settings
from rawstatus.tasks import calc_md5
from analysis.models import UniProtFasta


@shared_task(bind=True, queue=settings.QUEUE_FILE_DOWNLOAD)
def check_ensembl_uniprot_fasta_download(self, dbname, version, organism, dbtype):
    """Checks if there is a new version of ENSEMBL data,
    downloads it to system over FTP"""
    token = check_in_transfer_client(self.request.id, False, 'database')
    dstpath = os.path.join(settings.SHAREMAP[settings.PRIMARY_STORAGESHARENAME],
            settings.LIBRARY_FILE_PATH)
    doneurl = urljoin(settings.KANTELEHOST, reverse('jobs:internalfiledone'))

    fa_data = {'dbname': dbname, 'organism': organism, 'version': version}
    if dbname == 'uniprot':
        uptype = UniProtFasta.UniprotClass[dbtype]
        url = settings.UNIPROT_API.format(settings.UP_ORGS[organism],
                UniProtFasta.url_addons[dbtype])
        desc = f'Uniprot release {version}, {organism}, {uptype.label} fasta'
        with requests.get(url, stream=True) as req, NamedTemporaryFile(mode='wb') as wfp:
            for chunk in req.iter_content(chunk_size=8192):
                if chunk:
                    wfp.write(chunk)
            dstfn = f'Uniprot_{version}_{organism.replace(" ", "_")}_{uptype.label}.fa'
            regresp = register_resultfile(dstfn, wfp.name, token)
            if regresp:
                fa_data.update({'desc': desc, 'dbtype': dbtype})
                transfer_resultfile(dstpath, settings.LIBRARY_FILE_PATH, wfp.name, 
                        settings.PRIMARY_STORAGESHARENAME, regresp, doneurl, token, self.request.id,
                        is_fasta=fa_data)
            else:
                print('File was already downloaded')

    elif dbname == 'ensembl':
        # Download db, use FTP to get file, download zipped via HTTPS and unzip in stream
        url = urlsplit(settings.ENSEMBL_DL_URL.format(version, organism.lower().replace(' ', '_')))
        desc = f'ENSEMBL {organism} release {version} pep.all fasta'
        with FTP(url.netloc) as ftp:
            ftp.login()
            fn = [x for x in ftp.nlst(url.path) if 'pep.all.fa.gz' in x][0]
        # make sure to specify no compression (identity) to server, otherwise the 
        # raw object will be gzipped and when unzipped contain a gzipped file
        with requests.get(urljoin('http://' + url.netloc, fn), 
                headers={'Accept-Encoding': 'identity'}, stream=True).raw as reqfp:
            with NamedTemporaryFile(mode='wb') as wfp, GzipFile(fileobj=reqfp) as gzfp:
                for line in gzfp:
                    wfp.write(line)
                dstfn = f'ENS{version}_{organism.replace(" ", "_")}.fa'
                # Now register download in Kantele, still in context manager
                # since tmp file will be deleted on close()
                regresp = register_resultfile(dstfn, wfp.name, token)
                if regresp:
                    fa_data['desc'] = desc
                    transfer_resultfile(dstpath, settings.LIBRARY_FILE_PATH, wfp.name, 
                            settings.PRIMARY_STORAGESHARENAME, regresp, doneurl, token,
                            self.request.id, is_fasta=fa_data)
                else:
                    print('File was already downloaded')
    task_finished(self.request.id)
    print(f'Finished downloading {desc}')
        


def run_nextflow(run, params, rundir, gitwfdir, profiles, nf_version):
    """Fairly generalized code for kantele celery task to run a WF in NXF"""
    print('Starting nextflow workflow {}'.format(run['nxf_wf_fn']))
    outdir = os.path.join(rundir, 'output')
    try:
        clone(run['repo'], gitwfdir, checkout=run['wf_commit'])
    except FileExistsError:
        fetch(gitwfdir, run['repo'])
        reset(gitwfdir, 'hard', run['wf_commit'])
    # FIXME dulwich does not seem to checkout anything, use this until it does
    subprocess.run(['git', 'checkout', run['wf_commit']], check=True, cwd=gitwfdir)
    print('Checked out repo {} at commit {}'.format(run['repo'], run['wf_commit']))
    # There will be files inside data dir of WF repo so we must be in
    # that dir for WF to find them
    cmd = [settings.NXF_COMMAND, 'run', run['nxf_wf_fn'], *params, '--outdir', outdir, '-profile', profiles, '-with-trace', '-resume']
    env = os.environ
    env['NXF_VER'] = nf_version
    if 'token' in run and run['token']:
        nflogurl = urljoin(settings.KANTELEHOST, reverse('analysis:nflog'))
        cmd.extend(['-name', run['token'], '-with-weblog', nflogurl])
    if 'analysis_id' in run:
        log_analysis(run['analysis_id'], 'Running command {}, nextflow version {}'.format(' '.join(cmd), env.get('NXF_VER', 'default')))
    nxf_sub = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=gitwfdir, env=env)
    try:
        stdout, stderr = nxf_sub.communicate()
    except exceptions.SoftTimeLimitExceeded:
        # celery has killed the job (task revoked) make sure nextflow is stopped and not left
        nxf_sub.kill()
        print('Job has been revoked, stopping analysis')
        raise
    else:
        # raise any exceptions nextflow has caused
        if nxf_sub.returncode != 0:
            raise subprocess.CalledProcessError(nxf_sub.returncode, cmd, stdout, stderr=stderr)
    return outdir


def get_dir_content_size(fpath):
    return sum([os.path.getsize(f) for f in os.listdir(fpath) if os.path.isfile(f)])


def log_analysis(analysis_id, message):
    logurl = urljoin(settings.KANTELEHOST, reverse('analysis:appendlog'))
    update_db(logurl, json={'analysis_id': analysis_id, 'message': message})


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_nextflow_workflow(self, run, params, stagefiles, profiles, nf_version):
    print('Got message to run nextflow workflow, preparing')
    # Init
    postdata = {'client_id': settings.APIKEY,
                'analysis_id': run['analysis_id'], 'task': self.request.id,
                'name': run['name'], 'user': run['outdir']}
    rundir = create_runname_dir(run, run['fullname'])

    # stage files, create dirs etc
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles,
            run['infiles'], params)

    if sampletable := run['components']['ISOQUANT_SAMPLETABLE']:
        sampletable_fn = os.path.join(rundir, 'sampletable.txt')
        with open(sampletable_fn, 'w') as fp:
            for sample in sampletable:
                fp.write('\t'.join(sample))
                fp.write('\n')
        params.extend(['--sampletable', sampletable_fn])

    # create input file of filenames
    # depends on inputdef component, which is always in ours but maybe not in other pipelines
    if run['components']['INPUTDEF'] and len(run['infiles']):
        with open(os.path.join(rundir, 'inputdef.txt'), 'w') as fp:
            fp.write('\t'.join(run['components']['INPUTDEF']))
            for fn in run['infiles']:
                fnpath = os.path.join(stagedir, 'infiles', fn['fn'])
                fn_metadata = '\t'.join(fn[x] for x in run['components']['INPUTDEF'][1:]) 
                fp.write(f'\n{fnpath}\t{fn_metadata}')
        params.extend(['--input', os.path.join(rundir, 'inputdef.txt')])

    if 'COMPLEMENT_ANALYSIS' in run['components'] and run['old_mzmls']:
        with open(os.path.join(rundir, 'oldinputdef.txt'), 'w') as fp:
            for fn in run['old_infiles']:
                mzstr = '{}\n'.format(fn)
                fp.write(mzstr)
        params.extend(['--oldmzmldef', os.path.join(rundir, 'oldmzmldef.txt')])
    params = [x if x != 'RUNNAME__PLACEHOLDER' else run['runname'] for x in params]
    outfiles = execute_normal_nf(run, params, rundir, gitwfdir, self.request.id, nf_version, profiles)
    postdata.update({'state': 'ok'})

    fileurl = urljoin(settings.KANTELEHOST, reverse('jobs:internalfiledone'))
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisdone'))
    checksrvurl = urljoin(settings.KANTELEHOST, reverse('analysis:checkfileupload'))

    outpath = os.path.join(run['outdir'], os.path.split(rundir)[-1])
    outdir = os.path.join(settings.SHAREMAP[run['dstsharename']], outpath)
    try:
        os.makedirs(outdir, exist_ok=True)
    except (OSError, PermissionError):
        taskfail_update_db(self.request.id, 'Could not create output directory for analysis results')
        raise
    token = False
    for ofile in outfiles:
        token = check_in_transfer_client(self.request.id, token, 'analysis_output')
        regfile = register_resultfile(os.path.basename(ofile), ofile, token)
        if not regfile:
            continue
        transfer_resultfile(outdir, outpath, ofile, run['dstsharename'], regfile, fileurl, token, 
                self.request.id, analysis_id=run['analysis_id'], checksrvurl=checksrvurl)
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def refine_mzmls(self, run, params, mzmls, stagefiles, profiles, nf_version):
    print('Got message to run mzRefine workflow, preparing')
    rundir = create_runname_dir(run, f'{run["analysis_id"]}_{run["name"]}_{run["timestamp"]}')
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles, mzmls, params)
    # FIXME Should we use components here? -- internal pipe so maybe not?
    with open(os.path.join(rundir, 'mzmldef.txt'), 'w') as fp:
        for fn in mzmls:
            # FIXME not have set, etc, pass rawfnid here!
            fpath = os.path.join(stagedir, 'mzmls', fn['fn']) 
            mzstr = 'f{fpath}\t{fn["sfid"]}\n'
            fp.write(mzstr)
    params.extend(['--mzmldef', os.path.join(rundir, 'mzmldef.txt')])
    outfiles = execute_normal_nf(run, params, rundir, gitwfdir, self.request.id, nf_version, profiles)
    # TODO ideally do this:
    # stage mzML with {dbid}___{filename}.mzML
    # This keeps dbid / ___ split out of the NF workflow 
    outfiles_db = {}
    fileurl = urljoin(settings.KANTELEHOST, reverse('jobs:mzmlfiledone'))
    outpath = os.path.join(run['outdir'], os.path.split(rundir)[-1])
    outfullpath = os.path.join(settings.SHAREMAP[run['dstsharename']], outpath)
    try:
        os.makedirs(outfullpath, exist_ok=True)
    except (OSError, PermissionError):
        taskfail_update_db(self.request.id, 'Could not create output directory for analysis results')
        raise
    token = False
    for fn in outfiles:
        token = check_in_transfer_client(self.request.id, token, 'analysis_output')
        sf_id, newname = os.path.basename(fn).split('___')
        fdata = {'file_id': sf_id, 'newname': newname, 'md5': calc_md5(fn)}
        transfer_resultfile(outfullpath, outpath, fn, run['dstsharename'], fdata, fileurl, token,
                self.request.id)
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:analysisdone'))
    postdata = {'client_id': settings.APIKEY, 'analysis_id': run['analysis_id'],
            'task': self.request.id, 'name': run['name'], 'user': run['outdir'], 'state': 'ok'}
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


def create_runname_dir(run, runname):
    run['runname'] = runname
    rundir = settings.NF_RUNDIRS[run.get('nfrundirname', 'small')]
    return os.path.join(rundir, runname).replace(' ', '_')


def prepare_nextflow_run(run, taskid, rundir, stagefiles, infiles, params):
    if 'analysis_id' in run:
        log_analysis(run['analysis_id'], 'Got message to run workflow, preparing')
    gitwfdir = os.path.join(rundir, 'gitwfs')
    try:
        os.makedirs(rundir, exist_ok=True)
    except (OSError, PermissionError):
        taskfail_update_db(taskid, 'Could not create workdir on analysis server')
        raise
    stagedir = os.path.join(settings.ANALYSIS_STAGESHARE, run['runname'])
    if 'analysis_id' in run:
        log_analysis(run['analysis_id'], 'Checked out workflow repo, staging files')
    print(f'Staging files to {stagedir}')
    for flag, files in stagefiles.items():
        stagefiledir = os.path.join(stagedir, flag.replace('--', ''))
        if len(files) > 1:
            dst = os.path.join(stagefiledir, '*')
        else:
            dst = os.path.join(stagefiledir, files[0][2])
        params.extend([flag, dst])
        try:
            os.makedirs(stagefiledir, exist_ok=True)
        except Exception:
            taskfail_update_db(taskid, f'Could not create dir to stage files for {flag}')
            raise
        try:
            copy_stage_files(stagefiledir, files)
        except Exception:
            taskfail_update_db(taskid, f'Could not stage files for {flag} for analysis')
            raise
    if len(infiles):
        # Files which will be defined in some kind of input.txt file (no --param filename)
        infiledir = os.path.join(stagedir, 'infiles')
        try:
            os.makedirs(infiledir, exist_ok=True)
        except Exception:
            taskfail_update_db(taskid, f'Could not create dir to stage files for input')
            raise
        try:
            copy_stage_files(infiledir, [(x['servershare'], x['path'], x['fn']) for x in infiles])
        except Exception:
            taskfail_update_db(taskid, f'Could not stage files for {flag} for analysis')
            raise
    return params, gitwfdir, stagedir


def copy_stage_files(stagefiledir, files):
    not_needed_files = set(os.listdir(stagefiledir))
    # now actually copy
    for fdata in files:
        fpath = os.path.join(settings.SHAREMAP[fdata[0]], fdata[1], fdata[2])
        fdst = os.path.join(stagefiledir, fdata[2])
        try:
            not_needed_files.remove(fdata[2])
        except KeyError:
            pass
        if os.path.exists(fdst) and not os.path.isdir(fpath) and os.path.getsize(fdst) == os.path.getsize(fpath):
            # file already there
            continue
        elif os.path.exists(fdst) and os.path.isdir(fpath) and get_dir_content_size(fpath) == get_dir_content_size(fdst):
            # file is a dir but also ready
            continue
        elif os.path.exists(fdst):
            # file/dir exists but is not correct, delete first
            os.remove(fdst)
        if os.path.isdir(fpath):
            shutil.copytree(fpath, fdst)
        else:
            shutil.copy(fpath, fdst)
    # Remove obsolete files from stage-file-dir
    # FIXME all shutil/os FS operations must be try/excepted!
    for fn in not_needed_files:
        fpath = os.path.join(stagefiledir, fn)
        if os.path.isdir(fpath):
            shutil.rmtree(fpath)
        else:
            os.remove(fpath)


def process_error_from_nf_log(logfile):
    """Assume the log contains only a traceback as error (and log lines), 
    if not process the NF specific error output"""
    nf_swap_err = 'WARNING: Your kernel does not support swap limit capabilities or the cgroup is not mounted. Memory limited without swap.'
    errorlines = []
    is_traceback = True
    part_of_error = False
    tracelines = []
    with open(logfile) as fp:
        for line in fp:
            if line.strip() == 'Caused by:':
                is_traceback = False
                part_of_error = True
                break
            elif 'Cause:' in line or 'Exception' in line:
                tracelines.append(line.strip())
        if is_traceback:
            errorlines = tracelines[:]
        else:
            for line in fp:
                if line.startswith('  ') and part_of_error:
                    if line.strip() != nf_swap_err:
                        errorlines.append(line.strip())
                elif line.strip() == 'Command error:':
                    part_of_error = True
                elif line[:5] == 'Tip: ':
                    break
                else:
                    part_of_error = False
        return '\n'.join(errorlines)


def execute_normal_nf(run, params, rundir, gitwfdir, taskid, nf_version, profiles):
    log_analysis(run['analysis_id'], 'Staging files finished, starting analysis')
    if not profiles:
        profiles = 'standard'
    try:
        outdir = run_nextflow(run, params, rundir, gitwfdir, profiles, nf_version)
    except subprocess.CalledProcessError as e:
        errmsg = process_error_from_nf_log(os.path.join(gitwfdir, '.nextflow.log'))
        log_analysis(run['analysis_id'], 'Workflow crashed, reporting errors')
        taskfail_update_db(taskid, errmsg)
        raise RuntimeError('Error occurred running nextflow workflow '
                           '{}\n\nERROR MESSAGE:\n{}'.format(rundir, errmsg))
    # Revoked jobs do not need DB-updating, but need just to be stopped, 
    # so do not catch SoftTimeLimit exception

    with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
        nflog = fp.read()
    log_analysis(run['analysis_id'], 'Workflow finished, transferring result and'
                 ' cleaning. Full NF trace log: \n{}'.format(nflog))
    outfiles = [os.path.join(outdir, x) for x in os.listdir(outdir)]
    outfiles = [x for x in outfiles if not os.path.isdir(x)]
    reportfile = os.path.join(rundir, 'output', 'Documentation', 'pipeline_report.html')
    if os.path.exists(reportfile):
        outfiles.append(reportfile)
    return outfiles


@shared_task(bind=True, queue=settings.QUEUE_QC_NXF)
def run_nextflow_longitude_qc(self, run, params, stagefiles, profiles, nf_version):
    print('Got message to run QC workflow, preparing')
    reporturl = urljoin(settings.KANTELEHOST, reverse('jobs:storelongqc'))
    postdata = {'client_id': settings.APIKEY, 'rf_id': run['rf_id'],
                'analysis_id': run['analysis_id'], 'task': self.request.id,
                'instrument': run['instrument'], 'filename': run['filename']}
    rundir = create_runname_dir(run, f'{run["analysis_id"]}_rawfile_{run["rf_id"]}_{run["timestamp"]}')
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, stagefiles, [], params)
    try:
        outdir = run_nextflow(run, params, rundir, gitwfdir, profiles, nf_version)
    except subprocess.CalledProcessError:
        errmsg = process_error_from_nf_log(os.path.join(gitwfdir, '.nextflow.log'))
        log_analysis(run['analysis_id'], 'QC Workflow crashed')
        with open(os.path.join(gitwfdir, 'trace.txt')) as fp:
            header = next(fp).strip('\n').split('\t')
            exitfield, namefield = header.index('exit'), header.index('name')
            for line in fp:
                # exit code 3 -> not enough PSMs, but maybe
                # CANT FIND THIS IN PIPELINE OR MSSTITCH!
                # it would be ok to have pipeline output
                # this message instead
                line = line.strip('\n').split('\t')
                if line[namefield] == 'createPSMPeptideTable' and line[exitfield] == '3':
                    postdata.update({'state': 'error', 'errmsg': 'Not enough PSM data found in file to extract QC from, possibly bad run'})
                    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
                    raise RuntimeError('QC file did not contain enough quality PSMs')
        taskfail_update_db(self.request.id, errmsg)
        raise RuntimeError('Error occurred running QC workflow {rundir}')
    with open(os.path.join(outdir, 'qc.json')) as fp:
        qcreport = json.load(fp)
    log_analysis(run['analysis_id'], 'QC Workflow finished')
    postdata.update({'state': 'ok', 'plots': qcreport})
    report_finished_run(reporturl, postdata, stagedir, rundir, run['analysis_id'])
    return run


def report_finished_run(url, postdata, stagedir, rundir, analysis_id):
    print('Reporting and cleaning up after workflow in {}'.format(rundir))
    # If deletion fails, rerunning will be a problem? TODO wrap in a try/taskfail block
    postdata.update({'log': 'Analysis task completed.', 'analysis_id': analysis_id})
    update_db(url, json=postdata)
    shutil.rmtree(rundir)
    if os.path.exists(stagedir):
        shutil.rmtree(stagedir)


def check_in_transfer_client(task_id, token, filetype):
    url = urljoin(settings.KANTELEHOST, reverse('files:check_in'))
    resp = requests.post(url, json={'client_id': settings.APIKEY, 'token': token,
        'task_id': task_id, 'ftype': filetype})
    resp.raise_for_status()
    response = resp.json()
    print(response)
    if response.get('newtoken', False):
        return response['newtoken']
    else:
        return token


def register_resultfile(fname, fpath, token):
    reg_url = urljoin(settings.KANTELEHOST, reverse('files:register'))
    postdata = {'fn': fname,
                'client_id': settings.APIKEY,
                'md5': calc_md5(fpath),
                'size': os.path.getsize(fpath),
                'date': str(os.path.getctime(fpath)),
                'claimed': True,
                'token': token,
                }
    resp = requests.post(url=reg_url, json=postdata)
    resp.raise_for_status()
    rj = resp.json()
    if not rj['stored']:
        outfile = resp.json()
        outfile.update({'newname': fname, 'md5': postdata['md5']})
        return outfile
    else:
        return False


def transfer_resultfile(outfullpath, outpath, fn, dstsharename, regfile, url, token, task_id,
        analysis_id=False, checksrvurl=False, is_fasta=False):
    '''Copies files from analyses to outdir on result storage.
    outfullpath is absolute destination dir for file
    outpath is the path stored in Kantele DB (for users on the share of outfullpath)
    fn is absolute path to src file
    regfile is dict of registered file with md5, newname, fn_id
    '''
    fname = regfile['newname']
    dst = os.path.join(outfullpath, fname)
    try:
        shutil.copy(fn, dst)
    except:
        taskfail_update_db(task_id, 'Errored when trying to copy files to analysis result destination')
        raise
    os.chmod(dst, 0o640)
    postdata = {'client_id': settings.APIKEY, 'fn_id': regfile['file_id'],
            'outdir': outpath, 'filename': fname, 'token': token, 'dstsharename': dstsharename,
            'analysis_id': analysis_id, 'is_fasta': is_fasta}
    if calc_md5(dst) != regfile['md5']:
        msg = 'Copying error, MD5 of src and dst are different'
        taskfail_update_db(task_id, msg)
        raise RuntimeError(msg)
    else:
        postdata['md5'] = regfile['md5']
    if analysis_id:
        # Not for refine mzMLs
        postdata.update({'ftype': 'analysis_output', 'analysis_id': analysis_id})
        # first check if upload file is OK:
        resp = requests.post(checksrvurl, json={'fname': fname, 'client_id': settings.APIKEY})
        if resp.status_code == 200:
            # Servable file found, upload also to web server
            # Somewhat complex POST to get JSON and files in same request
            response = requests.post(url, files={
                'ana_file': (fname, open(fn, 'rb'), 'application/octet-stream'),
                'json': (None, json.dumps(postdata), 'application/json')})
        else:
            response = update_db(url, files={
                'json': (None, json.dumps(postdata), 'application/json')})
    # Also here, somewhat complex POST to get JSON and files in same request
    else:
        response = update_db(url, files={'json': (None, json.dumps(postdata), 'application/json')})
    response.raise_for_status()
