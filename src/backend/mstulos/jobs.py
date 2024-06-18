import re
import os

from django.db.models import Q

from jobs.jobs import BaseJob
from mstulos import models as m
from mstulos import tasks as mt
from analysis import models as am


# DDA pipeline 2.8 and up have OK format, before that: amount/count
# before 2.6 there is X__POOL
# before 2.3 # PSMs is not correct (identical)

class ProcessAnalysis(BaseJob): 
    refname = 'ingest_search_results'
    task = mt.summarize_result_peptable

    # version 1, 2021 msstitch sqlite
    """
    kwargs = {
    'analysis_id': 1,
    'token': abcdd1234 ,
    """
    # FIXME: need mods defined as unimod when analysing
    # ideally we have a unimod lookup in Kantele, can download from there
    # FIXME this is not atomic view, if crash -> DB entries!
    # maybe instead of job, put some of this in view that created/saved analysis
   
    #getfiles_query()? needed
    def process(self, **kwargs):
        analysis = am.Analysis.objects.select_related('nextflowsearch__nfwfversionparamset__wfoutput').get(
                pk=kwargs['analysis_id'])
        output = analysis.nextflowsearch.nfwfversionparamset.wfoutput
        # Output files headers according to their DB entry
        headers = {'pep': {'psmcount': output.psmcountfield, 'fdr': output.pepfdrfield,
            'peptide': output.peppeptidefield, 'protein': output.pepprotfield,
            'gene': output.pepgenefield, 'isobaric': []},
            'psm': {'fdr': output.psmfdrfield, 'fn': output.psmfnfield, 'scan': output.scanfield,
                'setname': output.psmsetname, 'peptide': output.psmpeptide, 'score': output.psmscorefield}}

        plexq = Q(dataset__quantdataset__quanttype__shortname__contains='plex')
        plexq |= Q(dataset__quantdataset__quanttype__shortname='tmtpro')
        for plextype in analysis.datasetanalysis_set.filter(plexq).distinct(
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
            base_output = base_analysis.nextflowsearch.nfwfversionparamset.wfoutput
            psmfile = os.path.join(base_analysis.storage_dir, base_output.psmfile)
        else:
            psmfile = os.path.join(analysis.storage_dir, output.psmfile)
        self.run_tasks.append(((kwargs['token'], kwargs['organism_id'], pepfile, psmfile, headers, kwargs['samplesets'], kwargs['samples']), {}))
        print(self.run_tasks)
