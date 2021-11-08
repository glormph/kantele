from datetime import datetime
import re
import os
from uuid import uuid4

from django.utils import timezone
from django.db.models import Q

from kantele import settings
from analysis import tasks, models
from rawstatus import models as rm
from rawstatus import tasks as filetasks
from datasets import models as dsmodels
from datasets.jobs import get_or_create_mzmlentry
from jobs.jobs import DatasetJob, MultiDatasetJob, SingleFileJob, BaseJob

# TODO
# rerun qc data and displaying qcdata for a given qc file, how? 
def get_ana_fullname(analysis):
    return f'{analysis.nextflowsearch.workflow.shortname.name}_{analysis.name}'



class RefineMzmls(DatasetJob):
    refname = 'refine_mzmls'
    task = tasks.refine_mzmls
    revokable = True

    def process(self, **kwargs):
        """Return all a dset mzMLs but not those that have a refined mzML associated, to not do extra work."""
        analysis = models.Analysis.objects.get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.get(pk=kwargs['wfv_id'])
        dbfn = models.LibraryFile.objects.get(pk=kwargs['dbfn_id']).sfile
        stagefiles = {'--tdb': [(dbfn.servershare.name, dbfn.path, dbfn.filename)]}
        all_sfiles = self.getfiles_query(**kwargs).filter(checked=True, deleted=False, purged=False, mzmlfile__isnull=False)
        existing_refined = all_sfiles.filter(mzmlfile__refined=True)
        mzmlfiles = all_sfiles.exclude(rawfile__storedfile__in=existing_refined).select_related('mzmlfile__pwiz')
        anashare = rm.ServerShare.objects.get(name=settings.ANALYSISSHARENAME).id
        mzmls = []
        for x in mzmlfiles:
            ref_sf = get_or_create_mzmlentry(x, x.mzmlfile.pwiz, refined=True, servershare_id=anashare)
            mzmls.append({'servershare': x.servershare.name, 'path': x.path, 'fn': x.filename,
                'sfid': ref_sf.id})
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
        profiles = ['standard', 'docker']
        self.run_tasks.append(((run, params, mzmls, stagefiles, ','.join(profiles), nfwf.nfversion), {}))
        # TODO replace this for general logging anyway, not necessary to keep queueing in analysis log
        analysis.log = ['[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'))]
        analysis.save()


class RunLabelCheckNF(MultiDatasetJob):
    refname = 'run_nf_lc_workflow'
    task = tasks.run_nextflow_workflow
    revokable = True

    def process(self, **kwargs):
        analysis = models.Analysis.objects.select_related('user',
                'nextflowsearch__workflow__shortname').get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
            pk=kwargs['wfv_id'])
        stagefiles = {}
        for flag, sf_id in kwargs['inputs']['singlefiles'].items():
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
            stagefiles[flag] = [(sf.servershare.name, sf.path, sf.filename)]
        sfiles = self.getfiles_query(**kwargs).filter(mzmlfile__refined=False).values(
                'servershare__name', 'path', 'filename',
                'rawfile__datasetrawfile__quantfilechannelsample__channel__channel__name',
                'rawfile__datasetrawfile__quantfilechannelsample__projsample__sample'
                )
        mzmls = [{'servershare': x['servershare__name'], 'path': x['path'], 'fn': x['filename'],
            'setname': kwargs['setnames'][str(x.id)] if 'setnames' in kwargs else False,
            'channel': x['rawfile__datasetrawfile__quantfilechannelsample__channel__channel__name'],
            'sample': x['rawfile__datasetrawfile__quantfilechannelsample__projsample__sample']}
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
        self.run_tasks.append(((run, kwargs['inputs']['params'], mzmls, stagefiles, ','.join(profiles), nfwf.nfversion), {}))
        analysis.log.append('[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S')))
        analysis.save()


class RunLongitudinalQCWorkflow(SingleFileJob):
    refname = 'run_longit_qc_workflow'
    task = tasks.run_nextflow_longitude_qc

    def process(self, **kwargs):
        """Assumes one file, one analysis"""
        analysis = models.Analysis.objects.get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.get(pk=kwargs['wfv_id'])
        dbfn = models.LibraryFile.objects.get(pk=kwargs['dbfn_id']).sfile
        mzml = rm.StoredFile.objects.select_related('rawfile__producer', 'filetype').get(pk=kwargs['sf_id'])
        wf = models.Workflow.objects.filter(shortname__name='QC').last()
        # FIXME hardcoded mods location
        params = kwargs.get('params', [])
        params.extend(['--mods', 'data/labelfreemods.txt',
            '--instrument', mzml.rawfile.producer.msinstrument.instrumenttype.name])
        if mzml.rawfile.producer.msinstrument.instrumenttype.name == 'timstof':
            params.extend(['--prectol', '20ppm'])
        stagefiles = {'--raw': [(mzml.servershare.name, mzml.path, mzml.filename)],
                      '--db': [(dbfn.servershare.name, dbfn.path, dbfn.filename)]}
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
        models.NextflowSearch.objects.update_or_create(defaults={'nfworkflow_id': nfwf.id, 
            'job_id': self.job_id, 'workflow_id': wf.id, 'token': 'nf-{}'.format(uuid4)},
            analysis=analysis)
        self.run_tasks.append(((run, params, stagefiles, nfwf.nfversion), {}))
        analysis.log.append('[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S')))
        analysis.save()




