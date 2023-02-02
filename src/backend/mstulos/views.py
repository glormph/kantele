import json
from base64 import b64decode

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.aggregates import ArrayAgg
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, F
from django.db.models.functions import Upper
from django.core.paginator import Paginator

from mstulos import models as m
from jobs import views as jv


# FIXME:
# fix fixmes in job/task
# have shareable URLs for search including unrolls
# create plots for TMT
# gene/protein centric tables

def paginate(qset, pnr):
    pages = Paginator(qset, 100)
    pages.ELLIPSIS = '__'
    try:
        pnr = int(pnr)
    except ValueError:
        pnr = 1
    page = pages.get_page(pnr)
    page_context = {'last_res_nr': page.end_index(), 'total_res_nr': pages.count,
            'first_res_nr': page.start_index(), 'page_nr': pnr,
            'pagerange': [x for x in pages.get_elided_page_range(pnr, on_each_side=2, on_ends=1)]}
    return page, page_context


# peptide centric:
@login_required
def frontpage(request):
    rawq = request.GET.get('q', False)
    qfields = ['peptides', 'proteins', 'genes', 'experiments']
    textfields = [f'{x}_text' for x in qfields] 
    exactfields = [f'{x}_text_exact' for x in qfields]
    idfields = [f'{x}_id' for x in qfields]
    if rawq:
        # fields/text/id must have right order as in client?
        # this because client doesnt send keys to have shorter b64 qstring
        getq = json.loads(b64decode(rawq))
        q = {f: getq[i] for i, f in enumerate(idfields + textfields + exactfields)}
        q['expand'] = {k: v for k,v in zip(qfields[1:],
            getq[len(idfields + textfields + exactfields):])}
    else:
        q = {f: [] for f in idfields}
        q.update({**{f: '' for f in textfields}, **{f: 1 for f in exactfields}})
        q['experiments_text_exact'] = 0
        q['expand'] = {'proteins': 0, 'genes': 0, 'experiments': 0}
    # first query filtering:
    qset = m.PeptideSeq.objects
    if q['peptides_id']:
        qset = qset.filter(pk__in=[x[0] for x in q['peptides_id']])
    if q['peptides_text']:
        qset = qset.annotate(pepupp=Upper('seq'))
        if q['peptides_text_exact']:
            qset = qset.filter(pepupp__in=q['peptides_text'].upper().split('\n'))
        else:
            peptq = Q()
            for pept in q['peptides_text'].upper().split('\n'):
                peptq |= Q(pepupp__contains=pept)
            qset = qset.filter(peptq)
            print(peptq)
    if q['experiments_id']:
        qset = qset.filter(peptideprotein__experiment__in=[x[0] for x in q['experiments_id']])
    if q['experiments_text']:
        qset = qset.annotate(eupp=Upper('peptideprotein__experiment__analysis__name'))
        exp_t_q = Q()
        for exp_t in q['experiments_text'].upper().split('\n'):
            exp_t_q |= Q(eupp__contains=exp_t)
        qset = qset.filter(exp_t_q)
        #(eupp__in=[x.upper() for x in q['experiments_text'].split('\n')])
    if q['proteins_id']:
        qset = qset.filter(peptideprotein__protein__in=[x[0] for x in q['proteins_id']])
    if q['proteins_text']:
        qset = qset.annotate(pupp=Upper('peptideprotein__protein__name'))
        if q['proteins_text_exact']:
            qset = qset.filter(pupp__in=[x.upper() for x in q['proteins_text'].split('\n')])
        else:
            ptxtq = Q()
            for ptxt in q['proteins_text'].upper().split('\n'):
                ptxtq |= Q(pupp__contains=ptxt)
            qset = qset.filter(ptxtq)
    if q['genes_id']:
        qset = qset.filter(peptideprotein__proteingene__gene__in=[x[0] for x in q['genes_id']])
    if q['genes_text']:
        qset = qset.annotate(gupp=Upper('peptideprotein__proteingene__gene__name'))
        if q['genes_text_exact']:
            qset = qset.filter(gupp__in=[x.upper() for x in q['genes_text'].split('\n')])
        else:
            gtxtq = Q()
            for gtxt in q['genes_text'].upper().split('\n'):
                gtxtq |= Q(gupp__contains=gtxt)
            qset = qset.filter(gtxtq)
    
    fields = {'seq', 'id', 
            'peptideprotein__protein__name', 'peptideprotein__protein_id',
            'peptideprotein__proteingene__gene__name', 'peptideprotein__proteingene__gene_id', 'peptideprotein__experiment__analysis__name', 'peptideprotein__experiment_id'}
    agg_fields = {
            'proteins': ('peptideprotein__protein__name', 'peptideprotein__protein_id'),
            'genes': ('peptideprotein__proteingene__gene__name', 'peptideprotein__proteingene__gene_id'),
            'experiments': ('peptideprotein__experiment__analysis__name', 'peptideprotein__experiment_id'),
            }
    for aggr_col in qfields[1:]:
        if not q['expand'][aggr_col]:
            qset = qset.annotate(**{aggr_col: ArrayAgg(agg_fields[aggr_col][0])})
            idkey = f'{aggr_col}_id'
            qset = qset.annotate(**{idkey: ArrayAgg(agg_fields[aggr_col][1])})
            fields.update((aggr_col, idkey))
            fields.difference_update(agg_fields[aggr_col])
        
    qset = qset.values(*fields).order_by('pk')
    rows = []
    pnr = request.GET.get('page', 1)
    page, page_context = paginate(qset, pnr)
    for pep in page:
        agg_prots = pep.get('proteins', False)
        agg_genes = pep.get('genes', False)
        agg_exps = pep.get('experiments', False)
        prot = pep.get('peptideprotein__protein__name', False)
        pid = pep.get('peptideprotein__protein_id', False)
        gene = pep.get('peptideprotein__proteingene__gene__name', False)
        gid = pep.get('peptideprotein__proteingene__gene_id', False)
        exp = pep.get('peptideprotein__experiment__analysis__name', False)
        eid = pep.get('peptideprotein__experiment_id', False)
        row = {'id': pep['id'], 'seq': pep['seq']}
            # Have to set() the below in case there are duplicates:
            # not sure if those can be fished out WITHOUT keeping the
            # ID order and name order correlate, either in PG SQL or python
        if agg_prots:
            row['proteins'] = list(set(zip(pep['proteins_id'], agg_prots)))
        if agg_genes:
            row['genes'] = list(set(zip(pep['genes_id'], agg_genes)))
        if agg_exps:
            row['experiments'] = list(set(zip(pep['experiments_id'], agg_exps)))
        if not agg_prots:
            row['proteins'] = [(pid, prot)]
        if not agg_genes:
            row['genes'] = [(gid, gene)]
        if not agg_exps:
            row['experiments'] = [(eid, exp)]
        rows.append(row)
    context = {'tulos_data': rows, 'filters': q, **page_context,
            'total_exp': m.Experiment.objects.filter(upload_complete=True).count(), 'q': rawq or '',
            'total_pep': m.PeptideSeq.objects.count(),
            }
    return render(request, 'mstulos/front_pep.html', context=context)


