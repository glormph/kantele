from datetime import datetime
import json

from kantele import settings
from analysis import tasks, models
from rawstatus import models as filemodels
from jobs.models import Task

# FIXMEs
# DONE? search must wait for convert, why does it not?
# DONE? store qc data does not finish tasks
# rerun qc data and displaying qcdata for a given qc file, how? 
# run should check if already ran with same commit/analysis

def auto_run_qc_workflow(job_id, dset_id, sf_id, analysis_id):
    """Assumes one file, one analysis"""
    analysis = models.Analysis.objects.get(pk=analysis_id)
    nfwf = models.NextflowWorkflow.objects.get(pk=settings.LONGQC_NXF_WF_ID)
    dbfn = models.LibraryFile.objects.get(pk=settings.LONGQC_FADB_ID)
    rawfn = filemodels.RawFile.objects.get(storedfile__id=sf_id)
    mzml = filemodels.StoredFile.objects.filter(
        rawfile_id=rawfn.id, filetype='mzml').select_related(
        'rawfile__producer', 'servershare').get()
    params = ['--mzml', mzml.filename, '--db', dbfn.sfile.filename, '--mods',
              'data/labelfreemods.txt', '--instrument']
    params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'rf_id': rawfn.id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           }
    create_nf_search_entries(analysis, nfwf, params, [mzml], [dbfn.sfile])
    stagefiles = {mzml.filename: (mzml.servershare.name, mzml.path),
                  dbfn.sfile.filename: (dbfn.sfile.servershare.name,
                                        dbfn.sfile.path)}
    res = tasks.run_nextflow_longitude_qc.delay(run, params, stagefiles)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')


def create_nf_search_entries(analysis, nfwf, params, mzmls, dbs):
    try:
        models.NextflowSearch.objects.get(analysis=analysis)
    except models.NextflowSearch.DoesNotExist:
        models.NextflowSearch.objects.create(
            nfworkflow=nfwf, params=json.dumps(params), analysis=analysis)
    for searchfile in mzmls + dbs:
        try:
            models.SearchFile.objects.get(analysis=analysis, sfile=searchfile)
        except models.SearchFile.DoesNotExist:
            models.SearchFile.objects.create(analysis=analysis,
                                             sfile=searchfile)
