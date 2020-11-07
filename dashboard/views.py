from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum
from django.db.models.functions import Trunc

from math import isnan

from datetime import datetime, timedelta

from analysis.models import AnalysisError, NextflowWfVersion
from rawstatus.models import Producer, RawFile
from dashboard import qcplots, models
from kantele import settings


def dashboard(request):
    instruments = Producer.objects.filter(msinstrument__active=True)
    return render(request, 'dashboard/dashboard.html',
                  {'instruments': zip([x.name for x in instruments], [x.id for x in instruments]),
                  'instrument_ids': [x.id for x in instruments]})


def fail_longitudinal_qc(data):
    """Called in case task detects QC run too bad to extract data from"""
    AnalysisError.objects.create(message=data['errmsg'], 
                                 analysis_id=data['analysis_id'])
    
def store_longitudinal_qc(data):
    try:
        qcrun = models.QCData.objects.get(rawfile_id=data['rf_id'])
    except models.QCData.DoesNotExist:
        qcrun = models.QCData(rawfile_id=data['rf_id'],
                              analysis_id=data['analysis_id'])
        qcrun.save()
        for plotname, qcdata in data['plots'].items():
            create_newplot(qcrun, qcdata, plotname)
    else:
        update_qcdata(qcrun, data)


def translate_plotname(qcname):
    """Translate names from QC pipeline to plot shortnames,
    TODO migrate shortnames so we are in sync with QC pipeline"""
    try:
        name = {
                'nrpsms': 'psms',
                'nrscans': 'scans',
                'nrpeptides': 'peptides',
                'nr_unique_peptides': 'unique_peptides',
                'nrproteins': 'proteins',
                'precursor_errors': 'perror',
                'msgfscores': 'msgfscore',
                'retention_times': 'rt',
                'peptide_areas': 'peparea',
                'ionmobilities': 'ionmob',
                }[qcname]
    except KeyError:
        name = qcname
    return name


def create_newplot(qcrun, qcdata, qcname):
    name = translate_plotname(qcname)
    if type(qcdata) == dict and 'q1' in qcdata:
        models.BoxplotData.objects.create(shortname=name, qcrun=qcrun,
                                          upper=qcdata['upper'],
                                          lower=qcdata['lower'],
                                          q1=qcdata['q1'], q2=qcdata['q2'],
                                          q3=qcdata['q3'])
    elif name == 'missed_cleavages':
        models.LineplotData.objects.bulk_create([models.LineplotData(qcrun=qcrun, value=num_psm, shortname='miscleav{}'.format(num_mc))
            for num_mc, num_psm in qcdata.items()])
    elif qcdata:
        # check if qcdata not false, eg peparea for TIMS
        models.LineplotData.objects.create(qcrun=qcrun, value=qcdata, shortname=name)


def get_file_production(request):
    def get_from_bins(allbins, value, binsize):
        for abin in allbins:
            if value < abin:
                break
            prevbin = abin
        return prevbin + binsize / 2
    lastdate = datetime.now() - timedelta(50)
    # get from db: list of [(size, projtype)]
    projsizelist = [(x['sizesum'] >> 30,
        x['datasetrawfile__dataset__runname__experiment__project__projtype__ptype__name']) for x in 
        RawFile.objects.filter(producer__msinstrument__isnull=False, datasetrawfile__dataset__runname__experiment__project__active=True).values('datasetrawfile__dataset__runname__experiment__project__projtype__ptype__name', 'datasetrawfile__dataset__runname__experiment__project').annotate(sizesum=Sum('size')).order_by('sizesum')]
    lowestsize, highestsize  = projsizelist[0][0], projsizelist[-1][0]
    # Need to round until the last bin of approx size
    #if len(str(lowestsize)) < 3:
    #    firstbin = lowestsize / 10 * 10
    #else:
    #    divider = 10 ** (len(str(lowestsize)) - 1)
    #    firstbin = lowestsize / divider * divider
    #if len(str(highestsize)) < 3:
    #    lastbin = round(highestsize / 10 + 0.5) * 10
    #else:
    #    divider = 10 ** (len(str(highestsize)) - 1)
    #    lastbin = round(highestsize / divider + 0.5) * divider
    firstbin, lastbin = 0, 500
    amount_bins = 30
    binsize = (lastbin - firstbin) / float(amount_bins)
    bins = [firstbin]
    for i in range(amount_bins):
        bins.append(bins[-1] + binsize)
    projdist = {binstart + binsize / 2: {} for binstart in bins}
    for size, ptype in projsizelist:
        sizebin = get_from_bins(bins, size, binsize)
        try:
            projdist[sizebin][ptype] += 1
        except KeyError:
            projdist[sizebin][ptype] = 1
    projdist = {'xkey': 'bin', 'data': [{**{'bin': sizebin}, **vals} for sizebin, vals in projdist.items()]}
    projdate = {}
    for date_proj in RawFile.objects.filter(date__gt=lastdate, producer__msinstrument__isnull=False, claimed=True).annotate(day=Trunc('date', 'day')).values('day', 'datasetrawfile__dataset__runname__experiment__project__projtype__ptype__name').annotate(sizesum=Sum('size')):
        day = datetime.strftime(date_proj['day'], '%Y-%m-%d')
        key = date_proj['datasetrawfile__dataset__runname__experiment__project__projtype__ptype__name']
        try:
            projdate[day][key] = date_proj['sizesum']
        except KeyError:
            projdate[day] = {key: date_proj['sizesum']}
    projdate = {'xkey': 'day', 'data': [{**{'day': day}, **vals} for day, vals in projdate.items()]}

    proddate = {}
    for date_instr in RawFile.objects.filter(date__gt=lastdate, producer__msinstrument__isnull=False).annotate(day=Trunc('date', 'day')).values('day', 'producer__name').annotate(sizesum=Sum('size')):
        day = datetime.strftime(date_instr['day'], '%Y-%m-%d')
        try:
            proddate[day][date_instr['producer__name']] = date_instr['sizesum']
        except KeyError:
            proddate[day] = {date_instr['producer__name']: date_instr['sizesum']}
    instruments = {z for x in proddate.values() for z in list(x.keys())}
    for day, vals in proddate.items():
        for missing_inst in instruments.difference(vals.keys()):
            vals[missing_inst] = 0
    proddate = {'xkey': 'day', 'data': [{**{'day': day}, **vals} for day, vals in proddate.items()]}
    return JsonResponse({
        'projectdistribution': projdist,
        'fileproduction': proddate,
        'projecttypeproduction': projdate,
        })


