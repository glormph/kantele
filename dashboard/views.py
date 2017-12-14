from datetime import datetime
import os
import json

from django.shortcuts import render
from django.http import (HttpResponse, JsonResponse, HttpResponseNotAllowed,
                         HttpResponseForbidden)
from bokeh.embed import components

from jobs.jobs import Jobstates, is_job_retryable
from jobs.models import Task
from datasets.models import DatasetJob
from rawstatus.models import FileJob, Producer
from dashboard import qcplots, models
from kantele import settings


def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


def store_longitudinal_qc(request):
    """This method is fed JSON over POST"""
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        if ('client_id' not in data or
                data['client_id'] not in settings.CLIENT_APIKEYS):
            return HttpResponseForbidden()
        try:
            qcrun = models.QCData.objects.get(rawfile_id=data['rf_id'])
        except models.QCData.DoesNotExist:
            qcrun = models.QCData(rawfile_id=data['rf_id'],
                                  analysis_id=data['analysis_id'])
            qcrun.save()
            plotmap = {p.shortname: p.id for p in models.Plot.objects.all()}
            for plotname, qcdata in data['plots'].items():
                plot_id = plotmap[plotname]
                create_newplot(qcrun, qcdata, plot_id)
        else:
            update_qcdata(qcrun, data)
        return HttpResponse()
    else:
        return HttpResponseNotAllowed(permitted_methods=['POST'])


def create_newplot(qcrun, qcdata, plot_id):
    if 'q1' in qcdata:
        models.BoxplotData.objects.create(plot_id=plot_id, qcrun=qcrun,
                                          upper=qcdata['upper'],
                                          lower=qcdata['lower'],
                                          q1=qcdata['q1'], q2=qcdata['q2'],
                                          q3=qcdata['q3'])
    else:
        for cat, val in qcdata.items():
            models.LineplotData.objects.create(plot_id=plot_id, qcrun=qcrun,
                                               value=val, category=cat)


def update_qcdata(qcrun, data):
    # FIXME rerun old data on new plots at qc task update --> what happens?
    plotmap = {p.shortname: p.id for p in models.Plot.objects.all()}
    old_plots = {p.plot.shortname: p for p in
                 qcrun.boxplotdata_set.all().select_related('plot')}
    for lpd in qcrun.lineplotdata_set.all().select_related('plot'):
        if lpd.plot.shortname not in old_plots:
            old_plots[lpd.plot.shortname] = [lpd]
        else:
            old_plots[lpd.plot.shortname].append(lpd)
    for plotname, qcdata in data['plots'].items():
        plot_id = plotmap[plotname]
        try:
            oldp = old_plots[plotname]
        except KeyError:
            create_newplot(qcrun, qcdata, plot_id)
        else:
            if 'q1' in qcdata:
                oldp.upper = qcdata['upper']
                oldp.lower = qcdata['lower']
                oldp.q1 = qcdata['q1']
                oldp.q2 = qcdata['q2']
                oldp.q3 = qcdata['q3']
                oldp.save()
            else:
                for op in oldp:
                    op.value = qcdata[op.category]
                    op.save()


def get_longitud_qcdata():
    long_qc = {}
    for qcrun in models.QCData.objects.select_related('rawfile__producer'):
        date, instru = qcrun.rawfile.date, qcrun.rawfile.producer.name
        if instru not in long_qc:
            long_qc[instru] = {}
        for lplot in qcrun.lineplotdata_set.all():
            try:
                long_qc[instru][lplot.plot.shortname][lplot.category].append(
                    (date, lplot.value))
            except KeyError:
                try:
                    long_qc[instru][lplot.plot.shortname][lplot.category] = [
                        (date, lplot.value)]
                except KeyError:
                    long_qc[instru][lplot.plot.shortname] = {
                        lplot.category: [(date, lplot.value)]}
        for boxplot in qcrun.boxplotdata_set.all():
            bplot = {'q1': boxplot.q1, 'q2': boxplot.q2, 'q3': boxplot.q3,
                     'upper': boxplot.upper, 'lower': boxplot.lower}
            try:
                long_qc[instru][boxplot.plot.shortname][date] = bplot
            except KeyError:
                long_qc[instru][boxplot.plot.shortname] = {date: bplot}
    return long_qc


def show_qc(request):
    print('It is run')
    """
    QC data:
        Date, Instrument, RawFile, AnalysisResult
    """
    instruments = [x.name for x in Producer.objects.all()]
    dateddata = get_longitud_qcdata()
    plot = {
        'amount_peptides': qcplots.timeseries_line(dateddata, 'nr_peptides',
                                                   instruments),
        'amount_proteins': qcplots.timeseries_line(dateddata, 'nr_proteins',
                                                   instruments),
        'amount_psms': qcplots.timeseries_line(dateddata, 'nr_psms',
                                               instruments),
        'missed_cleav': qcplots.timeseries_line(dateddata, 'miscleav',
                                                instruments),
        'precursorarea': qcplots.boxplotrange(dateddata, 'peparea',
                                              instruments),
        'prec_error': qcplots.boxplotrange(dateddata, 'perror', instruments),
        'msgfscore': qcplots.boxplotrange(dateddata, 'msgfscore', instruments),
        'rt': qcplots.boxplotrange(dateddata, 'rt', instruments),
            }
    script, div = components(plot, wrap_script=False, wrap_plot_info=False)
    print(JsonResponse({'bokeh_code': {'script': script, 'div': div}}))
    return JsonResponse({'bokeh_code': {'script': script, 'div': div}})


def show_jobs(request):
    jobs = {}
    for task in Task.objects.select_related('job').filter(
            job__state__in=[Jobstates.PENDING, Jobstates.PROCESSING,
                        Jobstates.ERROR]):
        freshjob = {'name': task.job.funcname, 
                    'date': datetime.strftime(task.job.timestamp, '%Y%m%d'),
                    'retry': is_job_retryable(task.job), 'id': task.job.id,
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        if not task.job.state in jobs:
            jobs[task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in jobs[task.job.state]:
            jobs[task.job.state][task.job.id] = freshjob
        jobs[task.job.state][task.job.id]['tasks'][task.state] += 1
    dsfnjobmap = {}
    for dsj in DatasetJob.objects.select_related(
            'dataset__runname__experiment__project', 'dataset__user',
            'job').exclude(job__state=Jobstates.DONE):
        ds = dsj.dataset
        dsname = '{} - {} - {}'.format(ds.runname.experiment.project.name,
                                       ds.runname.experiment.name,
                                       ds.runname.name)
        if dsj.job_id not in dsfnjobmap:
            dsfnjobmap[dsj.job_id] = {
                'user': '{} {}'.format(ds.user.first_name, ds.user.last_name),
                'alttexts': [dsname]}
        else:
            dsfnjobmap[dsj.job_id]['alttexts'].append(dsname)
    for fnj in FileJob.objects.select_related('storedfile__rawfile__producer', 
            'job').exclude(job__state=Jobstates.DONE):
        fname = os.path.join(fnj.storedfile.servershare.name, fnj.storedfile.path,
                             fnj.storedfile.filename)
        dsfnjobmap[fnj.job_id] = {'user': fnj.storedfile.rawfile.producer.name,
                                  'alttexts': [fname]}
    for jstate in [Jobstates.PENDING, Jobstates.PROCESSING, Jobstates.ERROR]:
        if jstate in jobs:
            jobs[jstate] = [x for x in jobs[jstate].values()]
            for job in jobs[jstate]:
                job.update(dsfnjobmap[job['id']])
    return JsonResponse(jobs)