def recurse_nrdsets_baseanalysis(aba):
    """Recursively get all old mzmls from what is possibly a chain of growing analyses,
    each e.g. adding a single set fresh of the MS"""
    try:
        # if this base ana has its base ana, run the recursive func
        older_aba = models.AnalysisBaseanalysis.objects.get(
                analysis=aba.base_analysis, is_complement=True)
    except models.AnalysisBaseanalysis.DoesNotExist:
        # youve found the last base ana, dont call deeper
        old_mzmls = {}
        old_dsets = {}
    else:
        # get older analysis' old mzmls
        old_mzmls, old_dsets = recurse_nrdsets_baseanalysis(older_aba)
    # First get stripnames of old ds
    strips = {}
    for oldads in aba.base_analysis.analysisdatasetsetname_set.select_related('dataset__prefractionationdataset__hiriefdataset'):
        hirief = oldads.dataset.prefractionationdataset.hiriefdataset.hirief
        strips[oldads.dataset_id] = '-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in str(hirief).split('-')])
    # Put old files fields into the run dict, group them by set so we dont get duplicates in case an analysis chain is:
    # 1. setA + setB
    # 2. setB rerun based on 1.
    # 3. setC addition based on 2
    # This would in 3. give us all oldmzmls from 1. and 2., so setB would be double
    single_ana_oldmzml = {}
    single_ana_oldds = {}
    for asf in models.AnalysisDSInputFile.objects.filter(
            analysis=aba.base_analysis).select_related(
                    'sfile__rawfile__producer', 'analysisdset__setname'):
        oldasf = {'fn': asf.sfile.filename,
                'instrument': asf.sfile.rawfile.producer.name,
                'setname': asf.analysisdset.setname.setname,
                'plate': strips[asf.analysisdset.dataset_id],
                'fraction': re.match(asf.analysisdset.regex, asf.sfile.filename).group(1),
                }
        try:
            single_ana_oldmzml[asf.analysisdset.setname.setname].append(oldasf)
            single_ana_oldds[asf.analysisdset.setname.setname].add(asf.analysisdset.dataset_id)
        except KeyError:
            single_ana_oldmzml[asf.analysisdset.setname.setname] = [oldasf]
            single_ana_oldds[asf.analysisdset.setname.setname] = {asf.analysisdset.dataset_id}
    old_mzmls.update(single_ana_oldmzml)
    old_dsets.update(single_ana_oldds)
    return old_mzmls, old_dsets


