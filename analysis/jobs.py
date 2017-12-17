import os
import json
from datetime import datetime

from celery import chain

from analysis import galaxy, tasks


def run_qc_workflow(gi, analysis, mzmlfiles, qcparams):
    # This should probably be a job
    # Have separate beat job for checking DBs with galaxy
    run = galaxy.initialize_run(analysis)
    instrumenttypes = set(['velos' if 'elos' in smz.mzml.rawfile.producer.name
                           else 'qe' for smz in mzmlfiles])
    if len(instrumenttypes) > 1:
        raise RuntimeError('Only one instrument type allowed per search '
                           'at the moment')
    run['params']['instrument'] = instrumenttypes.pop()
    run['datasets']['target db'] = {'galaxy_name': qcparams.targetdb.name,
                                    'id': qcparams.targetdb.galaxy_id,
                                    'src': 'ld'}
    run['datasets']['decoy db'] = {'galaxy_name': qcparams.targetdb.name,
                                   'id': qcparams.targetdb.galaxy_id,
                                   'src': 'ld'}
    run['params']['MS-GF+'] = galaxy.get_msgf_inputs(run['params'])
    timestamp = datetime.strftime(analysis.date, '%Y%m%d_%H.%M')
    run['galaxyname'] = '{}_{}'.format(analysis.name, timestamp)
    run['outdir'] = os.path.join('qc_results',
                                 '{}_{}'.format(analysis.name, timestamp))
    wf_json = json.loads(analysis.search.workflow.wfjson)
    wf_json['name'] = '{}_{}'.format(analysis.name, timestamp)
    run['wf'], galaxy_upload_wfid = galaxy.runtime_and_upload(wf_json, run, gi)
    runchain = [tasks.store_summary.s(run),
                tasks.stage_infile.s(0),
                tasks.import_staged_file.s(0),
                tasks.run_search_wf.s(galaxy_upload_wfid),
                tasks.download_results.s(qc=True),
                tasks.longitudinal_qc.s(),
                tasks.cleanup.s()]
    chain(*runchain).delay()
    runchain. qc
