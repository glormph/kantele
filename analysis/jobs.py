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
# run should check if already ran with same commit/analysis

class RefineMzmls(DatasetJob):
    refname = 'refine_mzmls'
    task = tasks.refine_mzmls

    def process(self, **kwargs):
        """Return all a dset mzMLs but not those that have a refined mzML associated, to not do extra work."""
        analysis = models.Analysis.objects.get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.get(pk=kwargs['wfv_id'])
        dbfn = models.LibraryFile.objects.get(pk=kwargs['dbfn_id']).sfile
        stagefiles = {'--tdb': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
        all_sfiles = self.getfiles_query(**kwargs)
        existing_refined = all_sfiles.filter(filetype_id=settings.REFINEDMZML_SFGROUP_ID, checked=True)
        mzmlfiles = all_sfiles.filter(filetype_id=settings.MZML_SFGROUP_ID).exclude(rawfile__storedfile__in=existing_refined)
        analysisshare = rm.ServerShare.objects.get(name=settings.ANALYSISSHARENAME).id
        mzmls = [(x.servershare.name, x.path, x.filename, 
                  get_or_create_mzmlentry(x, settings.REFINEDMZML_SFGROUP_ID, analysisshare).id, analysisshare)
                 for x in mzmlfiles]
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
    refname = 'run_labelcheck_nf'
    task = tasks.run_nextflow_workflow

    def process(self, **kwargs):
        analysis = models.Analysis.objects.select_related('user', 'nextflowsearch__workflow__shortname').get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
            pk=kwargs['wfv_id'])
        stagefiles = {}
        for flag, sf_id in kwargs['inputs']['singlefiles'].items():
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
            stagefiles[flag] = (sf.servershare.name, sf.path, sf.filename)
        all_sfiles = self.getfiles_query(**kwargs)
        sfiles = all_sfiles.select_related('rawfile__datasetrawfile__quantsamplefile__projsample').filter(filetype_id=settings.MZML_SFGROUP_ID)
        dsrfs = {sf.id: sf.rawfile.datasetrawfile.quantsamplefile for sf in sfiles}
        samples = {sfid: dsrf.projsample.sample for sfid, dsrf in dsrfs.items()}
        psf_to_sfile = {dsrf.projsample_id: sfid for sfid, dsrf in dsrfs.items()}
        channels = {psf_to_sfile[qcs.projsample_id]: qcs.channel.channel.name for qcs in dsmodels.QuantChannelSample.objects.filter(dataset_id__in=kwargs['dset_ids']).select_related('channel__channel')}
        mzmls = [(x.servershare.name, x.path, x.filename, channels[x.id], samples[x.id]) 
                for x in sfiles]
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
        mzml = self.getfiles_pre_query(**kwargs). select_related('rawfile__producer',
                'filetype').get(filetype__filetype='mzml')
        wf = models.Workflow.objects.filter(shortname__name='QC').last()
        # FIXME hardcoded mods location
        params = ['--mods', 'data/labelfreemods.txt', '--instrument']
        params.append('velos' if 'elos' in mzml.rawfile.producer.name else 'qe')
        stagefiles = {'--mzml': (mzml.servershare.name, mzml.path, mzml.filename),
                      '--db': (dbfn.servershare.name, dbfn.path, dbfn.filename)}
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'rf_id': mzml.rawfile_id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': 'longqc',
               'outdir': 'internal_results',
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


class RunNextflowWorkflow(MultiDatasetJob):
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
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=kwargs['sf_id'])
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
