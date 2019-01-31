from django.shortcuts import render
from django.http import JsonResponse
from bokeh.embed import components

from analysis.models import AnalysisError
from rawstatus.models import Producer
from dashboard import qcplots, models
from kantele import settings


def dashboard(request):
    instruments = Producer.objects.filter(name__in=['Luke', 'Leia', 'Barbie', 'Velos', 'Gin', 'Tonic'])
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


def create_newplot(qcrun, qcdata, name):
    if type(qcdata) == dict and 'q1' in qcdata:
        models.BoxplotData.objects.create(shortname=name, qcrun=qcrun,
                                          upper=qcdata['upper'],
                                          lower=qcdata['lower'],
                                          q1=qcdata['q1'], q2=qcdata['q2'],
                                          q3=qcdata['q3'])
    else:
        models.LineplotData.objects.create(qcrun=qcrun, value=qcdata, shortname=name)


def update_qcdata(qcrun, data):
    # FIXME rerun old data on new plots or methods at qc task update --> what happens?
    # also FIXME if no changes in msgf etc do recalculation on the analysed files
    old_plots = {p.shortname: p for p in qcrun.boxplotdata_set.all()}
    for lpd in qcrun.lineplotdata_set.all():
        old_plots[lpd.shortname] = lpd
    for plotname, qcdata in data['plots'].items():
        try:
            oldp = old_plots[plotname]
        except KeyError:
            create_newplot(qcrun, qcdata, plotname)
        else:
            if type(qcdata) == dict and 'q1' in qcdata:
                oldp.upper = qcdata['upper']
                oldp.lower = qcdata['lower']
                oldp.q1 = qcdata['q1']
                oldp.q2 = qcdata['q2']
                oldp.q3 = qcdata['q3']
                oldp.save()
            else:
                oldp.value = qcdata
                oldp.save()


def get_longitud_qcdata(instrument, wf_id):
    long_qc = {}
    # FIXME this shows data from qc runs for each workflow so if rerun against newer version both results will show
    for qcrun in models.QCData.objects.filter(rawfile__producer=instrument):
                                              #analysis__nextflowsearch__nfworkflow=wf_id):
        date = qcrun.rawfile.date
        for lplot in qcrun.lineplotdata_set.all():
            try:
                long_qc[lplot.shortname].append((date, lplot.value))
            except KeyError:
                try:
                    long_qc[lplot.shortname] = [(date, lplot.value)]
                except KeyError:
                    long_qc[lplot.shortname] = {[(date, lplot.value)]}
        for boxplot in qcrun.boxplotdata_set.all():
            bplot = {'q1': boxplot.q1, 'q2': boxplot.q2, 'q3': boxplot.q3,
                     'upper': boxplot.upper, 'lower': boxplot.lower}
            try:
                long_qc[boxplot.shortname][date] = bplot
            except KeyError:
                long_qc[boxplot.shortname] = {date: bplot}
    return long_qc


def show_qc(request, instrument_id):
    """
    QC data:
        Date, Instrument, RawFile, AnalysisResult
    """
    instrument = Producer.objects.get(pk=instrument_id)
    dateddata = get_longitud_qcdata(instrument, settings.LONGQC_NXF_WF_ID)
    plot = {
        'amount_peptides': qcplots.timeseries_line(dateddata, ['peptides', 'proteins', 'unique_peptides']),
        'amount_psms': qcplots.timeseries_line(dateddata, ['scans', 'psms', 'miscleav1', 'miscleav2']),
        'precursorarea': qcplots.boxplotrange(dateddata, 'peparea'),
        'prec_error': qcplots.boxplotrange(dateddata, 'perror'),
        'msgfscore': qcplots.boxplotrange(dateddata, 'msgfscore'),
        'rt': qcplots.boxplotrange(dateddata, 'rt'),
            }
    script, div = components(plot, wrap_script=False, wrap_plot_info=False)
    return JsonResponse({'bokeh_code': {'script': script, 'div': div}})
