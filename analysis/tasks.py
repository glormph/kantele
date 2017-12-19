import os
import json
import shutil
import subprocess
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task
from bioblend.galaxy import GalaxyInstance

from jobs.post import update_db
from kantele import settings
from analysis import qc, galaxy


def get_galaxy_instance(inputstore):
    return GalaxyInstance(settings.GALAXY_URL, inputstore['apikey'])


def runtime_and_upload(wf_json, run):
    print('Filling in runtime values...')
    gi = get_galaxy_instance(run)
    for step in wf_json['steps'].values():
        galaxy.fill_runtime_params(step, run['params'])
    print('Uploading workflow...')
    run['galaxy_wf_id'] = gi.workflows.import_workflow_json(wf_json)
    run['wf'] = wf_json
    return run


@shared_task(queue=settings.QUEUE_STORAGE, bind=True)
def store_summary(self, run):
    """Stores workflow JSON files, and other dataset choices in
    a report file"""
    print('Storing summary for search {}'.format(run['outdir']))
    gi = get_galaxy_instance(run)
    outpath_full = os.path.join(settings.STORAGESHARE, run['outdir'])
    if not os.path.exists(outpath_full) or not os.path.isdir(outpath_full):
        os.makedirs(outpath_full)
    wfname = 'workflow_{}'.format(run['wf']['name'])
    with open(os.path.join(outpath_full, wfname), 'w') as fp:
        json.dump(run['wf'], fp)
    summaryfn = os.path.join(outpath_full, 'summary.json')
    run['summary'] = summaryfn
    summary = {'datasets': {}, 'params': run['params'],
               'job_results': []}
    for name, dset in run['datasets'].items():
        if 'id' in dset and dset['id'] is not None:
            summary['datasets'][name] = dset
            if dset['src'] not in ['ld', 'disk']:
                print('Dataset {} : {} neither in library nor file on disk, '
                      'probably Galaxy ID: fetching'.format(name, dset['id']))
                gname = gi.datasets.show_dataset(dset['id'])['name']
                summary['datasets'][name]['galaxy_name'] = gname
    with open(summaryfn, 'w') as fp:
        json.dump(summary, fp)
    print('Summary stored')
    return run


@shared_task(queue=settings.QUEUE_PROD_STAGE, bind=True)
def stage_infile(self, run, number):
    rawfile = run['raw'][number]
    print('Staging {} to production'.format(rawfile))
    src = os.path.join(settings.GALAXY_STORAGE_MOUNTPATH, rawfile)
    gi = get_galaxy_instance(run)
    run['source_history'] = gi.histories.create_history(
        name='{}_source'.format(run['name']))['id']
    run['stagefolder'] = os.path.join(settings.PROD_STAGE_MOUNT,
                                      run['source_history'])
    # FIXME try/except here
    try:
        os.makedirs(run['stagefolder'])
    except FileExistsError:
        pass
    shutil.copy(src, os.path.join(run['stagefolder'], rawfile))
    return run


@shared_task(queue=settings.QUEUE_GALAXY_TOOLS, bind=True)
def import_staged_file(self, run, number):
    """Inputstore will contain one raw file, and a galaxy history.
    Raw file will have a file_id which can be read by the DB"""
    sourceinfo = run['raw'][number]
    rawfile = os.path.basename(sourceinfo['name'])
    print('Copy-importing {} to galaxy history '
          '{}'.format(rawfile, run['source_history']))
    gi = get_galaxy_instance(run)
    tool_inputs = {
        'folder': run['stagefolder'],
        'filename': rawfile,
        'transfertype': 'link',
        'dtype': 'mzml',
    }
    dset = gi.tools.run_tool(
        run['source_history'], 'testtoolshed.g2.bx.psu.edu/repos/jorritb/'
        'lehtio_input_output/locallink/0.2',
        tool_inputs=tool_inputs)
    state = galaxy.wait_for_copyjob(dset, gi)
    if state == 'ok':
        print('File {} imported'.format(rawfile))
        sourceinfo['galaxy_id'] = dset['outputs'][0]['id']
        return run
    else:
        errormsg = 'Problem copying file {}'.format(rawfile)
        print(errormsg)
        self.retry(exc=errormsg)


@shared_task(queue=settings.QUEUE_GALAXY_WORKFLOW, bind=True)
def run_search_wf(self, run):
    print('Workflow start task: Preparing inputs for workflow '
          'module {}'.format(run['galaxy_wf_id']))
    gi = get_galaxy_instance(run)
    if run['datasets']['spectra']['id'] is None:
        run = galaxy.collect_spectra(run, gi)
    try:
        run['history'] = gi.histories.create_history(
            name=run['galaxyname'])['id']
    except:
        self.retry(countdown=60)
    mod_inputs = galaxy.get_input_map_from_json(run['wf'], run['datasets'])
    print('Invoking workflow {} with id {}'.format(run['wf']['name'],
                                                   run['galaxy_wf_id']))
    try:
        gi.workflows.invoke_workflow(run['galaxy_wf_id'], inputs=mod_inputs,
                                     history_id=run['history'])
    except Exception as e:
        # Workflows are invoked so requests are fast, no significant
        # risk for timeouts
        print('Problem, retrying, error was {}'.format(e))
        self.retry(countdown=60, exc=e)
    print('Workflow invoked')
    return run


