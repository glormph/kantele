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



def auto_run_qc_workflow(job_id, sf_id, analysis_id, wf_id, dbfn_id):
    """Assumes one file, one analysis"""
    analysis = models.Analysis.objects.get(pk=analysis_id)
    nfwf = models.NextflowWorkflow.objects.get(pk=wf_id)
    dbfn = models.LibraryFile.objects.get(pk=dbfn_id).sfile
    mzml = filemodels.StoredFile.objects.select_related(
        'rawfile__producer', 'servershare').get(rawfile__storedfile__id=sf_id,
                                                filetype='mzml')
    params = ['--mzml', mzml.filename, '--db', dbfn.filename, '--mods',
              'data/labelfreemods.txt', '--instrument']
    params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'rf_id': mzml.rawfile_id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           }
    create_nf_search_entries(analysis, nfwf, params, [mzml], [dbfn])
    stagefiles = get_stagefiles([mzml, dbfn])
    res = tasks.run_nextflow_longitude_qc.delay(run, params, stagefiles)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')



        
def get_stagefiles(sfiles):
    return {x.filename: (x.servershare.name, x.path) for x in sfiles}


def create_nf_search_entries(analysis, nfwf, params, mzmls, dbs):
    try:
        nfs = models.NextflowSearch.objects.get(analysis=analysis)
    except models.NextflowSearch.DoesNotExist:
        nfs = models.NextflowSearch(nfworkflow=nfwf, params=json.dumps(params),
                                    analysis=analysis)
        nfs.save()
    for searchfile in mzmls + dbs:
        try:
            models.SearchFile.objects.get(search=nfs, sfile=searchfile)
        except models.SearchFile.DoesNotExist:
            models.SearchFile.objects.create(search=nfs, sfile=searchfile)
