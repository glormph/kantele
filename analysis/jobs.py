from datetime import datetime
import json
import re
import os

from django.utils import timezone

from kantele import settings
from analysis import tasks, models
from rawstatus import models as rm
from rawstatus import tasks as filetasks
from datasets import models as dsmodels
from datasets.jobs import get_or_create_mzmlentry
from jobs.jobs import DatasetJob, MultiDatasetJob, SingleFileJob, BaseJob

# TODO
# rerun qc data and displaying qcdata for a given qc file, how? 

class RefineMzmls(DatasetJob):
    refname = 'refine_mzmls'
    task = tasks.refine_mzmls

    def process(self, **kwargs):
        """Return all a dset mzMLs but not those that have a refined mzML associated, to not do extra work."""
        analysis = models.Analysis.objects.get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.get(pk=kwargs['wfv_id'])
        dbfn = models.LibraryFile.objects.get(pk=kwargs['dbfn_id']).sfile
        stagefiles = {'--tdb': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
        all_sfiles = self.getfiles_query(**kwargs).filter(checked=True, deleted=False, purged=False, mzmlfile__isnull=False)
        existing_refined = all_sfiles.filter(mzmlfile__refined=True)
        mzmlfiles = all_sfiles.exclude(rawfile__storedfile__in=existing_refined).select_related('mzmlfile__pwiz')
        anashare = rm.ServerShare.objects.get(name=settings.ANALYSISSHARENAME).id
        mzmls = []
        for x in mzmlfiles:
            ref_sf = get_or_create_mzmlentry(x, x.mzmlfile.pwiz, refined=True, servershare_id=anashare)
            mzmls.append((x.servershare.name, x.path, x.filename, ref_sf.id, anashare))
        allinstr = [x['rawfile__producer__name'] for x in mzmlfiles.distinct('rawfile__producer').values('rawfile__producer__name')] 
        if len(allinstr) > 1:
            raise RuntimeError('Trying to run a refiner job on dataset containing more than one instrument is not possible')
        params = ['--instrument']
        params.append('velos' if 'elos' in allinstr else 'qe')
        if kwargs['qtype'] != 'labelfree':
            params.extend(['--isobaric', kwargs['qtype']])
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': analysis.name,
               'outdir': analysis.user.username,
               }
        self.run_tasks.append(((run, params, mzmls, stagefiles), {}))
        # TODO replace this for general logging anyway, not necessary to keep queueing in analysis log
        analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
        analysis.save()


class RunLabelCheckNF(MultiDatasetJob):
    refname = 'run_nf_lc_workflow'
    task = tasks.run_nextflow_workflow

    def process(self, **kwargs):
        analysis = models.Analysis.objects.select_related('user',
                'nextflowsearch__workflow__shortname').get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
            pk=kwargs['wfv_id'])
        stagefiles = {}
        for flag, sf_id in kwargs['inputs']['singlefiles'].items():
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
            stagefiles[flag] = (sf.servershare.name, sf.path, sf.filename)
        sfiles = self.getfiles_query(**kwargs).filter(mzmlfile__refined=False).values(
                'servershare__name', 'path', 'filename',
                'rawfile__datasetrawfile__quantfilechannelsample__channel__channel__name',
                'rawfile__datasetrawfile__quantfilechannelsample__projsample__sample'
                )
        mzmls = [(x['servershare__name'], x['path'], x['filename'],
            x['rawfile__datasetrawfile__quantfilechannelsample__channel__channel__name'],
            x['rawfile__datasetrawfile__quantfilechannelsample__projsample__sample']) for x in sfiles]
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': analysis.name,
               'outdir': analysis.user.username,
               'nfrundirname': 'small' if analysis.nextflowsearch.workflow.shortname.name != '6FT' else 'larger'
               }
        profiles = ['standard', 'docker', 'lehtio']
        kwargs['inputs']['params'].extend(['--name', 'RUNNAME__PLACEHOLDER'])
        self.run_tasks.append(((run, kwargs['inputs']['params'], mzmls, stagefiles, ','.join(profiles)), {}))
        analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
        analysis.save()


