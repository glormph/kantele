import json

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q

from mstulos import models as m
from jobs import views as jv


def frontpage_context():
    context = {
            'proteins': [],
            'peptides': [],
            'genes': [],
            'exps': [],
            'search': [],
        }
    return context


@login_required
def frontpage(request):
    context = {
            'searchresult': [
                {'name': 'TP53', 'type': 'Gene', 'expnr': 20, 'active': True},
                {'name': 'IAMAPEPTID', 'type': 'Peptide', 'expnr': 2320, 'active': False},
                {'name': 'IAMAPEPTIDANDIAMREALLYREALLYREALLYREALLYLARGE', 'type': 'Peptide', 'expnr': 2320, 'active': False},
                {'name': 'ALL_CCK', 'type': 'Experiment', 'expnr': 2, 'active': False},
                ],
            'expresult': [
                {'name': 'My great experiment', 'date': '2020-04-23', 'user': 'maria', 'cond': '5/12', 'psms': '0.0023'},
                {'name': 'CAR T CCK big advanced', 'date': '2018-09-05', 'user': 'rozbeh', 'cond': '22/25', 'psms': '0.0052'},
                {'name': 'A431, what else?', 'date': '2017-12-20', 'user': 'rui', 'cond': '8/8', 'psms': '0.0005'},
                ],
            'proteins': [],
        'peptides': [],
        'genes': [],
        'exps': [],
        }
    return render(request, 'mstulos/front.html', context)

@login_required
def find_query(request):
    pepseq = request.GET['q'].upper()
    query = Q(bareseq__seq__contains=pepseq)
    query |= Q(encoded_pep__contains=pepseq)
    pepmols = m.PeptideMolecule.objects.filter(query).filter(pepfdr__isnull=False)
    results = [{'id': x.pk, 'txt': x.encoded_pep,
        'type': 'peptide',
        'expnum': x.pepfdr_set.distinct('condition__experiment').count(),
        'condnum': x.pepfdr_set.count(),
        'experiments': [{'name': pf['condition__experiment__name'],
            'id': pf['condition__experiment__pk'],
            } for pf in x.pepfdr_set.distinct('condition__experiment').values('condition__experiment__name', 'condition__experiment__pk')],
        } for x in pepmols]
    return JsonResponse({'results': results})


@login_required
def get_results(request, restype, resid):
    if restype == 'peptide':
        m.PepFDR.objects.filter(peptide_id=resid)
    return JsonResponse({})


@login_required
def get_data(request):
    """
    input:
    {type: peptide, ids: [1,2,3,4], experiments: [1,2,3,4]}
    
    output:
    {pepfdr: 
          {exp_id: {name: exp_name, samples: 
    maybe [{exp: 1, sam: 3, 3: 0.002, 4: 0.001, 5: 0, ...}...]
    """
    data = json.loads(request.body.decode('utf-8'))
    pepquant, pepfdr = {}, {}
    if data['type'] == 'peptide':
        for pf in m.PepFDR.objects.filter(peptide_id__in=data['ids'],
                condition__experiment_id__in=data['experiments']).select_related(
                'peptide').order_by('condition__experiment_id'):
            #pepquant[pf.condition.experiment_id].append('sam': sam, 'featid': pf.peptide_id, 'value': pf.value})
            if pf.condition.experiment_id not in pepfdr:
                pepfdr[pf.condition.experiment_id] = {}
            sam = pf.condition.name
            try:
                pepfdr[pf.condition.experiment_id][sam][pf.peptide_id] = pf.value
            except KeyError:
                pepfdr[pf.condition.experiment_id][sam] = {pf.peptide_id: pf.value}
        for pq in m.PeptideQuantResult.objects.filter(peptide_id__in=data['ids'],
                condition__experiment_id__in=data['experiments']).select_related(
                'peptide'):
            sam = pq.condition.name
            try:
                pepquant[sam][pq.peptide_id] = (pq.peptide.encoded_pep, pq.value)
            except KeyError:
                pepquant[sam] = {pq.peptide_id: (pq.peptide.encoded_pep, pq.value)}
    return JsonResponse({'pepfdr': pepfdr, 'pepquant': {}})


def start_exp_upload(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'])
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    # need to open upload in a job, not a task  view??
    # FIXME open exp for uploads so we dont get duplicates when task runs multiple
    # times? Proba not nec bc will enforce unique on DB level


@require_POST
def upload_proteins(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'], upload_comlete=False)
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    except KeyError:
        return JsonResponse({'error': 'Bad request to mstulos uploads'}, status=400)
    stored_prots = {}
    organism_proteins = {x.name: x.pk for x in m.Protein.objects.filter(organism_id=data['organism_id'])}
    organism_genes = {x.name: x.pk for x in m.Gene.objects.filter(organism_id=data['organism_id'])}
    for prot, gene in data['protgenes']:
        if prot in organism_proteins:
            store_pid = organism_proteins[prot]
        else:
            store_pid = m.Protein.objects.get_or_create(name=prot, organism_id=data['organism_id'])[0].pk
        if gene in organism_proteins:
            store_gid = organism_genes[gene]
        else:
            store_gid = m.Gene.objects.get_or_create(name=gene, organism_id=data['organism'])[0].pk
        m.ProteinGene.objects.get_or_create(protein_id=store_pid, gene=store_gid, experiment=exp)
        stored_prots[prot] = store_pid
    return JsonResponse({'error': False, 'protein_ids': stored_prots})


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
    for pep, bareseq, prot_id in data['pepprots']:
        pepseq, _cr = m.PeptideSeq.objects.get_or_create(seq=bareseq)
        if _cr:
            m.PeptideProtein.objects.create(peptide=pepseq, protein_id=prot_id, experiment=exp)
            mol = m.PeptideMolecule.objects.create(sequence=pepseq, encoded_pep=pep)
        else:
            mol, _cr = m.PeptideMolecule.objects.get_or_create(sequence=pepseq, encoded_pep=pep)
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
        # go over condistions!
        for cond_id, fdr in pep['qval']:
            m.PeptideFDR.objects.create(peptide_id=pep['pep_id'], fdr=fdr, condition_id=cond_id)
        for cond_id, nrpsms in pep['psmcount']:
            m.AmountPSMsPeptide.objects.create(peptide=pep['pep_id'], value=nrpsms, condition_id=cond_id)
        for cond_id, quant in pep['isobaric']:
            m.PeptideIsoQuant.objects.create(peptide=pep['pep_id'], value=quant, condition_id=cond_id)
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
                condition_id=psm['fncond'], score=psm['score'])


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