class RunNextflowWorkflow(BaseJob):
    refname = 'run_nf_search_workflow'
    task = tasks.run_nextflow_workflow
    revokable = True

    """
    inputs is {'params': ['--isobaric', 'tmt10plex'],
               'singlefiles': {'--tdb': tdb_sf_id, ... },}
    or shoudl inputs be DB things fields flag,sf_id (how for mzmls though?)
{'params': ['--isobaric', 'tmt10plex', '--instrument', 'qe', '--hirief', 'SAMPLETABLE', "126::set1::treat1::treat::::127::set1::treat2::treat..."
], 'mzml': ('--mzmls', '{sdir}/*.mzML'), 'singlefiles': {'--tdb': 42659, '--dbsnp': 42665, '--genome': 42666, '--snpfa': 42662, '--cosmic': 42663, '--ddb': 42664, '--blastdb': 42661, '--knownproteins': 42408, '--gtf': 42658, '--mods': 42667}}
    """

    def getfiles_query(self, **kwargs):
        return rm.StoredFile.objects.filter(pk__in=kwargs['fractions'].keys()).select_related(
                'servershare', 'rawfile__producer__msinstrument__instrumenttype',
                'rawfile__datasetrawfile__quantfilechannelsample__channel__channel',
                'rawfile__datasetrawfile__quantfilechannelsample__projsample',
                )

    def process(self, **kwargs):
        analysis = models.Analysis.objects.select_related('user', 'nextflowsearch__workflow__shortname').get(pk=kwargs['analysis_id'])
        nfwf = models.NextflowWfVersion.objects.select_related('nfworkflow').get(
            pk=kwargs['wfv_id'])
        stagefiles = {}
        for flag, sf_id in kwargs['inputs']['singlefiles'].items():
            sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
            stagefiles[flag] = [(sf.servershare.name, sf.path, sf.filename)]
        for flag, sf_ids in kwargs['inputs']['multifiles'].items():
            stagefiles[flag] = []
            for sf_id in sf_ids:
                sf = rm.StoredFile.objects.select_related('servershare').get(pk=sf_id)
                stagefiles[flag].append((sf.servershare.name, sf.path, sf.filename)) 
        # re-filter mzML files in case files are removed or added to dataset
        # between a stop/error and rerun of job
        job = analysis.nextflowsearch.job
        dss = analysis.datasetsearch_set.all()
        # First new files included:
        # NB including new files leads to problems with e.g. fraction regex
        # if they are somehow strange
        newfns = rm.StoredFile.objects.filter(mzmlfile__isnull=False,
            rawfile__datasetrawfile__dataset__datasetsearch__in=dss).exclude(
            pk__in=kwargs['fractions'].keys())
        if newfns.count():
            raise RuntimeError('Could not rerun job, there are files added to '
                'a dataset, please edit the analysis so it is still correct, '
                'save, and re-queue the job')

        # Now remove obsolete deleted files (e.g. corrupt, empty, etc)
        obsolete = self.getfiles_query(**kwargs).exclude(rawfile__datasetrawfile__dataset__datasetsearch__in=dss)
        analysis.analysisdsinputfile_set.filter(sfile__in=obsolete).delete()
        analysis.analysisfilesample_set.filter(sfile__in=obsolete).delete()
        rm.FileJob.objects.filter(job_id=job.pk, storedfile__in=obsolete).delete()
        for del_sf in obsolete:
            kwargs['setnames'].pop(str(del_sf.pk))
            kwargs['fractions'].pop(str(del_sf.pk))
        if obsolete:
            job.kwargs = kwargs
            job = job.save()

        # token is unique per job run:
        analysis.nextflowsearch.token = 'nf-{}'.format(uuid4())
        analysis.nextflowsearch.save()
        run = {'timestamp': datetime.strftime(analysis.date, '%Y%m%d_%H.%M'),
               'analysis_id': analysis.id,
               'token': analysis.nextflowsearch.token,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'name': get_ana_fullname(analysis),
               'outdir': analysis.user.username,
               'nfrundirname': 'small' if analysis.nextflowsearch.workflow.shortname.name != '6FT' else 'larger',
               'mzmls': [],
               'old_mzmls': False,
               }
        
        # Gather mzML input
        if kwargs['inputs']['components']['mzmldef']:
            mzmldef_fields = models.WFInputComponent.objects.get(name='mzmldef').value[kwargs['inputs']['components']['mzmldef']]
            mzmls = [{
                'servershare': x.servershare.name, 'path': x.path, 'fn': x.filename,
                'setname': kwargs['setnames'][str(x.id)] if 'setname' in mzmldef_fields else False,
                'plate': kwargs['platenames'].get(str(x.rawfile.datasetrawfile.dataset_id), False) 
                if 'plate' in mzmldef_fields else False,
                'channel': x.rawfile.datasetrawfile.quantfilechannelsample.channel.channel.name 
                if 'channel' in mzmldef_fields else False,
                'sample': x.rawfile.datasetrawfile.quantfilechannelsample.projsample.sample 
                if 'sample' in mzmldef_fields else False,
                'fraction': kwargs['fractions'].get(str(x.id), False) 
                if 'fractions' in kwargs else False,
                'instrument': x.rawfile.producer.msinstrument.instrumenttype.name 
                if 'instrument' in mzmldef_fields else False,
                } for x in self.getfiles_query(**kwargs)]
            mzmls = [{'mzmldef': '\t'.join([x[key] for key in mzmldef_fields if x[key]]), **{k: x[k] 
                for k in ['servershare', 'path', 'fn']}} for x in mzmls]

        # Add base analysis stuff if it is complement and fractionated (if not it has only been used
        # for fetching parameter values and can be ignored in the job)
        ana_baserec = models.AnalysisBaseanalysis.objects.select_related('base_analysis').filter(analysis_id=analysis.id)
        try:
            ana_baserec = ana_baserec.get(Q(is_complement=True) | Q(rerun_from_psms=True))
        except models.AnalysisBaseanalysis.DoesNotExist:
            # Run with normal mzmldef input
            run['mzmls'] = mzmls
        else:
            if hasattr(ana_baserec.base_analysis, 'analysismzmldef') and ana_baserec.base_analysis.analysismzmldef.mzmldef == 'fractionated':
                # rerun/complement runs with fractionated base analysis need --oldmzmldef parameter
                old_mzmls, old_dsets = recurse_nrdsets_baseanalysis(ana_baserec)
                oldmz_fields = models.WFInputComponent.objects.get(name='mzmldef').value['fractionated']
                run['old_mzmls'] = ['{}\t{}'.format(x['fn'], '\t'.join([x[key] for key in oldmz_fields]))
                        for setmzmls in old_mzmls.values() for x in setmzmls]
            if not ana_baserec.rerun_from_psms:
                # Only mzmldef input if not doing a rerun
                run['mzmls'] = mzmls

        profiles = ['standard', 'docker', 'lehtio']
        params = [str(x) for x in kwargs['inputs']['params']]
        # Runname defined when run executed (FIXME can be removed, no reason to not do that here)
        params.extend(['--name', 'RUNNAME__PLACEHOLDER'])
        if kwargs['inputs']['components']['sampletable']:
            params.extend(['SAMPLETABLE', kwargs['inputs']['components']['sampletable']])
        self.run_tasks.append(((run, params, stagefiles, ','.join(profiles), nfwf.nfversion), {}))
        analysis.log.append('[{}] Job queued'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S')))
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