@shared_task(queue=settings.QUEUE_STORAGE, bind=True)
def longitudinal_qc(self, run):
    """DOwnloads results from galaxy to QC analysis folder,
    calculates QC and passes to DB Then removes the workdir"""
    gi = get_galaxy_instance(run)
    infiles = {}
    try:
        for infile, gdata in run['output_dsets']:
            infiles[infile] = gi.datasets.show_dataset(gdata['id'])['file_name']
    except:
        self.retry(countdown=60)
    qcmap = qc.calc_longitudinal_qc(infiles)
    postdata = {'client_id': settings.APIKEY, 'rf_id': run['rf_id'],
                'analysis_id': run['analysis_id'], 'plots': qcmap}
    url = urljoin(settings.KANTELEHOST, reverse('dash:storeqc'))
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        raise
    return run


@shared_task(queue=settings.QUEUE_STORAGE, bind=True)
def download_results(self, run, qc=False):
    """Downloads both zipped collections and normal datasets"""
    print('Got command to download results to disk from Galaxy for history '
          '{}'.format(run['history']))
    gi = get_galaxy_instance(run)
    outpath_full = os.path.join(settings.ANALYSIS_STORAGESHARE,
                                run['outdir'])
    try:
        run = galaxy.get_datasets_to_download(run, outpath_full, gi)
        run = galaxy.wait_for_completion(run, gi)
    except Exception as e:
        print('Problem downloading datasets, retrying in 60s. '
              'Problem message:', e)
        self.retry(countdown=60, exc=e)
    for dset in run['output_dsets'].values():
        if dset['download_url'][:4] != 'http':
            dset['download_url'] = '{}{}'.format(settings.GALAXY_URL,
                                                 dset['download_url'])
        dlcmd = ['curl', '-o', dset['download_dest'], dset['download_url']]
        print('running: {}'.format(dlcmd))
        try:
            subprocess.check_call(dlcmd)
        except BaseException as e:
            print('Problem occurred downloading: {}'.format(e))
            self.retry(countdown=60)
    print('Finished downloading results to disk for history '
          '{}. Writing up stdout'.format(run['history']))
    if not qc:
        write_stdouts(run, outpath_full, gi)
    return run


@shared_task(queue=settings.QUEUE_PROD_STAGE, bind=True)
def cleanup(self, run):
    gi = get_galaxy_instance(run)
    print('Deleting history {}'.format(run['history']))
    try:
        gi.histories.delete_history(run['history'], purge=True)
        if not run['keep_source']:
            print('Deleting source history {}'.format(run['source_history']))
            gi.histories.delete_history(run['source_history'], purge=True)
    except:
        self.retry(countdown=60)
    print('Deleting staged files')
    stage = os.path.join(settings.PROD_STAGE_MOUNT, run['source_history'])
    try:
        shutil.rmtree(stage)
    except:
        print('Could not delete staged dir {}'.format(stage))
        raise
    return run


def write_stdouts(run, outpath_full, gi):
    if run['params']['multiplextype'] is None:
        return
    hiscon = gi.histories.show_history(run['history'], contents=True)
    possible_dscols = [x for x in hiscon
                       if x['name'][:20] == 'Create peptide table'
                       and x['history_content_type'] == 'dataset_collection']
    stdouts = {}
    for pepdscol in possible_dscols:
        coldsets = gi.histories.show_dataset_collection(run['history'],
                                                        pepdscol['id'])
        for colds in coldsets['elements']:
            pep_job = gi.jobs.show_job(gi.datasets.show_dataset(
                colds['object']['id'])['creating_job'], full_details=True)
            if 'medians' not in pep_job['stdout']:
                break
            stdouts[colds['element_identifier']] = pep_job['stdout']
    summaryfn = os.path.join(outpath_full, 'summary.json')
    with open(summaryfn) as fp:
        report = json.load(fp)
    report['stdout'] = {'normalizing medians': stdouts}
    with open(summaryfn, 'w') as fp:
        json.dump(report, fp, indent=2)


@shared_task(queue=settings.QUEUE_GALAXY_TOOLS, bind=True)
def misc_files_copy(self, inputstore, filelist):
    """Inputstore will contain some files that are on storage server, which
    §may be imported to search history. E.g. special DB"""
    gi = get_galaxy_instance(inputstore)
    dsets = inputstore['datasets']
    for dset_name in filelist:
        print('Copy-importing {} to galaxy history '.format(dset_name))
        folder, fn = os.path.split(dsets[dset_name]['id'][0])
        tool_inputs = {'folder': folder, 'filename': fn,
                       'transfertype': 'copy', 'dtype':
                       dsets[dset_name]['id'][1]}
        dset = gi.tools.run_tool(inputstore['source_history'],
        'testtoolshed.g2.bx.psu.edu/repos/jorritb/lehtio_input_output/locallink/0.2',
                                 tool_inputs=tool_inputs)
        state = galaxy.wait_for_copyjob(dset, gi)
        if state == 'ok':
            print('File {} imported'.format(dsets[dset_name]['id'][0]))
            dsets[dset_name]['id'] = dset['outputs'][0]['id']
            dsets[dset_name]['src'] = 'hda'
        else:
            errormsg = ('Problem copying file '
                        '{}'.format(dsets[dset_name]['id'][0]))
            print(errormsg)
            self.retry(exc=errormsg)
    return inputstore