#@login_required
def peptide_table(request):
    rawq = request.GET.get('q', False)
    if rawq:
        '''{ peptide_id: [exp_id, exp_id2, ...], ...}'''
        pepquery = json.loads(b64decode(rawq))
    else:
        pepquery = {}
    peptides = []
    filterq = Q()
    setorsample = 'SAMPLESET'
    for pepid, exps in pepquery.items():
        filterq |= Q(peptide__sequence_id=pepid, setorsample__experiment__in=exps)
    peptides = m.IdentifiedPeptide.objects.filter(filterq).values('peptide__encoded_pep', 'peptidefdr__fdr', 'amountpsmspeptide__value', 'setorsample__name', 'setorsample__experiment__analysis__name').order_by('peptide_id', 'setorsample__experiment_id', 'setorsample_id')
    pnr = request.GET.get('page', 1)
    page, page_context = paginate(peptides, pnr)
    context = {'peptides': page, **page_context}
    return render(request, 'mstulos/peptides.html', context=context)
    


#@login_required
def psm_table(request):
    '''Given a combination of peptide-sequence-ids and experiments they are in,
    produce a PSM table'''
    # TODO is it faster to loop over the peptides (all given peps x all given experiments) 
    # in python, or should we keep the SQL statement?
    rawq = request.GET.get('q', False)
    if rawq:
        '''{ peptide_id: [exp_id, exp_id2, ...], ...}'''
        pepquery = json.loads(b64decode(rawq))
    else:
        pepquery = {}
    all_exp_ids = {y for x in pepquery.values() for y in x}
    exp_files = {eid: m.Condition.objects.filter(cond_type=m.Condition.Condtype['FILE'],
        experiment=eid) for eid in all_exp_ids}

    filterq = Q()
    for pepid, exps in pepquery.items():
        pepexps = [exp_files[eid] for eid in exps]
        filterq |= Q(peptide__sequence_id=pepid, filecond__experiment__in=exps)
    sample_cond = 'filecond__parent_conds__name'
    sample_cond_id = 'filecond__parent_conds__id'
    qset = m.PSM.objects.filter(filterq).annotate(sample_or_set=F(sample_cond)).values('peptide__encoded_pep', 'filecond__name', 'scan', 'fdr', 'score', 'filecond__experiment__analysis__name', 'sample_or_set').order_by('peptide_id', 'filecond__experiment_id', sample_cond_id, 'filecond_id')
    pnr = request.GET.get('page', 1)
    page, page_context = paginate(qset, pnr)
    context = {'psms': page, **page_context}
    return render(request, 'mstulos/psms.html', context=context)


