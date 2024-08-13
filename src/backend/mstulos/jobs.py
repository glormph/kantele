import re
import os

from django.db.models import Q

from jobs.jobs import BaseJob
from mstulos import models as m
from mstulos import tasks as mt
from analysis import models as am
from rawstatus import models as rm


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
    # FIXME this is not atomic view, if crash -> DB entries!
    # maybe instead of job, put some of this in view that created/saved analysis
   
    #getfiles_query()? needed
    def process(self, **kwargs):
        analysis = am.Analysis.objects.select_related('nextflowsearch__nfwfversionparamset__wfoutput').get(
                pk=kwargs['analysis_id'])
        output = analysis.nextflowsearch.nfwfversionparamset.wfoutput
        # Output files headers according to their DB entry
        headers = {'pep': {'psmcount': output.peppsmcountfield, 'fdr': output.pepfdrfield,
            'peptide': output.peppeptidefield, 'protein': output.pepprotfield,
            'ms1': output.pepms1field, 'isobaric': []},
            'psm': {'fdr': output.psmfdrfield, 'fn': output.psmfnfield, 'scan': output.scanfield,
                'setname': output.psmsetname, 'peptide': output.psmpeptide,
                'charge': output.psmchargefield, 'score': output.psmscorefield}}

        plexq = Q(dataset__quantdataset__quanttype__shortname__contains='plex')
        plexq |= Q(dataset__quantdataset__quanttype__shortname='tmtpro')
        for plextype in analysis.datasetanalysis_set.filter(plexq).distinct(
                'dataset__quantdataset__quanttype__shortname'):
            ptname = plextype.dataset.quantdataset.quanttype.shortname
            plextype_trf = {'tmtpro': 'tmt16plex'}.get(ptname, ptname)
            headers['pep']['isobaric'].append(plextype_trf)
        
        # Get fasta files
        fa_rc, fa_files, faerr = output.get_fasta_files(**analysis.nextflowsearch.job.kwargs['inputs'])
        psm_rc, psmfile, psmerr = output.get_psm_outfile(analysis)
        pep_rc, pepfile, peperr = output.get_peptide_outfile(analysis)
        
        if fa_rc or psm_rc or pep_rc:
            raise RuntimeError('\n'.join([faerr, psmerr, peperr]).strip())
        else:
            psmfile = psmfile.get()
            pepfile = pepfile.get()

        fa_files = [(x['pk'], x['servershare__name'], os.path.join(x['path'], x['filename']))
                for x in fa_files]
        pepfile_arg = (pepfile['sfile__servershare__name'],
                os.path.join(pepfile['sfile__path'], pepfile['sfile__filename']))
        psmfile_arg =  (psmfile['sfile__servershare__name'],
                os.path.join(psmfile['sfile__path'], psmfile['sfile__filename']))
        self.run_tasks.append(((kwargs['token'], kwargs['organism_id'], pepfile_arg, psmfile_arg, headers, fa_files), {}))
