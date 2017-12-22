import os
import json
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
    qcparams = json.loads(analysis.params.paramjson)
    run = galaxy.initialize_run(analysis, [mzml])
    run['params']['instrument'] = ('velos' if 'elos' in
                                   mzml.rawfile.producer.name else 'qe')
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
    # FIXME this WF has spectra in collectio and not? check and correct it.
    runchain = [tasks.tasks.runtime_and_upload(wf_json, run),
                tasks.store_summary.s(run),
                tasks.stage_infile.s(0),
                tasks.import_staged_file.s(0),
                tasks.run_search_wf.s(),
                tasks.download_results.s(qc=True),
                tasks.longitudinal_qc.s(),
                tasks.cleanup.s()]
    lastnode = chain(*runchain).delay()
    save_task_chain(lastnode, job_id)


