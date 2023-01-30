import re
import os
from uuid import uuid4

from django.db.models import Q

from jobs.jobs import BaseJob
from mstulos import models as m
from mstulos import tasks as mt
from analysis import models as am


# DDA pipeline 2.8 and up have OK format, before that: amount/count
# before 2.6 there is X__POOL
# before 2.3 # PSMs is not correct (identical)

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
        try:
            exp = m.Experiment.objects.get(analysis=analysis)
        except m.Experiment.DoesNotExist:
            exp = m.Experiment.objects.create(analysis=analysis, token=str(uuid4()))
        if exp.upload_complete:
            return

        # TODO currently only recent and isobaric data, as  a start
        # figure out how we store one file/sample -> analysisfilesample
        # and labelfree fractions?  -> analysisdset probbaly
        if not hasattr(analysis, 'analysissampletable'):
            raise RuntimeError('Cannot process analysis without sampletable as conditions currently')
        # Delete all conditions before rerunning again, since it is not possible to only
        # get_or_create on name/exp, as there are duplicates in the DB e.g. multiple sets with
        # TMT channel 126
        m.Condition.objects.filter(experiment=exp).delete()
        samplesets = {}
        # FIXME non-set searches (have analysisdsinputfile), also non-sampletable (same?)
        organisms = set()
        for ads in analysis.analysisdatasetsetname_set.all():
            c_setn = m.Condition.objects.create(name=ads.setname.setname,
                    cond_type=m.Condition.Condtype['SAMPLESET'], experiment=exp)
            sampleset = {'set_id': c_setn.pk, 'fractions': {}, 'files': {}}
            for dsf in ads.analysisdsinputfile_set.all():
                c_fn = m.Condition.objects.create(name=dsf.sfile.filename,
                        cond_type=m.Condition.Condtype['FILE'], experiment=exp)
                sampleset['files'][dsf.sfile.filename] = c_fn.pk
                if ads.regex != '':
                    frnum = re.match(ads.regex, dsf.sfile.filename).group(1)
                    c_fr = m.Condition.objects.create(name=frnum,
                            cond_type=m.Condition.Condtype['FRACTION'], experiment=exp)
                    c_fr.parent_conds.add(c_setn)
                    c_fn.parent_conds.add(c_fr)
                else:
                    c_fn.parent_conds.add(c_setn)
            dsorganisms = ads.dataset.datasetspecies_set.all()
            if not dsorganisms.count():
                raise RuntimeError('Must enter organism in dataset metadata in order to load results')
            organisms.update([x.species_id for x in dsorganisms])
            clean_set = re.sub('[^a-zA-Z0-9_]', '_', ads.setname.setname)
            samplesets[clean_set] = sampleset
        if len(organisms) > 1:
            raise RuntimeError('Multiple organism-datasets are not possible to load in result service')
        organism_id = organisms.pop()


        # Sample name and group name are repeated in sampletable so they use get_or_create
        # Can also do that because they cant be duplicate in experiment, like e.g.
        # fractions or channels over multiple sets
        # TODO exempt them from deletion above?
        samples = {'groups': {}, 'samples': {}, }
        for ch, setn, sample, sgroup in analysis.analysissampletable.samples:
            clean_group = re.sub('[^a-zA-Z0-9_]', '_', sgroup)
            clean_sample = re.sub('[^a-zA-Z0-9_]', '_', sample)
            clean_set = re.sub('[^a-zA-Z0-9_]', '_', setn)
            if sgroup != '':
                gss = f'{clean_group}_{clean_sample}_{clean_set}___{ch}'
                c_group, _cr = m.Condition.objects.get_or_create(name=sgroup,
                        cond_type=m.Condition.Condtype['SAMPLEGROUP'], experiment=exp)
                samples['groups'][gss] = c_group.pk
            else:
                gss = f'{clean_sample}_{clean_set}___{ch}'
            c_sample, _cr = m.Condition.objects.get_or_create(name=sample,
                    cond_type=m.Condition.Condtype['SAMPLE'], experiment=exp)
            #samples['samples'][gss] = c_sample.pk
            c_ch = m.Condition.objects.create(name=ch, cond_type=m.Condition.Condtype['CHANNEL'],
                    experiment=exp)
            samples[gss] = c_ch.pk
            # Now add hierarchy:
            c_ch.parent_conds.add(samplesets[clean_set]['set_id'])
            c_ch.parent_conds.add(c_sample)
            # TODO how to treat non-grouped sample? currently this is X__POOL
            if sgroup != '':
                c_sample.parent_conds.add(c_group)

        # Output files headers according to their DB entry
        headers = {'pep': {'psmcount': output.psmcountfield, 'fdr': output.pepfdrfield,
            'peptide': output.peppeptide, 'isobaric': []},
            'psm': {'fdr': output.psmfdrfield, 'fn': output.psmfnfield, 'scan': output.scanfield,
                'setname': output.psmsetname, 'peptide': output.psmpeptide, 'score': output.psmscorefield}}

        plexq = Q(dataset__quantdataset__quanttype__shortname__contains='plex')
        plexq |= Q(dataset__quantdataset__quanttype__shortname='tmtpro')
        for plextype in analysis.datasetsearch_set.filter(plexq).distinct(
                'dataset__quantdataset__quanttype__shortname'):
            ptname = plextype.dataset.quantdataset.quanttype.shortname
            plextype_trf = {'tmtpro': 'tmt16plex'}.get(ptname, ptname)
            headers['pep']['isobaric'].append(plextype_trf)
        pepfile = os.path.join(analysis.storage_dir, output.pepfile)
        b_ana_mgr = am.AnalysisBaseanalysis.objects.filter(analysis=analysis, rerun_from_psms=True)
        base_analysis = False
        # Get potentially nested base analysis for PSM tables:
        while b_ana_mgr.count():
            base_analysis = b_ana_mgr.get().base_analysis
            b_ana_mgr = am.AnalysisBaseanalysis.objects.filter(analysis=base_analysis,
                    rerun_from_psms=True)

        if base_analysis:
            base_output = base_analysis.nextflowsearch.nfworkflow.wfoutput
            lookupfile = os.path.join(base_analysis.storage_dir, base_output.lookup)
            psmfile = os.path.join(base_analysis.storage_dir, base_output.psmfile)
        else:
            lookupfile = os.path.join(analysis.storage_dir, output.lookup)
            psmfile = os.path.join(analysis.storage_dir, output.psmfile)
        self.run_tasks.append(((exp.token, organism_id, lookupfile, pepfile, psmfile, headers, samplesets, samples), {}))
        print(self.run_tasks)