class RunLongitudinalQCWorkflow(SingleFileJob):
    refname = 'run_longit_qc_workflow'
    task = tasks.run_nextflow_longitude_qc

    def process(self, **kwargs):
        """Assumes one file, one analysis"""
        analysis = models.Analysis.objects.get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.get(pk=kwargs['wfv_id'])
        dbfn = models.LibraryFile.objects.get(pk=kwargs['dbfn_id']).sfile
        # FIXME temp conditional code until all QC runs through msconvert
        if nfwf.id > 14:
            mzml = rm.StoredFile.objects.select_related('rawfile__producer', 'filetype').get(pk=kwargs['sf_id'])
        else:
            mzml = rm.StoredFile.objects.select_related('rawfile__producer', 'filetype').get(rawfile__storedfile__id=kwargs['sf_id'], mzmlfile__isnull=False)
        wf = models.Workflow.objects.filter(shortname__name='QC').last()
        # FIXME hardcoded mods location
        params = kwargs.get('params', [])
        params.extend(['--mods', 'data/labelfreemods.txt', '--instrument'])
        params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
        stagefiles = {'--mzml': (mzml.servershare.name, mzml.path, mzml.filename),
                    # FIXME temp keep both --mzml and --raw, until no longer using old QC
        	      '--raw': (mzml.servershare.name, mzml.path, mzml.filename),
                      '--db': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'rf_id': mzml.rawfile_id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': 'longqc',
               'outdir': 'internal_results',
               'filename': mzml.filename,
               'instrument': mzml.rawfile.producer.name,
               }
        create_nf_search_entries(analysis, wf.id, nfwf.id, self.job_id)
        self.run_tasks.append(((run, params, stagefiles), {}))
        analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
        analysis.save()


def create_nf_search_entries(analysis, wf_id, nfv_id, job_id):
    try:
        nfs = models.NextflowSearch.objects.get(analysis=analysis)
    except models.NextflowSearch.DoesNotExist:
        nfs = models.NextflowSearch(nfworkflow_id=nfv_id, job_id=job_id,
                                    workflow_id=wf_id, analysis=analysis)
        nfs.save()


class RunNextflowWorkflow(BaseJob):
    refname = 'run_nf_search_workflow'
    task = tasks.run_nextflow_workflow

    """
    inputs is {'params': ['--isobaric', 'tmt10plex'],
               'singlefiles': {'--tdb': tdb_sf_id, ... },}
    or shoudl inputs be DB things fields flag,sf_id (how for mzmls though?)
{'params': ['--isobaric', 'tmt10plex', '--instrument', 'qe', '--nfcore', '--hirief', 'SAMPLETABLE', "126::set1::treat1::treat::::127::set1::treat2::treat..."
], 'mzml': ('--mzmls', '{sdir}/*.mzML'), 'singlefiles': {'--tdb': 42659, '--dbsnp': 42665, '--genome': 42666, '--snpfa': 42662, '--cosmic': 42663, '--ddb': 42664, '--blastdb': 42661, '--knownproteins': 42408, '--gtf': 42658, '--mods': 42667}}
    """

    def getfiles_query(self, **kwargs):
        return rm.StoredFile.objects.filter(pk__in=kwargs['fractions'].keys())

    def process(self, **kwargs):
        analysis = models.Analysis.objects.select_related('user', 'nextflowsearch__workflow__shortname').get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
            pk=kwargs['wfv_id'])
        stagefiles = {}
        for flag, sf_id in kwargs['inputs']['singlefiles'].items():
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
            stagefiles[flag] = (sf.servershare.name, sf.path, sf.filename)
        mzmls = [(x.servershare.name, x.path, x.filename, kwargs['setnames'][str(x.id)],
                  kwargs['platenames'][str(x.rawfile.datasetrawfile.dataset_id)], kwargs['fractions'].get(str(x.id), False)) for x in
                 self.getfiles_query(**kwargs)]
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': analysis.name,
               'outdir': analysis.user.username,
               'nfrundirname': 'small' if analysis.nextflowsearch.workflow.shortname.name != '6FT' else 'larger'
               }
        profiles = ['standard']
        if '--nfcore' in kwargs['inputs']['params']:
            kwargs['inputs']['params'] = [x for x in kwargs['inputs']['params'] if x != '--nfcore']
            profiles.extend(['docker', 'lehtio'])
            kwargs['inputs']['params'].extend(['--name', 'RUNNAME__PLACEHOLDER'])
        else:
            kwargs['inputs']['params'].extend(['--searchname', 'RUNNAME__PLACEHOLDER'])
        if 'sampletable' in kwargs['inputs']:
            kwargs['inputs']['params'].extend(['SAMPLETABLE', kwargs['inputs']['sampletable']])
        self.run_tasks.append(((run, kwargs['inputs']['params'], mzmls, stagefiles, ','.join(profiles)), {}))
        # TODO remove this logging
        analysis.log = json.dumps(['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))])
        analysis.save()


class PurgeAnalysis(BaseJob):
    refname = 'purge_analysis'
    task = filetasks.delete_file
    """Queues tasks for deleting files from analysis from disk, then queues 
    job for directory removal"""

    def getfiles_query(self, **kwargs):
        return rm.StoredFile.objects.filter(analysisresultfile__analysis__id=kwargs['analysis_id'])

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs):
            fullpath = os.path.join(fn.path, fn.filename)
            print('Purging {} from analysis {}'.format(fullpath, kwargs['analysis_id']))
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}))
