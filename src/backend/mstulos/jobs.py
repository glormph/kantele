import re
import os
from uuid import uuid4

from jobs.jobs import BaseJob
from mstulos import models as m
from mstulos import tasks as mt

from analysis import models as am


class ProcessAnalysis(BaseJob): 
    refname = 'process_p_search_results'
    task = mt.summarize_result_peptable

    # version 1, 2021 msstitch sqlite
    """
    kwargs = {
    'analysis_id': 1,
    '': ,
    """
    # FIXME: need mods defined as unimod when analysing
    # ideally we have a unimod lookup in Kantele, can download from there
    # FIXME this is not atomic view, if crash -> DB entries!
    # maybe instead of job, put some of this in view that created/saved analysis
   
    #getfiles_query()? needed
    def process(self, **kwargs):
        # First store the pre-result-things
        analysis = am.Analysis.objects.select_related('nextflowsearch__nfworkflow__wfoutput').get(
                pk=kwargs['analysis_id'])
        output = analysis.nextflowsearch.nfworkflow.wfoutput
       # new_exp = False
        try:
            expana = m.ExpAnalysis.objects.get(analysis=analysis)
        except m.ExpAnalysis.DoesNotExist:
       #     new_exp = True

            exp = m.Experiment.objects.create(name=analysis.name, token=str(uuid4()))
            expana = m.ExpAnalysis.objects.create(analysis=analysis, experiment=exp)
        if expana.experiment.upload_complete:
            return

        # TODO currently only recent and isobaric data, as  a start
        # figure out how we store one file/sample -> analysisfilesample
        # and labelfree fractions?  -> analysisdset probbaly
        if not hasattr(analysis, 'analysissampletable'):
            raise RuntimeError('Cannot process analysis without sampletable as conditions currently')
        # Delete all conditions before rerunning again, since it is not possible to only
        # get_or_create on name/exp, as there are duplicates in the DB e.g. multiple sets with
        # TMT channel 126
        m.Condition.objects.filter(experiment=expana.experiment).delete()
        samplesets = {}
        for ads in analysis.analysisdatasetsetname_set.all():
            c_setn = m.Condition.objects.create(name=ads.setname.setname,
                    cond_type=m.Condition.Condtype['SAMPLESET'], experiment=expana.experiment)
            sampleset = {'set_id': c_setn.pk, 'fractions': {}, 'files': {}}
            for dsf in ads.analysisdsinputfile_set.all():
                c_fn = m.Condition.objects.create(name=dsf.sfile.filename,
                        cond_type=m.Condition.Condtype['FILE'], experiment=expana.experiment)
                sampleset['files'][dsf.sfile.filename] = c_fn.pk
                if ads.regex != '':
                    frnum = re.match(ads.regex, dsf.sfile.filename).group(1)
                    c_fr = m.Condition.objects.create(name=frnum,
                            cond_type=m.Condition.Condtype['FRACTION'], experiment=expana.experiment)
                    #sampleset['fractions'][frnum] = c_fr.pk
                    c_fr.parent_conds.add(c_setn)
                    c_fn.parent_conds.add(c_fr)
                else:
                    c_fn.parent_conds.add(c_setn)
            samplesets[ads.setname.setname] = sampleset

        # Sample name and group name are repeated in sampletable so they use get_or_create
        # Can also do that because they cant be duplicate in experiment, like e.g.
        # fractions or channels over multiple sets
        # TODO exempt them from deletion above?
        samples = {'groups': {}, 'samples': {}, }
        for ch, setn, sample, sgroup in analysis.analysissampletable.samples:
            if sgroup != '':
                gss = f'{sgroup}_{sample}_{setn}___{ch}'
                c_group, _cr = m.Condition.objects.get_or_create(name=sgroup,
                        cond_type=m.Condition.Condtype['SAMPLEGROUP'], experiment=expana.experiment)
                samples['groups'][gss] = c_group.pk
            else:
                gss = f'{sample}_{setn}___{ch}'
            c_sample, _cr = m.Condition.objects.get_or_create(name=sample,
                    cond_type=m.Condition.Condtype['SAMPLE'], experiment=expana.experiment)
            samples['samples'][gss] = c_sample.pk
            c_ch = m.Condition.objects.create(name=ch, cond_type=m.Condition.Condtype['CHANNEL'],
                    experiment=expana.experiment)
            samples[gss] = c_ch.pk
            # Now add hierarchy:
            c_ch.parent_conds.add(samplesets[setn]['set_id'])
            c_ch.parent_conds.add(c_sample)
            # TODO how to treat non-grouped sample? currently this is X__POOL
            if sgroup != '':
                c_sample.parent_conds.add(c_group)

        # Output files headers according to their DB entry
        headers = {'pep': {'psmcount': output.psmcountfield, 'fdr': output.pepfdrfield,
            'peptide': output.peppeptide, 'isobaric': []},
            'psm': {'fdr': output.psmfdrfield, 'fn': output.psmfnfield, 'scan': output.scanfield,
                'setname': output.psmsetname, 'peptide': output.psmpeptide}}
        for plextype in analysis.datasetsearch_set.filter(
                dataset__quantdataset__quanttype__shortname__contains='plex').distinct(
                        'dataset__quantdataset__quanttype__shortname'):
            headers['pep']['isobaric'].append(plextype['dataset__quantdataset__quanttype__shortname'])
        pepfile = os.path.join(analysis.storage_dir, output.pepfile)
        b_ana_mgr = am.AnalysisBaseanalysis.objects.filter(analysis=analysis, rerun_from_psms=True)
        if b_ana_mgr.count():
            base_analysis = b_ana_mgr.get().base_analysis
            base_output = base_analysis.nextflowsearch.nfworkflow.wfoutput
            lookupfile = os.path.join(base_analysis.storage_dir, base_output.lookup)
            psmfile = os.path.join(base_analysis.storage_dir, base_output.psmfile)
        else:
            lookupfile = os.path.join(analysis.storage_dir, output.lookup)
            psmfile = os.path.join(analysis.storage_dir, output.psmfile)
        self.run_tasks.append(((token, pepfile, psmfile, lookupfile, headers, samplesets, samples), {}))
        print(self.run_tasks)
