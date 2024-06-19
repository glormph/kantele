import os
import re
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task

from kantele import settings
from jobs.post import update_db

# TODO
# matching to proteins, how will we do that? use sqlite, do not parse fasta, since fasta have
# releases every so often!
# in this case we need the protein to be multiple, per experiment
# upload proteins first, get IDs and track, 

# TODO multi-organism (i.e. metaproteomics) is a bit different, the sample contains a blend
# of organisms and you run multi-db, then we have to keep track of which proteins is which
# organism -> some kind of parsing required. Our ddamsproteomics pipeline doesnt handle
# that smoothly, youd like a fasta/organism coupling then (entered by user), and then
# read fasta to keep track/lookup protein names to organism when running this


@shared_task(bind=True, queue=settings.QUEUE_SEARCH_INBOX)
def summarize_result_peptable(self, token, organism_id, peptide_file, psm_file, outheaders):
    # FIXME maybe not do proteins when running 6FT? Need to make it selectable!
    # FIXME exempt proteogenomics completely for now or make button (will be misused!)
    # FIXME not all runs have genes
    # FIXME isobaric has not been fone yet!

    # Create conditions etc
    init_url = urljoin(settings.KANTELEHOST, reverse('mstulos:init_store'))
    resp = update_db(init_url, json={'token': token})
    resp.raise_for_status()
    samplesets, samples = resp.json()['samplesets'], resp.json()['samples']

    # Store proteins, genes found
    protgenes = []
    storedproteins, storedgenes = {}, {}
    protein_url = urljoin(settings.KANTELEHOST, reverse('mstulos:upload_proteins'))
    pepheader = outheaders['pep']
    with open(os.path.join(settings.ANALYSISSHARE, peptide_file)) as fp:
        header = next(fp).strip('\n').split('\t')
        protfield = header.index(pepheader['protein'])
        genefield = header.index(pepheader['gene'])
        for line in fp:
            line = line.strip('\n').split('\t')
            # FIXME if genes:
            protein = line[protfield]
            if protein not in storedproteins:
                protgenes.append([protein, line[genefield]])
            if len(protgenes) == 1000:
                resp = update_db(protein_url, json={'protgenes': protgenes, 'token': token,
                    'organism_id': organism_id})
                resp.raise_for_status()
                storedproteins.update(resp.json()['protein_ids'])
                storedgenes.update(resp.json()['gene_ids'])
                protgenes = []
    if len(protgenes):
        resp = update_db(protein_url, json={'protgenes': protgenes, 'token': token,
                'organism_id': organism_id})
        resp.raise_for_status()
        storedproteins.update(resp.json()['protein_ids'])
        storedgenes.update(resp.json()['gene_ids'])

    # Now store all peptide sequences found with proteins/genes association, and
    # any conditions used
    pepurl = urljoin(settings.KANTELEHOST, reverse('mstulos:upload_peptides'))
    storedpeps = {} # for ID tracking
    with open(os.path.join(settings.ANALYSISSHARE, peptide_file)) as fp:
        header = next(fp).strip('\n').split('\t')
        conditions = {'psmcount': [], 'qval': [], 'isobaric': []}
        # find header fields and match with conditions by setname/sample/channel
        # FIXME do bareseq thing on backend
        pepfield = header.index(pepheader['peptide'])
        for ix, field in enumerate(header):
            # bit strict handling with f'_PSM count' to avoid Quanted PSM count fields..
            # Text parsing is not always super clean. We may need to think about that in
            # the pipeline itself, to make sure it is parseable, or encode somehow
            if pepheader['psmcount'] and f'_{pepheader["psmcount"]}' in field:
                setname = re.sub(f'_{pepheader["psmcount"]}', '', field)
                conditions['psmcount'].append((ix, samplesets[setname]['set_id']))
            elif pepheader['fdr'] and pepheader['fdr'] in field:
                setname = re.sub(f'_{pepheader["fdr"]}', '', field)
                conditions['qval'].append((ix, samplesets[setname]['set_id']))
            elif pepheader['isobaric'] and any(plex in field for plex in pepheader['isobaric']):
                plex_re = '(.*)_[a-z0-9]+plex_([0-9NC]+)'
                # FIXME isobaric lookup is not done in jobs yet!
                # Need to remove e.g. plex_126 - Quanted PSMs, with $
                if re.match(f'{plex_re}$', field):
                    sample_set_ch = re.sub(plex_re, '\\1___\\2', field)
                    conditions['isobaric'].append((ix, samples[sample_set_ch]))

        # conditions is now e.g. {'qval': [(header_ix, set_id), ...],
        #                       'isobaric': [(header_ix, sample_set_ch
        # parse peptide table and upload
        pep_values = []
        for line in fp:
            line = line.strip('\n').split('\t')
            storepep = {'pep': line[pepfield], 'prot': storedproteins[line[protfield]],
                'gene': storedgenes.get(line[genefield], False)}
            for datatype, col_conds in conditions.items():
                storepep[datatype] = []
                for col, cond_id in col_conds:
                    storepep[datatype].append((cond_id, line[col]))
            pep_values.append(storepep)
            if len(pep_values) == 1000:
                resp = update_db(pepurl, json={'peptides': pep_values, 'token': token})
                resp.raise_for_status()
                pep_values = []
                storedpeps.update(resp.json()['pep_ids'])
        if len(pep_values):
            resp = update_db(pepurl, json={'peptides': pep_values, 'token': token})
            resp.raise_for_status()
            storedpeps.update(resp.json()['pep_ids'])

            # TODO encoded_pep is likely for searching stuff, not sure how this was
            # thought out! Or if the MSGF+ format is the one we're using, but here we go
            # get frontend to search peptides to decide on how to store
            # mods need parsing etc, but nice with cut/paste from PSM table
            # NO! encoded pep should be possible to store without MSGF also
            # just easy to calculate!!!
            # so we need MSGF->encoded pep and other SE -> encoded pep
            # on storing and on looking up!! A hash would be good of peptide
            # with mods 

    # Go through PSM table with peptide_ids as map
    psm_header = outheaders['psm']
    psms = []
    psmurl = urljoin(settings.KANTELEHOST, reverse('mstulos:upload_psms'))
    with open(os.path.join(settings.ANALYSISSHARE, psm_file)) as fp:
        header = next(fp).strip('\n').split('\t')
        # FIXME catch these index() calls!
        fncol = header.index(psm_header['fn'])
        scancol = header.index(psm_header['scan'])
        setcol = header.index(psm_header['setname'])
        pepcol = header.index(psm_header['peptide'])
        fdrcol = header.index(psm_header['fdr'])
        scorecol = header.index(psm_header['score'])
        for line in fp:
            line = line.strip('\n').split('\t')
            storepsm = {}
            fn_cond_id = samplesets[line[setcol]]['files'][line[fncol]]
            # FIXME catch no peps, no fdr, no scan -- what??
            storepsm = {'scan': line[scancol], 'qval': line[fdrcol], 'fncond': fn_cond_id,
                    'score': line[scorecol], 'pep_id': storedpeps[line[pepcol]]}
            psms.append(storepsm)
            if len(psms) > 10000:
                resp = update_db(psmurl, json={'psms': psms, 'token': token})
                resp.raise_for_status()
                psms = []
        if len(psms):
            resp = update_db(psmurl, json={'psms': psms, 'token': token})
            resp.raise_for_status()
    
    # Finished, report done
    update_db(urljoin(settings.KANTELEHOST, reverse('mstulos:upload_done')), json={'token': token, 'task_id': self.request.id})



