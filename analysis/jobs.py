import os
import json
from datetime import datetime

from celery import chain

from jobs.post import save_task_chain
from analysis import galaxy, tasks, models


def run_qc_workflow(job_id, analysis_id, mzmlfiles_id, qcparams_id):
    # Have separate beat job for checking DBs with galaxy
    analysis = models.Analysis.objects.select_related(
        'search__workflow', 'account').get(pk=analysis_id)
    mzmlfiles = models.SearchMzmlFiles.objects.select_related(
        'mzml__rawfile__producer').filter(analysis_id=analysis_id)
    qcparams = json.loads(QCParams.objects.get(pk=qcparams_id).paramjson)
    run = galaxy.initialize_run(analysis)
    instrumenttypes = set(['velos' if 'elos' in smz.mzml.rawfile.producer.name
                           else 'qe' for smz in mzmlfiles])
    if len(instrumenttypes) > 1:
        raise RuntimeError('Only one instrument type allowed per search '
                           'at the moment')
    run['params']['instrument'] = instrumenttypes.pop()
    targetdb = models.GalaxyLibDataset.objects.get(pk=qcparams['target db'])
    decoydb = models.GalaxyLibDataset.objects.get(pk=qcparams['decoy db'])
    run['datasets']['target db'] = {'galaxy_name': targetdb.name,
                                    'id': targetdb.galaxy_id, 'src': 'ld'}
    run['datasets']['decoy db'] = {'galaxy_name': decoydb.name,
                                   'id': decoydb.galaxy_id, 'src': 'ld'}
    run['params']['MS-GF+'] = galaxy.get_msgf_inputs(run['params'])
    timestamp = datetime.strftime(analysis.date, '%Y%m%d_%H.%M')
    run['galaxyname'] = '{}_{}'.format(analysis.name, timestamp)
    run['outdir'] = os.path.join('qc_results',
                                 '{}_{}'.format(analysis.name, timestamp))
    wf_json = json.loads(analysis.search.workflow.wfjson)
    wf_json['name'] = '{}_{}'.format(analysis.name, timestamp)
    runchain = [tasks.runtime_and_upload(wf_json, run),
                tasks.store_summary.s(run),
                tasks.stage_infile.s(0),
                tasks.import_staged_file.s(0),
                tasks.run_search_wf.s(galaxy_upload_wfid),
                tasks.download_results.s(qc=True),
                tasks.longitudinal_qc.s(),
                tasks.cleanup.s()]
    lastnode = chain(*runchain).delay()
    save_task_chain(lastnode, job_id)


