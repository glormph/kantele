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
           'repo': 'https://github.com/lehtiolab/galaxy-workflows',
           }
    create_nf_search_entries(analysis, nfwf, params, [mzml], [dbfn])
    stagefiles = get_stagefiles([mzml, dbfn])
    res = tasks.run_nextflow_longitude_qc.delay(run, params, stagefiles)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')


def get_nonstage_file_params(lib_ids, sfile_ids=False):
    libfiles = {x.id: x for x in models.LibraryFile.objects.filter(
        pk__in=lib_ids.values()).select_related('sfile')}
    nonstagefiles = {x.sfile.filename: (x.sfile.servershare.name, x.sfile.path) 
        for x in libfiles.values()}
    params = []
    for pname, pid in lib_ids.items():
        params.extend(['--{}'.format(pname), libfiles[pid].sfile.filename])
    if sfile_ids:
        nonlibfiles = {x.id: x for x in filemodels.StoredFile.objects.filter(
            pk__in=sfile_ids.values())
        nonstagefiles.update({x.filename: (x.servershare.name, x.path) 
                              for x in nonlibfiles.values()}
        for pname, pid in sfile_ids.items():
            params.extend(['--{}'.format(pname), nonlibfiles[pid].filename])
    return nonstagefiles, params

        
def get_stagefiles(sfiles):
    return {x.filename: (x.servershare.name, x.path) for x in sfiles}


def run_ipaw(job_id, dset_id, sf_ids, analysis_id, wf_id, tdb_id, ddb_id,
             known_id, blast_id, gtf_id, snp_id, dbsnp_id, cosmic_id,genome_id):
    """iPAW currently one dataset at a time
    2do: create lib datasets, make this code correct
    """
    analysis = models.Analysis.objects.get(pk=analysis_id)
    nfwf = models.NextflowWorkflow.objects.get(pk=wf_id)
    tdbfn = models.LibraryFile.objects.get(pk=tdb_id).sfile
    ddbfn = models.LibraryFile.objects.get(pk=ddb_id).sfile
    modfn = models.LibraryFile.objects.get(pk=mod_id).sfile
    nonstage, params = get_nonstage_file_params(
        {'knownproteins': known_id, 'blastdb': blast_id, 
         'gtf': gtf_id, 'snpfa': snp_id, 'dbsnp': dbsnp_id, 
         'cosmic': cosmic_id, 'genome': genome_id})
    params.extend(['--tdb', tdbfn.filename, '--ddb', ddbfn.filename,
                   '--mods', modfn.filename, '--instrument'])
    mzmls = filemodels.StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset__id=dset_id, filetype='mzml').select_related(
            'rawfile__producer', 'servershare')
    instruments = [x.rawfile.producer.name for x in mzmls]
    if any(['elos' in x for x in instruments]) and len(instruments) > 1:
        raise RuntimeError('Mixed of Velos and other instruments is '
                           'not possible to search currently. '
                           'Instruments: {}'.format(instruments))
    params.append('velos' if 'elos' in instruments[0] else 'qe')
    if bam_ids:
        pass  # TODO add bams
    get_stagefiles(mzmls + [tdbfn, ddbfn, modfn])
    run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
           'analysis_id': analysis.id,
           'wf_commit': nfwf.commit,
           'nxf_wf_fn': nfwf.filename,
           'repo': 'https://github.com/lehtiolab/proteogenomics-analysis-workflow',
           }
    create_nf_search_entries(analysis, nfwf, params, [mzml], [dbfn.sfile])
    res = tasks.run_nextflow_ipaw.delay(run, params, stagefiles, nonstagefiles)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')
    

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
