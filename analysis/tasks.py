import os
import json
import shutil
import subprocess
from time import sleep
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task
from bioblend.galaxy import GalaxyInstance

from jobs.post import update_db
from kantele import settings
from analysis import qc


def get_galaxy_instance(inputstore):
    return GalaxyInstance(inputstore['galaxy_url'], inputstore['apikey'])


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
    state = wait_for_copyjob(dset, gi)
    if state == 'ok':
        print('File {} imported'.format(rawfile))
        sourceinfo['galaxy_id'] = dset['outputs'][0]['id']
        return run
    else:
        errormsg = 'Problem copying file {}'.format(rawfile)
        print(errormsg)
        self.retry(exc=errormsg)


@shared_task(queue=settings.QUEUE_GALAXY_WORKFLOW, bind=True)
def run_search_wf(self, run, wf_id):
    print('Workflow start task: Preparing inputs for workflow '
          'module {}'.format(wf_id))
    gi = get_galaxy_instance(run)
    if run['datasets']['spectra']['id'] is None:
        run = collect_spectra(run, gi)
    try:
        run['history'] = gi.histories.create_history(
            name=run['galaxyname'])['id']
    except:
        self.retry(countdown=60)
    mod_inputs = get_input_map_from_json(run['wf'], run['datasets'])
    print('Invoking workflow {} with id {}'.format(run['wf']['name'], wf_id))
    try:
        gi.workflows.invoke_workflow(wf_id, inputs=mod_inputs,
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
        run = get_datasets_to_download(run, outpath_full, gi)
        run = wait_for_completion(run, gi)
    except Exception as e:
        print('Problem downloading datasets, retrying in 60s. '
              'Problem message:', e)
        self.retry(countdown=60, exc=e)
    for dset in run['output_dsets'].values():
        if dset['download_url'][:4] != 'http':
            dset['download_url'] = '{}{}'.format(run['galaxy_url'],
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
        state = wait_for_copyjob(dset, gi)
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

def wait_for_copyjob(dset, gi):
    state = dset['jobs'][0]['state']
    while state in ['new', 'queued', 'running']:
        sleep(3)
        state = gi.jobs.show_job(dset['jobs'][0]['id'])['state']
    return state


def collect_spectra(inputstore, gi):
    print('Putting files from source histories {} in collection in search '
          'history {}'.format(inputstore['source_history'],
                              inputstore['history']))
    name_id_hdas = []
    for mzml in inputstore['raw']:
        name_id_hdas.append((mzml['filename'], mzml['galaxy_id']))
    if 'sort_specfiles' in inputstore['params']:
        name_id_hdas = sorted(name_id_hdas, key=lambda x: x[0])
    coll_spec = {
        'name': 'spectra', 'collection_type': 'list',
        'element_identifiers': [{'name': name, 'id': g_id, 'src': 'hda'}
                                for name, g_id in name_id_hdas]}
    collection = gi.histories.create_dataset_collection(inputstore['history'],
                                                        coll_spec)
    inputstore['datasets']['spectra'] = {'src': 'hdca', 'id': collection['id'],
                                         'history': inputstore['history']}
    return inputstore


def get_datasets_to_download(run, outpath_full, gi):
    print('Collecting datasets to download')
    download_dsets = {}
    for step in run['wf']['steps'].values():
        if 'post_job_actions' not in step:
            continue
        pj = step['post_job_actions']
        for pjk in pj:
            if pjk[:19] == 'RenameDatasetAction':
                nn = pj[pjk]['action_arguments']['newname']
                if nn[:4] == 'out:':
                    outname = nn[5:].replace(' ', '_')
                    download_dsets[nn] = {
                        'download_state': False, 'download_id': False,
                        'id': None, 'src': 'hda',
                        'download_dest': os.path.join(outpath_full, outname)}
    run['output_dsets'] = download_dsets
    print('Defined datasets from workflow: {}'.format(download_dsets.keys()))
    update_inputstore_from_history(gi, run['output_dsets'],
                                   run['output_dsets'].keys(), run['history'],
                                   'download')
    print('Found datasets to download, {}'.format(download_dsets))
    return run


def get_workflow_inputs_json(wfjson):
    """From workflow JSON returns (name, uuid) of the input steps"""
    for step in wfjson['steps'].values():
        if (step['tool_id'] is None and step['name'] in
                ['Input dataset', 'Input dataset collection']):
            yield(step['label'], step['uuid'])


def update_inputstore_from_history(gi, datasets, dsetnames, history_id,
                                   modname):
    print('Getting history contents')
    while not check_inputs_ready(datasets, dsetnames, modname):
        his_contents = gi.histories.show_history(history_id, contents=True,
                                                 deleted=False)
        # FIXME reverse contents so we start with newest dsets?
        for index, dset in enumerate(his_contents):
            if not dset_usable(dset):
                continue
            name = dset['name']
            if name in dsetnames and datasets[name]['id'] is None:
                print('found dset {}'.format(name))
                datasets[name]['history'] = history_id
                if datasets[name]['src'] == 'hdca':
                    datasets[name]['id'] = get_collection_id_in_his(
                        his_contents, name, dset['id'], gi, index)
                elif datasets[name]['src'] == 'hda':
                    datasets[name]['id'] = dset['id']
        sleep(10)


def dset_usable(dset):
    state_ok = True
    if 'state' in dset and dset['state'] == 'error':
        state_ok = False
    if dset['deleted'] or not state_ok:
        return False
    else:
        return True


def get_collection_id_in_his(his_contents, dset_name, named_dset_id, gi,
                             his_index=False, direction=False):
    """Search through history contents (passed) to find a collection that
    contains the named_dset_id. When passing direction=-1, the history will
    be searched backwards. Handy when having tools that do discover_dataset
    and populate a collection after creating it."""
    print('Trying to find collection ID belonging to dataset {}'
          'and ID {}'.format(dset_name, named_dset_id))
    if his_index:
        search_start = his_index
        direction = 1
    elif direction == -1:
        search_start = -1
    for dset in his_contents[search_start::direction]:
        if dset['type'] == 'collection':
            dcol = gi.histories.show_dataset_collection(dset['history_id'],
                                                        dset['id'])
            if named_dset_id in [x['object']['id'] for x in dcol['elements']]:
                print('Correct, using {} id {}'.format(dset['name'],
                                                       dset['id']))
                return dset['id']
    print('No matching collection in history (yet)')
    return None


def check_inputs_ready(datasets, inputnames, modname):
    print('Checking inputs {} for module {}'.format(inputnames, modname))
    ready, missing = True, []
    for name in inputnames:
        if datasets[name]['id'] is None:
            missing.append(name)
            ready = False
    if not ready:
        print('Missing inputs for module {}: '
              '{}'.format(modname, ', '.join(missing)))
    else:
        print('All inputs found for module {}'.format(modname))
    return ready


def get_input_map_from_json(module, inputstore):
    inputmap = {}
    for label, uuid in get_workflow_inputs_json(module):
        inputmap[uuid] = {
            'id': inputstore[label]['id'],
            'src': inputstore[label]['src'],
        }
    return inputmap


def wait_for_completion(inputstore, gi):
    """Waits for all output data to be finished before continuing with
    download steps"""
    print('Wait for completion of datasets to download')
    workflow_ok = True
    while workflow_ok and False in [x['download_id'] for x in
                                    inputstore['output_dsets'].values()]:
        print('Datasets not ready yet, checking')
        workflow_ok = check_outputs_workflow_ok(gi, inputstore)
        sleep(60)
    if workflow_ok:
        print('Datasets ready for downloading in history '
              '{}'.format(inputstore['history']))
        return inputstore
    else:
        raise RuntimeError('Output datasets are in error or deleted state!')