x = ('jorrit/14394_STD_GMPSDL1-allsample_pool_denominator_20221102_14.52/peptides_table.txt', 'georgios/14392_STD_GMPSDL1-13_20221101_15.20/target_psmtable.txt', 'georgios/14392_STD_GMPSDL1-13_20221101_15.20/target_psmlookup.sql', {'pep': {'psmcount': 'PSM count', 'fdr': 'q-value', 'peptide': 'Peptide sequence', 'isobaric': []}, 'psm': {'fdr': 'PSM q-value', 'fn': 'SpectraFile', 'scan': 'ScanNum', 'setname': 'Biological set', 'peptide': 'Peptide'}}, {'set1': {'set_id': 269, 'fractions': {}, 'files': {'GMPSDL1-13_Labelcheck_4hrs_3of10_set01.mzML': 270}}}, {'groups': {}, 'samples': {'GMPSDL_1_set1___126': 271, 'GMPSDL_2_set1___127N': 273, 'GMPSDL_3_set1___127C': 275, 'GMPSDL_4_set1___128N': 277, 'GMPSDL_5_set1___128C': 279, 'GMPSDL_6_set1___129N': 281, 'GMPSDL_7_set1___129C': 283, 'GMPSDL_8_set1___130N': 285, 'GMPSDL_9_set1___130C': 287, 'GMPSDL_10_set1___131N': 289, 'GMPSDL_11_set1___131C': 291, 'GMPSDL_12_set1___132N': 293, 'GMPSDL_13_set1___132C': 295, 'POOL(EAPSDL1-30)_set1___133N': 297, 'empty_set1___133C': 299, 'empty_set1___134N': 299}, 'GMPSDL_1_set1___126': 272, 'GMPSDL_2_set1___127N': 274, 'GMPSDL_3_set1___127C': 276, 'GMPSDL_4_set1___128N': 278, 'GMPSDL_5_set1___128C': 280, 'GMPSDL_6_set1___129N': 282, 'GMPSDL_7_set1___129C': 284, 'GMPSDL_8_set1___130N': 286, 'GMPSDL_9_set1___130C': 288, 'GMPSDL_10_set1___131N': 290, 'GMPSDL_11_set1___131C': 292, 'GMPSDL_12_set1___132N': 294, 'GMPSDL_13_set1___132C': 296, 'POOL(EAPSDL1-30)_set1___133N': 298, 'empty_set1___133C': 300, 'empty_set1___134N': 301})

