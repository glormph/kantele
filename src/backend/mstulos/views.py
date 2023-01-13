import json

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
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
    # FIXME open exp for uploads so we dont get duplicates when task runs multiple
    # times? Proba not nec bc will enforce unique on DB level


def upload_proteins(request):
    pass


def upload_peptides(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'])
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    # FIXME pep-prot relations
    stored_peps = {}
    for pep in data['peptides']:
        pseq, _cr = m.PeptideSeq.objects.get_or_create(seq=pep['bareseq'])
        # FIXME think of encodign for peptide to be created from e.g. MSGF or other SE
        mol, _cr = m.PeptideMolecule.objects.get_or_create(sequence=pseq, encoded_pep=pep['peptide'])
        stored_peps[pep['peptide']] = mol.pk
        # go over condistions!
        for cond_id, fdr in pep['qval'].items():
            m.PeptideFDR.objects.create(peptide=mol, fdr=fdr, condition_id=cond_id)
        for cond_id, nrpsms in pep['psmcount'].items():
            m.AmountPSMsPeptide.objects.create(peptide=mol, value=nrpsms, condition_id=cond_id)
        for cond_id, quant in pep['isobaric'].items():
            m.PeptideIsoQuant.objects.create(peptide=mol, value=quant, condition_id=cond_id)
    return JsonResponse({'error': False, 'pep_ids': stored_peps})


def upload_psms(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'])
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    for psm in data['psms']:
        m.PSMFDR.objects.create(peptide_id=psm['pep_id'], fdr=psm['qval'], scan=psm['scan'],
                condition_id=psm['fncond'])



def upload_done(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        exp = m.Experiment.objects.get(token=data['token'])
    except m.Experiment.DoesNotExist:
        return JsonResponse({'error': 'Not allowed to access'}, status=403)
    exp.upload_complete = True
    exp.save()
    jv.set_task_done(data['task_id'])
    return JsonResponse({'error': False})