@require_POST
def upload_proteins(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_complete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    stored_prots, stored_genes = {}, {}
    organism_genes = m.Gene.objects.filter(organism_id=data['organism_id'])
    organism_proteins = m.Protein.objects.filter(peptideprotein__proteingene__gene__in=organism_genes)
    existing_genes = {x.name: x.pk for x in organism_genes}
    existing_prots = {x.name: x.pk for x in organism_proteins}
    for prot, gene in data['protgenes']:
        if gene in existing_genes:
            store_gid = existing_genes[gene]
        else:
            store_gid = m.Gene.objects.get_or_create(name=gene, organism_id=data['organism_id'])[0].pk
        if prot in existing_prots:
            store_pid = existing_prots[prot]
        else:
            # cannot get_or_create here, we only have name field
            store_pid = m.Protein.objects.create(name=prot).pk
        stored_prots[prot] = store_pid
        stored_genes[gene] = store_gid
    return JsonResponse({'error': False, 'protein_ids': stored_prots, 'gene_ids': stored_genes})


@require_POST
def upload_pepprots(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_complete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    stored_peps = {}
    for pep, bareseq, prot_id, gene_id in data['pepprots']:
        pepseq, _cr = m.PeptideSeq.objects.get_or_create(seq=bareseq)
        if _cr:
            #m.PeptideProtein.objects.create(peptide=pepseq, protein_id=prot_id, experiment=exp)
            mol = m.PeptideMolecule.objects.create(sequence=pepseq, encoded_pep=pep)
        else:
            mol, _cr = m.PeptideMolecule.objects.get_or_create(sequence=pepseq, encoded_pep=pep)
        pepprot, _cr = m.PeptideProtein.objects.get_or_create(peptide=pepseq, protein_id=prot_id, experiment=exp)
        if gene_id:
            m.ProteinGene.objects.get_or_create(pepprot=pepprot, gene_id=gene_id)
            
        stored_peps[pep] = mol.pk
    return JsonResponse({'error': False, 'pep_ids': stored_peps})


@require_POST
def upload_peptides(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_complete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    stored_peps = {}
    for pep in data['peptides']:
        # FIXME think of encodign for peptide to be created from e.g. MSGF or other SE
        idpeps = {}
        # TODO go over condistions!
        for cond_id, fdr in pep['qval']:
            idpep = m.IdentifiedPeptide.objects.create(peptide_id=pep['pep_id'], setorsample_id=cond_id)
            idpeps[cond_id] = idpep
            m.PeptideFDR.objects.create(fdr=fdr, idpep=idpep)
        for cond_id, nrpsms in pep['psmcount']:
            m.AmountPSMsPeptide.objects.create(value=nrpsms, idpep=idpeps[cond_id])
        for cond_id, quant in pep['isobaric']:
            m.PeptideIsoQuant.objects.create(peptide_id=pep['pep_id'], value=quant, channel_id=cond_id)
    return JsonResponse({'error': False, 'pep_ids': stored_peps})


@require_POST
def upload_psms(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_complete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    for psm in data['psms']:
        m.PSM.objects.create(peptide_id=psm['pep_id'], fdr=psm['qval'], scan=psm['scan'],
                filecond=psm['fncond'], score=psm['score'])
    return JsonResponse({'error': False})


@require_POST
def upload_done(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_complete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)

    exp.upload_complete = True
    exp.save()
    jv.set_task_done(data['task_id'])
    return JsonResponse({'error': False})