def update_qcdata(qcrun, data):
    # FIXME rerun old data on new plots or methods at qc task update --> what happens?
    # also FIXME if no changes in msgf etc do recalculation on the analysed files
    old_plots = {p.shortname: p for p in qcrun.boxplotdata_set.all()}
    for lpd in qcrun.lineplotdata_set.exclude(shortname__startswith='miscleav'):
        old_plots[lpd.shortname] = lpd
    for qcname, qcdata in data['plots'].items():
        name = translate_plotname(qcname)
        try:
            oldp = old_plots[name]
        except KeyError:
            create_newplot(qcrun, qcdata, qcname)
        else:
            if type(qcdata) == dict and 'q1' in qcdata:
                oldp.upper = qcdata['upper']
                oldp.lower = qcdata['lower']
                oldp.q1 = qcdata['q1']
                oldp.q2 = qcdata['q2']
                oldp.q3 = qcdata['q3']
                oldp.save()
            elif name == 'missed_cleavages':
                for num_mc, num_psm in qcdata.items():
                    lpd = models.LineplotData.objects.get(qcrun=qcrun, shortname='miscleav{}'.format(num_mc))
                    lpd.value = num_psm
                    lpd.save()
            else:
                oldp.value = qcdata
                oldp.save()


def get_line_data(instrument, days, seriesnames):
    long_qc = []
    fromdate = datetime.now() - timedelta(days)
    for qcrun in models.QCData.objects.filter(rawfile__producer=instrument, rawfile__date__gt=fromdate).annotate(day=Trunc('rawfile__date', 'day')).order_by('day'):
        datepoints = {lplot.shortname: lplot.value for lplot in qcrun.lineplotdata_set.filter(shortname__in=seriesnames)}
        datepoints['day'] = datetime.strftime(qcrun.day, '%Y-%m-%d')
        long_qc.append(datepoints)
    return {'xkey': 'day', 'data': long_qc}
    

def get_boxplot_data(instrument, days, name):
    data = []
    fromdate = datetime.now() - timedelta(days)
    for qcrun in models.QCData.objects.filter(boxplotdata__shortname=name, rawfile__date__gt=fromdate, rawfile__producer=instrument).annotate(day=Trunc('rawfile__date', 'day')).order_by('day'):
        bplot = qcrun.boxplotdata_set.get(shortname=name)
        dayvals = {
            'upper': bplot.upper,
            'lower': bplot.lower,
            'q1': bplot.q1,
            'q2': bplot.q2,
            'q3': bplot.q3,
            }
        dayvals['day'] = datetime.strftime(qcrun.day, '%Y-%m-%d')
        if not isnan(dayvals['upper']):
            data.append(dayvals)
    return {'xkey': 'day', 'data': data}


def show_qc(request, instrument_id):
    days = 100
    return JsonResponse({
        'ident': get_line_data(instrument_id, days, seriesnames=['peptides', 'proteins', 'unique_peptides']),
        'psms': get_line_data(instrument_id, days, ['scans', 'psms', 'miscleav1', 'miscleav2']),
        'fwhm': get_boxplot_data(instrument_id, days, 'fwhms'),
        'precursorarea': get_boxplot_data(instrument_id, days, 'peparea'),
        'prec_error': get_boxplot_data(instrument_id, days, 'perror'),
        'rt': get_boxplot_data(instrument_id, days, 'rt'),
        'msgfscore': get_boxplot_data(instrument_id, days, 'msgfscore'),
        'ionmob': get_boxplot_data(instrument_id, days, 'ionmob'),
        })
